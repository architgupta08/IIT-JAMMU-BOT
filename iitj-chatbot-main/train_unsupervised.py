"""
train_unsupervised.py — Unsupervised Pretraining on IIT Jammu Data
==================================================================
Loads all markdown files from data/processed/ (or data/raw/ as fallback),
tokenizes using the Mistral-7B tokenizer, and pretrains a causal language
model (CLM) on the IIT Jammu corpus using next-token prediction.

USAGE:
  python train_unsupervised.py                          # default settings
  python train_unsupervised.py --data-dir data/raw      # use raw markdown
  python train_unsupervised.py --epochs 3 --batch-size 4
  python train_unsupervised.py --model-name mistralai/Mistral-7B-v0.1

OUTPUT:
  models/pretrained_iitj/  — saved checkpoint + tokenizer
  models/training_logs.json — loss history
"""

import os
import json
import logging
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────
ROOT_DIR       = Path(__file__).resolve().parent
DATA_RAW_DIR   = ROOT_DIR / "data" / "raw"
DATA_PROC_DIR  = ROOT_DIR / "data" / "processed"
MODELS_DIR     = ROOT_DIR / "models"
OUTPUT_DIR     = MODELS_DIR / "pretrained_iitj"
LOGS_FILE      = MODELS_DIR / "training_logs.json"

# ── Defaults ──────────────────────────────────────────────────────
DEFAULT_MODEL      = "mistralai/Mistral-7B-v0.1"
DEFAULT_EPOCHS     = 3
DEFAULT_BATCH_SIZE = 2
DEFAULT_LR         = 2e-5
DEFAULT_MAX_LENGTH = 512
DEFAULT_SAVE_STEPS = 200


# ══════════════════════════════════════════════════════════════════
#  Data Loading
# ══════════════════════════════════════════════════════════════════

def _load_markdown_texts(data_dir: Path) -> List[str]:
    """Return cleaned text from every .md file in *data_dir*."""
    texts: List[str] = []
    md_files = sorted(data_dir.glob("**/*.md"))

    if not md_files:
        logger.warning("No .md files found in %s", data_dir)
        return texts

    for p in md_files:
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
            # Strip YAML front-matter
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                raw = parts[2] if len(parts) >= 3 else raw
            text = raw.strip()
            if len(text) > 100:            # skip near-empty files
                texts.append(text)
        except Exception as exc:
            logger.warning("Skipping %s — %s", p, exc)

    logger.info("Loaded %d markdown documents from %s", len(texts), data_dir)
    return texts


def _load_json_index_texts(index_path: Path) -> List[str]:
    """Fallback: extract text blobs from the processed JSON index."""
    texts: List[str] = []
    if not index_path.exists():
        return texts

    data = json.loads(index_path.read_text(encoding="utf-8"))

    def _walk(nodes: list):
        for node in nodes:
            txt = node.get("text", "").strip()
            if len(txt) > 100:
                title = node.get("title", "")
                texts.append(f"{title}\n{txt}" if title else txt)
            # Support both 'children' and 'nodes' key names
            _walk(node.get("children", node.get("nodes", [])))

    _walk(data.get("structure", []))
    logger.info("Loaded %d text blobs from JSON index %s", len(texts), index_path)
    return texts


def collect_corpus(data_dir: Path) -> List[str]:
    """
    Collect training corpus in priority order:
      1. Markdown files in data_dir
      2. Markdown files in data/raw/
      3. Texts extracted from data/processed/iitj_index.json
    """
    texts = _load_markdown_texts(data_dir)

    if not texts and data_dir != DATA_RAW_DIR:
        logger.info("Trying data/raw/ …")
        texts = _load_markdown_texts(DATA_RAW_DIR)

    if not texts:
        logger.info("Falling back to JSON index …")
        texts = _load_json_index_texts(DATA_PROC_DIR / "iitj_index.json")

    if not texts:
        raise RuntimeError(
            "No training data found. Run the scraper first:\n"
            "  cd scraper && python crawler_v3.py --max 500"
        )

    logger.info("Total corpus: %d documents", len(texts))
    return texts


# ══════════════════════════════════════════════════════════════════
#  Dataset
# ══════════════════════════════════════════════════════════════════

def build_dataset(texts: List[str], tokenizer, max_length: int):
    """Create a HuggingFace Dataset with tokenized + chunked text."""
    from datasets import Dataset

    def _chunk_text(text: str) -> List[str]:
        """Split long texts into overlapping chunks of ~max_length tokens."""
        words = text.split()
        chunk_words = max_length // 2      # rough estimate
        overlap = chunk_words // 4
        chunks, start = [], 0
        while start < len(words):
            end = min(start + chunk_words, len(words))
            chunks.append(" ".join(words[start:end]))
            if end == len(words):
                break
            start += chunk_words - overlap
        return chunks

    all_chunks: List[str] = []
    for txt in texts:
        all_chunks.extend(_chunk_text(txt))

    logger.info("Created %d text chunks for training", len(all_chunks))

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_special_tokens_mask=True,
        )

    raw = Dataset.from_dict({"text": all_chunks})
    tokenized = raw.map(tokenize, batched=True, remove_columns=["text"])
    tokenized = tokenized.train_test_split(test_size=0.05, seed=42)
    return tokenized


# ══════════════════════════════════════════════════════════════════
#  Training
# ══════════════════════════════════════════════════════════════════

def train(args):
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        DataCollatorForLanguageModeling,
        TrainingArguments,
        Trainer,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Device ────────────────────────────────────────────────────
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Using device: %s", device)

    # ── Tokenizer ─────────────────────────────────────────────────
    logger.info("Loading tokenizer: %s", args.model_name)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name,
        use_fast=True,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── Model ─────────────────────────────────────────────────────
    logger.info("Loading model: %s", args.model_name)
    load_kwargs: Dict[str, Any] = {
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
    }
    if device == "cuda":
        load_kwargs["torch_dtype"] = torch.float16
        load_kwargs["device_map"] = "auto"

    # Mistral is a causal LM, so we use CLM objective (not MLM)
    model = AutoModelForCausalLM.from_pretrained(args.model_name, **load_kwargs)
    model.config.use_cache = False

    # ── Data ──────────────────────────────────────────────────────
    data_dir = Path(args.data_dir)
    texts = collect_corpus(data_dir)
    dataset = build_dataset(texts, tokenizer, args.max_length)

    # CLM data collator (no masking — predict next token)
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,         # Mistral uses CLM, not MLM
    )

    # ── Training arguments ────────────────────────────────────────
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        overwrite_output_dir=True,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        evaluation_strategy="steps",
        eval_steps=args.save_steps,
        save_steps=args.save_steps,
        save_total_limit=2,
        learning_rate=args.lr,
        warmup_ratio=0.05,
        weight_decay=0.01,
        fp16=(device == "cuda"),
        logging_dir=str(MODELS_DIR / "logs"),
        logging_steps=50,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to="none",           # no wandb / tensorboard required
        dataloader_num_workers=0,
        gradient_accumulation_steps=4,
        gradient_checkpointing=(device == "cuda"),
    )

    # ── Trainer ───────────────────────────────────────────────────
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        data_collator=data_collator,
        tokenizer=tokenizer,
    )

    logger.info(
        "Starting pretraining | epochs=%d | batch=%d | lr=%g | train_samples=%d",
        args.epochs, args.batch_size, args.lr, len(dataset["train"]),
    )
    start_time = time.time()
    train_result = trainer.train()
    elapsed = time.time() - start_time

    # ── Save checkpoint ───────────────────────────────────────────
    logger.info("Saving pretrained model to %s …", OUTPUT_DIR)
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))

    # ── Save logs ─────────────────────────────────────────────────
    log_entry: Dict[str, Any] = {
        "stage": "unsupervised_pretraining",
        "model_name": args.model_name,
        "epochs": args.epochs,
        "train_samples": len(dataset["train"]),
        "eval_samples": len(dataset["test"]),
        "elapsed_seconds": round(elapsed, 1),
        "train_loss": round(train_result.training_loss, 4),
        "output_dir": str(OUTPUT_DIR),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    existing_logs: List[Dict] = []
    if LOGS_FILE.exists():
        try:
            existing_logs = json.loads(LOGS_FILE.read_text())
        except Exception:
            pass
    existing_logs.append(log_entry)
    LOGS_FILE.write_text(json.dumps(existing_logs, indent=2))

    logger.info(
        "✅ Pretraining complete | loss=%.4f | elapsed=%.1fs | saved to %s",
        train_result.training_loss, elapsed, OUTPUT_DIR,
    )
    return train_result


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Unsupervised pretraining on IIT Jammu markdown corpus"
    )
    p.add_argument("--model-name",  default=DEFAULT_MODEL,
                   help="HuggingFace model ID (default: %(default)s)")
    p.add_argument("--data-dir",    default=str(DATA_PROC_DIR),
                   help="Directory with .md files (default: %(default)s)")
    p.add_argument("--epochs",      type=int,   default=DEFAULT_EPOCHS,
                   help="Number of training epochs (default: %(default)s)")
    p.add_argument("--batch-size",  type=int,   default=DEFAULT_BATCH_SIZE,
                   help="Per-device batch size (default: %(default)s)")
    p.add_argument("--lr",          type=float, default=DEFAULT_LR,
                   help="Learning rate (default: %(default)s)")
    p.add_argument("--max-length",  type=int,   default=DEFAULT_MAX_LENGTH,
                   help="Max token sequence length (default: %(default)s)")
    p.add_argument("--save-steps",  type=int,   default=DEFAULT_SAVE_STEPS,
                   help="Save/eval interval in steps (default: %(default)s)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args)
