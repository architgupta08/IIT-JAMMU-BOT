#!/usr/bin/env bash
# =============================================================================
# scripts/train_full.sh — Complete IIT Jammu LLM Fine-tuning Pipeline
# =============================================================================
# Runs the full training pipeline end-to-end:
#   Step 1: Generate supervised dataset from knowledge base
#   Step 2: Unsupervised pretraining on markdown corpus
#   Step 3: Supervised fine-tuning with LoRA
#
# USAGE:
#   chmod +x scripts/train_full.sh
#   ./scripts/train_full.sh                        # default settings
#   ./scripts/train_full.sh --skip-pretrain        # skip step 2 (use HF model)
#   ./scripts/train_full.sh --model mistralai/Mistral-7B-v0.1
#   ./scripts/train_full.sh --epochs 5
#
# REQUIREMENTS:
#   pip install -r requirements_finetune.txt
#
# GPU vs CPU:
#   GPU: ~2-3 hours total
#   CPU: ~12+ hours total (not recommended for pretraining)
# =============================================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # no colour

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Defaults ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

MODEL_NAME="mistralai/Mistral-7B-v0.1"
EPOCHS_PRETRAIN=3
EPOCHS_FINETUNE=3
BATCH_SIZE=2
MIN_PAIRS=500
SKIP_PRETRAIN=false
SKIP_DATAGEN=false
LOG_FILE="$ROOT_DIR/models/pipeline.log"

# ── Argument parsing ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --model)           MODEL_NAME="$2"; shift 2 ;;
    --epochs)          EPOCHS_PRETRAIN="$2"; EPOCHS_FINETUNE="$2"; shift 2 ;;
    --epochs-pretrain) EPOCHS_PRETRAIN="$2"; shift 2 ;;
    --epochs-finetune) EPOCHS_FINETUNE="$2"; shift 2 ;;
    --batch-size)      BATCH_SIZE="$2"; shift 2 ;;
    --min-pairs)       MIN_PAIRS="$2"; shift 2 ;;
    --skip-pretrain)   SKIP_PRETRAIN=true; shift ;;
    --skip-datagen)    SKIP_DATAGEN=true; shift ;;
    --help|-h)
      echo "Usage: $0 [options]"
      echo "  --model NAME           HuggingFace model ID (default: $MODEL_NAME)"
      echo "  --epochs N             Epochs for both stages (default: $EPOCHS_PRETRAIN)"
      echo "  --epochs-pretrain N    Epochs for pretraining only"
      echo "  --epochs-finetune N    Epochs for fine-tuning only"
      echo "  --batch-size N         Per-device batch size (default: $BATCH_SIZE)"
      echo "  --min-pairs N          Minimum Q&A pairs to generate (default: $MIN_PAIRS)"
      echo "  --skip-pretrain        Skip Step 2 (use HF model directly for fine-tuning)"
      echo "  --skip-datagen         Skip Step 1 (use existing dataset)"
      exit 0
      ;;
    *) error "Unknown argument: $1"; exit 1 ;;
  esac
done

# ── Setup ─────────────────────────────────────────────────────────
mkdir -p "$ROOT_DIR/models"
mkdir -p "$ROOT_DIR/models/pretrained_iitj"
mkdir -p "$ROOT_DIR/models/finetuned_iitj"
mkdir -p "$ROOT_DIR/data"

exec > >(tee -a "$LOG_FILE") 2>&1

PIPELINE_START=$(date +%s)
echo ""
echo "============================================================"
echo "  IIT Jammu LLM Fine-tuning Pipeline"
echo "  Started: $(date)"
echo "============================================================"
echo ""

# ── Detect GPU ────────────────────────────────────────────────────
if python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  GPU_INFO=$(python -c "import torch; print(torch.cuda.get_device_name(0))")
  info "GPU detected: $GPU_INFO"
  DEVICE="cuda"
else
  warn "No GPU detected — training will be slow on CPU"
  DEVICE="cpu"
fi

# ── Python binary ─────────────────────────────────────────────────
PYTHON="${PYTHON:-python}"
if ! "$PYTHON" --version &>/dev/null; then
  PYTHON=python3
fi
info "Using Python: $($PYTHON --version)"

# ── Check dependencies ────────────────────────────────────────────
info "Checking fine-tuning dependencies …"
cd "$ROOT_DIR"
if ! "$PYTHON" -c "import transformers, peft, trl, datasets" 2>/dev/null; then
  warn "Some dependencies missing. Installing from requirements_finetune.txt …"
  "$PYTHON" -m pip install -q -r requirements_finetune.txt
  success "Dependencies installed"
else
  success "All dependencies available"
fi

# ─────────────────────────────────────────────────────────────────
# STEP 1 — Generate supervised dataset
# ─────────────────────────────────────────────────────────────────
if [[ "$SKIP_DATAGEN" == "true" ]]; then
  warn "Step 1 skipped (--skip-datagen)"
else
  echo ""
  echo "------------------------------------------------------------"
  echo "  STEP 1/3 — Generate Supervised Dataset"
  echo "------------------------------------------------------------"

  STEP1_START=$(date +%s)
  "$PYTHON" generate_supervised_data.py --min-pairs "$MIN_PAIRS"
  STEP1_END=$(date +%s)
  STEP1_ELAPSED=$(( STEP1_END - STEP1_START ))

  PAIR_COUNT=$(wc -l < data/supervised_dataset.jsonl 2>/dev/null || echo 0)
  success "Step 1 complete | $PAIR_COUNT Q&A pairs | $(( STEP1_ELAPSED / 60 ))m $(( STEP1_ELAPSED % 60 ))s"

  if [[ "$PAIR_COUNT" -lt "$MIN_PAIRS" ]]; then
    warn "Only $PAIR_COUNT pairs generated (min: $MIN_PAIRS)."
    warn "Run the scraper to collect more data for better results."
  fi
fi

# ─────────────────────────────────────────────────────────────────
# STEP 2 — Unsupervised pretraining
# ─────────────────────────────────────────────────────────────────
if [[ "$SKIP_PRETRAIN" == "true" ]]; then
  warn "Step 2 skipped (--skip-pretrain) — fine-tuning will use HF model directly"
else
  echo ""
  echo "------------------------------------------------------------"
  echo "  STEP 2/3 — Unsupervised Pretraining"
  echo "  Model : $MODEL_NAME"
  echo "  Epochs: $EPOCHS_PRETRAIN"
  echo "  Device: $DEVICE"
  echo "------------------------------------------------------------"

  if [[ "$DEVICE" == "cpu" ]]; then
    warn "Pretraining on CPU may take 6+ hours."
    warn "Consider using --skip-pretrain to go directly to fine-tuning."
    read -t 10 -p "Continue? [y/N] " REPLY || REPLY="n"
    if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
      warn "Pretraining skipped by user"
      SKIP_PRETRAIN=true
    fi
  fi

  if [[ "$SKIP_PRETRAIN" == "false" ]]; then
    STEP2_START=$(date +%s)
    "$PYTHON" train_unsupervised.py \
      --model-name "$MODEL_NAME" \
      --epochs "$EPOCHS_PRETRAIN" \
      --batch-size "$BATCH_SIZE"
    STEP2_END=$(date +%s)
    STEP2_ELAPSED=$(( STEP2_END - STEP2_START ))

    success "Step 2 complete | elapsed $(( STEP2_ELAPSED / 60 ))m $(( STEP2_ELAPSED % 60 ))s"
    success "Pretrained model saved to models/pretrained_iitj/"
  fi
fi

# ─────────────────────────────────────────────────────────────────
# STEP 3 — Supervised fine-tuning
# ─────────────────────────────────────────────────────────────────
echo ""
echo "------------------------------------------------------------"
echo "  STEP 3/3 — Supervised Fine-tuning (LoRA)"
echo "  Epochs: $EPOCHS_FINETUNE"
echo "  Device: $DEVICE"
echo "------------------------------------------------------------"

STEP3_START=$(date +%s)
"$PYTHON" train_supervised.py \
  --epochs "$EPOCHS_FINETUNE" \
  --batch-size "$BATCH_SIZE"
STEP3_END=$(date +%s)
STEP3_ELAPSED=$(( STEP3_END - STEP3_START ))

success "Step 3 complete | elapsed $(( STEP3_ELAPSED / 60 ))m $(( STEP3_ELAPSED % 60 ))s"
success "Fine-tuned model saved to models/finetuned_iitj/"

# ─────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────
PIPELINE_END=$(date +%s)
TOTAL_ELAPSED=$(( PIPELINE_END - PIPELINE_START ))

echo ""
echo "============================================================"
echo "  Pipeline Complete"
echo "  Total time: $(( TOTAL_ELAPSED / 3600 ))h $(( (TOTAL_ELAPSED % 3600) / 60 ))m $(( TOTAL_ELAPSED % 60 ))s"
echo "============================================================"
echo ""
echo "Output:"
echo "  models/pretrained_iitj/   — pretrained checkpoint"
echo "  models/finetuned_iitj/    — LoRA adapter"
echo "  models/training_logs.json — loss history"
echo ""
echo "To use the fine-tuned model in the backend:"
echo "  Add to backend/.env:"
echo "    USE_FINETUNED_MODEL=true"
echo ""
echo "To test inference:"
echo "  python finetune_inference.py --query 'What is the B.Tech fee at IIT Jammu?'"
echo ""
