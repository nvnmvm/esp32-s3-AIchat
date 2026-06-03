#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

bash -n manage.sh deploy.sh scripts/menu/*.sh scripts/menu/lang/*.sh

py_bin="python3"
if ! command -v "$py_bin" >/dev/null 2>&1; then
  py_bin="python"
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
config="$tmp_dir/models.json"

"$py_bin" scripts/model_config_cli.py --config "$config" add-llm \
  --brand deepseek \
  --name "smoke-llm" \
  --remark "smoke LLM" \
  --base-url "https://api.deepseek.com" \
  --api-key "sk-smoke-llm-1234567890" \
  --model "deepseek-chat" \
  --activate >/dev/null

"$py_bin" scripts/model_config_cli.py --config "$config" add-asr \
  --brand qwen \
  --provider qwen_dashscope \
  --name "smoke-asr" \
  --remark "smoke ASR" \
  --base-http-api-url "https://dashscope.aliyuncs.com/api/v1" \
  --api-key "sk-smoke-asr-1234567890" \
  --model "qwen3-asr-flash" \
  --language zh \
  --enable-itn \
  --activate >/dev/null

list_output="$("$py_bin" scripts/model_config_cli.py --config "$config" list)"
printf '%s\n' "$list_output" | grep -q "smoke LLM"
if printf '%s\n' "$list_output" | grep -q "sk-smoke"; then
  echo "Secret masking failed." >&2
  exit 1
fi

echo "manage/menu smoke checks passed."
