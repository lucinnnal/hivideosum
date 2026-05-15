#!/usr/bin/env bash
# Launch vLLM with the fine-tuned LoRA adapter.
# Adapter directory must contain adapter_config.json + adapter_model.safetensors
# under ./adapters/hivideosum/ (mounted into the container at /adapters).

set -euo pipefail

BASE_MODEL="${BASE_MODEL:-google/gemma-4-E4B-it}"
ADAPTER_PATH="${ADAPTER_PATH:-/adapters/hivideosum}"
MAX_LEN="${MAX_LEN:-20000}"
PORT="${PORT:-8001}"

exec vllm serve "${BASE_MODEL}" \
  --enable-lora \
  --lora-modules "hivideosum=${ADAPTER_PATH}" \
  --max-model-len "${MAX_LEN}" \
  --port "${PORT}"
