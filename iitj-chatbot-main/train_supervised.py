"""
train_supervised.py — Supervised Fine-tuning with LoRA (PEFT)
=============================================================
Fine-tunes the pretrained IIT Jammu model on Q&A instruction-following pairs
using LoRA (Low-Rank Adaptation) for parameter-efficient training.

USAGE:
  python train_supervised.py
  python train_supervised.py --base-model models/pretrained_iitj
  python train_supervised.py --dataset data/supervised_dataset.jsonl --epochs 5
  python train_supervised.py --base-model mistralai/Mistral-7B-v0.1

INPUT:
  data/supervised_dataset.jsonl  — instruction-following Q&A pairs
  models/pretrained_iitj/        — pretrained model (or HF model ID as fallback)

OUTPUT:
  models/finetuned_iitj/         — LoRA adapter weights + merged model
  models/training_logs.json      — updated training log
"""

import os
import json
import logging
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────
ROOT_DIR        = Path(__file__).resolve().parent
MODELS_DIR      = ROOT_DIR / "models"
PRETRAINED_DIR  = MODELS_DIR / "pretrained_iitj"
FINETUNED_DIR   = MODELS_DIR / "finetuned_iitj"
LOGS_FILE       = MODELS_DIR / "training_logs.json"
DEFAULT_DATASET = ROOT_DIR / "data" / "supervised_dataset.jsonl"

# ── Defaults ──────────────────────────────────────────────────────
DEFAULT_BASE_MODEL  = "mistralai/Mistral-7B-v0.1"
DEFAULT_EPOCHS      = 3
DEFAULT_BATCH_SIZE  = 2
DEFAULT_LR          = 2e-4
DEFAULT_MAX_LENGTH  = 512
DEFAULT_SAVE_STEPS  = 100
DEFAULT_VAL_SPLIT   = 0.1

# LoRA hyperparameters
LORA_R          = 16
LORA_ALPHA      = 32
LORA_DROPOUT    = 0.05
LORA_TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"]


# ══════════════════════════════════════════════════════════════════
#  Dataset
# ══════════════════════════════════════════════════════════════════

def _load_jsonl(path: Path) -> List[Dict]:
    """Load JSONL file into a list of dicts."""
    records: List[Dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _format_prompt(record: Dict) -> str:
    """
    Convert a Q&A record into an instruction-following prompt string.

    Format:
        ### Instruction:
        {instruction}

        ### Context:
        {context}

        ### Response:
        {response}
    """
    instruction = record.get("instruction", "").strip()
    context     = record.get("context", "").strip()
    response    = record.get("response", "").strip()

    parts = ["### Instruction:", instruction]
    if context:
        parts += ["", "### Context:", context]
    parts += ["", "### Response:", response]
    return "\n".join(parts)


def build_dataset(jsonl_path: Path, tokenizer, max_length: int, val_split: float):
    """Load JSONL, format prompts, tokenize, and split train/val."""
    from datasets import Dataset

    records = _load_jsonl(jsonl_path)
    if not records:
        raise RuntimeError(f"No records found in {jsonl_path}")
    logger.info("Loaded %d records from %s", len(records), jsonl_path)

    prompts = [_format_prompt(r) for r in records]

    def tokenize(batch):
        tokenized = tokenizer(
            batch["text"],
            truncation=True,
            padding="max_length",
            max_length=max_length,
        )
        # For CLM, labels == input_ids (shift is handled inside the model)
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    raw = Dataset.from_dict({"text": prompts})
    tokenized = raw.map(tokenize, batched=True, remove_columns=["text"])
    split = tokenized.train_test_split(test_size=val_split, seed=42)
    logger.info(
        "Dataset split: %d train | %d validation",
        len(split["train"]), len(split["test"]),
    )
    return split


# ══════════════════════════════════════════════════════════════════
#  Training
# ══════════════════════════════════════════════════════════════════

def _resolve_base_model(args) -> str:
    """
    Return the model path to load from:
      1. Explicitly passed --base-model argument
      2. models/pretrained_iitj/ if it exists
      3. Default HuggingFace model ID
    """
    if args.base_model:
        return args.base_model
    if PRETRAINED_DIR.exists() and any(PRETRAINED_DIR.iterdir()):
        logger.info("Using local pretrained model from %s", PRETRAINED_DIR)
        return str(PRETRAINED_DIR)
    logger.info(
        "Local pretrained model not found, using HF model: %s",
        DEFAULT_BASE_MODEL,
    )
    return DEFAULT_BASE_MODEL


def train(args):
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        TrainingArguments,
        DataCollatorForSeq2Seq,
    )
    from peft import (
        LoraConfig,
        TaskType,
        get_peft_model,
        prepare_model_for_kbit_training,
    )
    from trl import SFTTrainer

    FINETUNED_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Device ────────────────────────────────────────────────────
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Using device: %s", device)

    base_model_path = _resolve_base_model(args)

    # ── Tokenizer ─────────────────────────────────────────────────
    logger.info("Loading tokenizer from: %s", base_model_path)
    tokenizer = AutoTokenizer.from_pretrained(
        base_model_path,
        use_fast=True,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # ── Model ─────────────────────────────────────────────────────
    logger.info("Loading base model from: %s", base_model_path)
    load_kwargs: Dict[str, Any] = {
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
    }

    # 4-bit quantization for memory efficiency when on GPU
    if device == "cuda":
        try:
            from transformers import BitsAndBytesConfig
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
            load_kwargs["quantization_config"] = bnb_config
            load_kwargs["device_map"] = "auto"
            logger.info("Using 4-bit quantization (bitsandbytes)")
        except Exception as e:
            logger.warning("4-bit quantization unavailable (%s) — loading in fp16", e)
            load_kwargs["torch_dtype"] = torch.float16
            load_kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(base_model_path, **load_kwargs)
    model.config.use_cache = False
    model.config.pretraining_tp = 1

    # Prepare for k-bit training if quantized
    if device == "cuda":
        model = prepare_model_for_kbit_training(model)

    # ── LoRA configuration ────────────────────────────────────────
    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        target_modules=LORA_TARGET_MODULES,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ── Dataset ───────────────────────────────────────────────────
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}\n"
            "Run first: python generate_supervised_data.py"
        )
    dataset = build_dataset(dataset_path, tokenizer, args.max_length, args.val_split)

    # ── Training arguments ────────────────────────────────────────
    training_args = TrainingArguments(
        output_dir=str(FINETUNED_DIR),
        overwrite_output_dir=True,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        evaluation_strategy="steps",
        eval_steps=args.save_steps,
        save_steps=args.save_steps,
        save_total_limit=2,
        learning_rate=args.lr,
        warmup_ratio=0.03,
        weight_decay=0.001,
        fp16=(device == "cuda"),
        bf16=False,
        max_grad_norm=0.3,
        lr_scheduler_type="cosine",
        logging_steps=25,
        logging_dir=str(MODELS_DIR / "logs"),
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to="none",
        dataloader_num_workers=0,
        optim="paged_adamw_32bit" if device == "cuda" else "adamw_torch",
        gradient_checkpointing=(device == "cuda"),
        group_by_length=True,
    )

    # ── Trainer (SFTTrainer from trl) ─────────────────────────────
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        tokenizer=tokenizer,
        dataset_text_field=None,     # already tokenized
        max_seq_length=args.max_length,
        packing=False,
    )

    logger.info(
        "Starting supervised fine-tuning | base=%s | epochs=%d | "
        "batch=%d | lr=%g | train_samples=%d | val_samples=%d",
        base_model_path, args.epochs, args.batch_size, args.lr,
        len(dataset["train"]), len(dataset["test"]),
    )
    start_time = time.time()
    train_result = trainer.train()
    elapsed = time.time() - start_time

    # ── Evaluate on validation set ────────────────────────────────
    eval_results = trainer.evaluate()
    val_loss = eval_results.get("eval_loss", float("nan"))
    logger.info("Validation loss: %.4f", val_loss)
    if val_loss > 2.0:
        logger.warning(
            "⚠  Validation loss %.4f > 2.0 — consider more training data or epochs",
            val_loss,
        )

    # ── Save LoRA adapter ─────────────────────────────────────────
    logger.info("Saving LoRA adapter to %s …", FINETUNED_DIR)
    trainer.model.save_pretrained(str(FINETUNED_DIR))
    tokenizer.save_pretrained(str(FINETUNED_DIR))

    # Save a model card
    (FINETUNED_DIR / "pytorch_model.json").write_text(
        json.dumps(
            {
                "base_model": base_model_path,
                "lora_r": LORA_R,
                "lora_alpha": LORA_ALPHA,
                "train_samples": len(dataset["train"]),
                "val_loss": round(val_loss, 4),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            indent=2,
        )
    )

    # ── Update logs ───────────────────────────────────────────────
    log_entry: Dict[str, Any] = {
        "stage": "supervised_finetuning",
        "base_model": base_model_path,
        "epochs": args.epochs,
        "train_samples": len(dataset["train"]),
        "val_samples": len(dataset["test"]),
        "train_loss": round(train_result.training_loss, 4),
        "val_loss": round(val_loss, 4),
        "elapsed_seconds": round(elapsed, 1),
        "output_dir": str(FINETUNED_DIR),
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
        "✅ Fine-tuning complete | train_loss=%.4f | val_loss=%.4f | "
        "elapsed=%.1fs | saved to %s",
        train_result.training_loss, val_loss, elapsed, FINETUNED_DIR,
    )
    return train_result


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Supervised fine-tuning of IIT Jammu LLM with LoRA"
    )
    p.add_argument(
        "--base-model", default=None,
        help="Path to pretrained model or HF model ID "
             "(default: models/pretrained_iitj or mistralai/Mistral-7B-v0.1)",
    )
    p.add_argument(
        "--dataset", default=str(DEFAULT_DATASET),
        help="Path to supervised JSONL dataset (default: %(default)s)",
    )
    p.add_argument("--epochs",     type=int,   default=DEFAULT_EPOCHS)
    p.add_argument("--batch-size", type=int,   default=DEFAULT_BATCH_SIZE)
    p.add_argument("--lr",         type=float, default=DEFAULT_LR)
    p.add_argument("--max-length", type=int,   default=DEFAULT_MAX_LENGTH)
    p.add_argument("--save-steps", type=int,   default=DEFAULT_SAVE_STEPS)
    p.add_argument("--val-split",  type=float, default=DEFAULT_VAL_SPLIT,
                   help="Fraction of data for validation (default: %(default)s)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args)
