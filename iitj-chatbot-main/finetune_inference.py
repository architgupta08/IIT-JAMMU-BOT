"""
finetune_inference.py — Fine-tuned LLM Inference Wrapper
=========================================================
Loads the fine-tuned IIT Jammu model and provides an inference interface
that is **drop-in compatible** with the existing GeminiClient / GroqClient
used by the RAG engine.

USAGE (standalone):
  python finetune_inference.py
  python finetune_inference.py --query "What is the fee structure for B.Tech?"

USAGE (as a module):
  from finetune_inference import get_finetuned_client
  client = get_finetuned_client()
  answer = await client.generate("What is the fee at IIT Jammu?")
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ROOT_DIR       = Path(__file__).resolve().parent
MODELS_DIR     = ROOT_DIR / "models"
FINETUNED_DIR  = MODELS_DIR / "finetuned_iitj"
PRETRAINED_DIR = MODELS_DIR / "pretrained_iitj"

# Default fallback HF model if no local weights are found
_DEFAULT_HF_MODEL = "mistralai/Mistral-7B-v0.1"


# ══════════════════════════════════════════════════════════════════
#  Inference client (compatible with GeminiClient interface)
# ══════════════════════════════════════════════════════════════════

class FinetunedModelClient:
    """
    Wraps a locally fine-tuned (LoRA) or pretrained causal LM for inference.

    Provides the same async interface as GeminiClient so it can be used
    as a drop-in replacement inside rag_engine.py / main.py:
      - generate(prompt, system_instruction) -> str
      - formulate_answer(query, context, target_language) -> str
    """

    def __init__(self, model_path: Optional[str] = None):
        self._model_path = model_path or self._resolve_model_path()
        self._model = None
        self._tokenizer = None
        self._device = None
        self._loaded = False
        logger.info("FinetunedModelClient initialised | path=%s", self._model_path)

    # ── Model path resolution ─────────────────────────────────────

    @staticmethod
    def _resolve_model_path() -> str:
        """
        Return the best available model path:
          1. FINETUNED_MODEL_PATH env var
          2. models/finetuned_iitj/  (LoRA adapter)
          3. models/pretrained_iitj/ (base pretrained)
          4. HF model ID (download on first use)
        """
        env_path = os.getenv("FINETUNED_MODEL_PATH")
        if env_path and Path(env_path).exists():
            return env_path

        if FINETUNED_DIR.exists() and any(FINETUNED_DIR.iterdir()):
            return str(FINETUNED_DIR)

        if PRETRAINED_DIR.exists() and any(PRETRAINED_DIR.iterdir()):
            logger.warning(
                "Fine-tuned model not found, falling back to pretrained model"
            )
            return str(PRETRAINED_DIR)

        logger.warning(
            "No local model found. Will download %s on first inference call.",
            _DEFAULT_HF_MODEL,
        )
        return _DEFAULT_HF_MODEL

    # ── Lazy loading ──────────────────────────────────────────────

    def _load(self):
        """Load model + tokenizer on first call (lazy initialisation)."""
        if self._loaded:
            return

        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(
            "Loading fine-tuned model from %s on %s …",
            self._model_path, self._device,
        )

        # Tokenizer
        self._tokenizer = AutoTokenizer.from_pretrained(
            self._model_path,
            use_fast=True,
            trust_remote_code=True,
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        # Model
        load_kwargs = {"trust_remote_code": True, "low_cpu_mem_usage": True}
        if self._device == "cuda":
            load_kwargs["torch_dtype"] = torch.float16
            load_kwargs["device_map"] = "auto"

        # Check if this is a LoRA adapter directory
        adapter_cfg = Path(self._model_path) / "adapter_config.json"
        if adapter_cfg.exists():
            from peft import PeftModel
            # Load base model first, then apply adapter
            cfg = json.loads(adapter_cfg.read_text())
            base_id = cfg.get("base_model_name_or_path", _DEFAULT_HF_MODEL)
            logger.info("Loading LoRA adapter | base_model=%s", base_id)
            base = AutoModelForCausalLM.from_pretrained(base_id, **load_kwargs)
            self._model = PeftModel.from_pretrained(base, self._model_path)
        else:
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_path, **load_kwargs
            )

        self._model.eval()
        self._loaded = True
        logger.info("✅ Fine-tuned model loaded")

    # ── Inference ─────────────────────────────────────────────────

    def _generate_sync(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.1,
        do_sample: bool = False,
    ) -> str:
        """Synchronous text generation."""
        import torch

        self._load()

        inputs = self._tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
        )
        input_ids = inputs["input_ids"].to(self._device)

        with torch.no_grad():
            output_ids = self._model.generate(
                input_ids,
                max_new_tokens=max_new_tokens,
                temperature=temperature if do_sample else 1.0,
                do_sample=do_sample,
                repetition_penalty=1.1,
                pad_token_id=self._tokenizer.pad_token_id,
                eos_token_id=self._tokenizer.eos_token_id,
            )

        # Decode only the newly generated tokens
        new_ids = output_ids[0][input_ids.shape[1]:]
        return self._tokenizer.decode(new_ids, skip_special_tokens=True).strip()

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """
        Async wrapper around _generate_sync.
        Compatible with GeminiClient.generate().
        """
        import asyncio

        full_prompt = prompt
        if system_instruction:
            full_prompt = f"### System:\n{system_instruction}\n\n### User:\n{prompt}\n\n### Assistant:\n"

        # Run synchronous inference in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._generate_sync, full_prompt)
        return result

    async def formulate_answer(
        self,
        query: str,
        context: str,
        target_language: str = "en",
    ) -> str:
        """
        Formulate an answer using the instruction-following prompt format.
        Compatible with GeminiClient.formulate_answer().
        """
        lang_map = {
            "hi": "Hindi",
            "de": "German",
            "fr": "French",
            "it": "Italian",
            "pt": "Portuguese",
            "es": "Spanish",
            "th": "Thai",
        }
        lang_name = lang_map.get(target_language, "")
        lang_instr = (
            f"\nIMPORTANT: Your entire response MUST be written in {lang_name}.\n"
            if lang_name else ""
        )

        prompt = (
            "### Instruction:\n"
            "You are the official AI Assistant for IIT Jammu. "
            "Answer the question using ONLY the context provided. "
            "If the answer is not in the context, say so clearly and suggest "
            "visiting https://www.iitjammu.ac.in."
            f"{lang_instr}\n\n"
            f"### Context:\n{context}\n\n"
            f"### Question:\n{query}\n\n"
            "### Response:\n"
        )

        return await self.generate(prompt)


# ══════════════════════════════════════════════════════════════════
#  Singleton
# ══════════════════════════════════════════════════════════════════

_client: Optional[FinetunedModelClient] = None


def get_finetuned_client(model_path: Optional[str] = None) -> FinetunedModelClient:
    """Return the singleton FinetunedModelClient (create on first call)."""
    global _client
    if _client is None:
        _client = FinetunedModelClient(model_path=model_path)
    return _client


# ══════════════════════════════════════════════════════════════════
#  Standalone CLI
# ══════════════════════════════════════════════════════════════════

async def _interactive_demo():
    import asyncio

    client = get_finetuned_client()
    print("\n🤖 IIT Jammu Fine-tuned LLM — Interactive Demo")
    print("=" * 50)
    print("Type your question (or 'quit' to exit)\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if query.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        if not query:
            continue

        print("Bot: ", end="", flush=True)
        answer = await client.generate(
            f"### Instruction:\nYou are the IIT Jammu AI Assistant. Answer: {query}\n\n"
            "### Response:\n"
        )
        print(answer)
        print()


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Run inference with the fine-tuned IIT Jammu model"
    )
    parser.add_argument(
        "--query", "-q", default=None,
        help="Single question to answer (omit for interactive mode)",
    )
    parser.add_argument(
        "--model-path", default=None,
        help="Path to model directory (default: auto-detect from models/)",
    )
    cli_args = parser.parse_args()

    if cli_args.query:
        client = get_finetuned_client(model_path=cli_args.model_path)
        answer = asyncio.run(
            client.generate(
                f"### Instruction:\nYou are the IIT Jammu AI Assistant. "
                f"Answer: {cli_args.query}\n\n### Response:\n"
            )
        )
        print(f"\nQ: {cli_args.query}")
        print(f"A: {answer}")
    else:
        asyncio.run(_interactive_demo())
