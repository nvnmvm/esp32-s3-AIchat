#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

random_token() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  else
    date +%s%N | sha256sum | awk '{print $1}'
  fi
}

load_existing_env() {
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$ENV_FILE"
  fi
}

read_token() {
  local mode token
  if [ -n "${WS_TOKEN:-}" ]; then
    echo "Choose WebSocket token mode:" >&2
    echo "1) Keep existing token" >&2
    echo "2) Random token" >&2
    echo "3) Custom token" >&2
    read -r -p "Select [1]: " mode
    mode="${mode:-1}"
    case "$mode" in
      1) printf '%s' "$WS_TOKEN"; return ;;
      2) token="$(random_token)" ;;
      3) read -r -p "Enter custom WebSocket token: " token ;;
      *) echo "Unknown token mode." >&2; exit 1 ;;
    esac
  else
    echo "Choose WebSocket token mode:" >&2
    echo "1) Random token" >&2
    echo "2) Custom token" >&2
    read -r -p "Select [1]: " mode
    mode="${mode:-1}"
    if [ "$mode" = "2" ]; then
      read -r -p "Enter custom WebSocket token: " token
    else
      token="$(random_token)"
    fi
  fi

  if [ -z "$token" ]; then
    echo "Token cannot be empty." >&2
    exit 1
  fi
  case "$token" in
    *[[:space:]]*) echo "Token cannot contain whitespace." >&2; exit 1 ;;
  esac
  printf '%s' "$token"
}

read_port() {
  local default_port="${SERVER_PORT:-8000}"
  local port
  read -r -p "Enter WebSocket server port [${default_port}]: " port
  port="${port:-$default_port}"
  case "$port" in
    ''|*[!0-9]*) echo "Port must be a number." >&2; exit 1 ;;
  esac
  if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
    echo "Port must be between 1 and 65535." >&2
    exit 1
  fi
  printf '%s' "$port"
}

read_ai_api_key() {
  local api_key
  read -r -p "Enter legacy DeepSeek/OpenAI-compatible API key [optional, press Enter to skip]: " api_key
  if [ -z "$api_key" ]; then
    api_key="${AI_API_KEY:-}"
  fi
  printf '%s' "$api_key"
}

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "python3"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s' "python"
    return
  fi
  return 1
}

run_model_cli() {
  local py config_path
  py="$(python_bin)" || {
    echo "python3 is not available; skipped model config setup." >&2
    return 1
  }
  config_path="${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  case "$config_path" in
    /*) ;;
    *) config_path="$PROJECT_DIR/$config_path" ;;
  esac
  "$py" "$PROJECT_DIR/scripts/model_config_cli.py" --config "$config_path" "$@"
}

add_llm_model_interactive() {
  local choice brand base_url default_model model api_key
  echo
  echo "Choose LLM brand:"
  echo "1) DeepSeek"
  echo "2) Qwen / Alibaba Cloud Model Studio"
  echo "3) Doubao / Volcengine Ark"
  echo "4) OpenAI-compatible custom"
  read -r -p "Select [1]: " choice
  choice="${choice:-1}"
  case "$choice" in
    1) brand="deepseek"; base_url="https://api.deepseek.com"; default_model="deepseek-chat" ;;
    2) brand="qwen"; base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"; default_model="qwen-flash" ;;
    3) brand="doubao"; base_url="https://ark.cn-beijing.volces.com/api/v3"; default_model="doubao-1-5-pro-32k-250115" ;;
    4)
      read -r -p "Brand name: " brand
      read -r -p "OpenAI-compatible base URL: " base_url
      default_model=""
      ;;
    *) echo "Unknown brand." >&2; return 1 ;;
  esac
  read -r -p "API key: " api_key
  [ -n "$api_key" ] || { echo "API key cannot be empty." >&2; return 1; }
  read -r -p "Model name [${default_model}]: " model
  model="${model:-$default_model}"
  [ -n "$model" ] || { echo "Model name cannot be empty." >&2; return 1; }
  run_model_cli add-llm --brand "$brand" --base-url "$base_url" --api-key "$api_key" --model "$model" --activate >/dev/null
  echo "Added and activated LLM model: ${brand}/${model}"
}

add_asr_model_interactive() {
  local choice brand provider base_http_api_url base_url default_model model api_key language
  echo
  echo "Choose ASR model source:"
  echo "1) Qwen DashScope ASR (recommended for 3.0.1)"
  echo "2) OpenAI-compatible multimodal model"
  read -r -p "Select [1]: " choice
  choice="${choice:-1}"
  case "$choice" in
    1)
      brand="qwen"
      provider="qwen_dashscope"
      base_http_api_url="https://dashscope.aliyuncs.com/api/v1"
      base_url=""
      default_model="qwen3-asr-flash"
      ;;
    2)
      read -r -p "Brand name: " brand
      provider="openai_multimodal"
      base_http_api_url=""
      read -r -p "OpenAI-compatible base URL: " base_url
      default_model=""
      ;;
    *) echo "Unknown ASR source." >&2; return 1 ;;
  esac
  read -r -p "API key: " api_key
  [ -n "$api_key" ] || { echo "API key cannot be empty." >&2; return 1; }
  read -r -p "Model name [${default_model}]: " model
  model="${model:-$default_model}"
  [ -n "$model" ] || { echo "Model name cannot be empty." >&2; return 1; }
  read -r -p "Language hint [zh]: " language
  language="${language:-zh}"
  run_model_cli add-asr \
    --brand "$brand" \
    --provider "$provider" \
    --base-url "$base_url" \
    --base-http-api-url "$base_http_api_url" \
    --api-key "$api_key" \
    --model "$model" \
    --language "$language" \
    --enable-itn \
    --activate >/dev/null
  echo "Added and activated ASR model: ${brand}/${model}"
}

configure_models_interactive() {
  local mode count index purpose
  echo
  echo "Model configuration is stored in runtime/config/models.json."
  echo "Secrets in that file are under runtime/ and are not committed to git."
  echo "0) Skip for now"
  echo "1) Add one model"
  echo "2) Add multiple models"
  read -r -p "Select [1]: " mode
  mode="${mode:-1}"
  case "$mode" in
    0) return ;;
    1) count=1 ;;
    2)
      read -r -p "How many models do you want to add? " count
      case "$count" in ''|*[!0-9]*) echo "Count must be a number." >&2; return 1 ;; esac
      ;;
    *) echo "Unknown option." >&2; return 1 ;;
  esac
  index=1
  while [ "$index" -le "$count" ]; do
    echo
    echo "Model ${index}/${count}:"
    echo "1) LLM dialogue model"
    echo "2) ASR transcription model"
    read -r -p "Purpose [1]: " purpose
    purpose="${purpose:-1}"
    case "$purpose" in
      1) add_llm_model_interactive ;;
      2) add_asr_model_interactive ;;
      *) echo "Unknown purpose." >&2; return 1 ;;
    esac
    index=$((index + 1))
  done
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed. Run install.sh on a fresh VPS, or install Docker first." >&2
    exit 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose plugin is not installed." >&2
    exit 1
  fi
}

check_firewall() {
  local port="$1"
  echo "Checking local firewall for TCP port ${port}..."
  if command -v ufw >/dev/null 2>&1 && ufw status | grep -qi '^Status: active'; then
    ufw allow "${port}/tcp"
    echo "ufw is active; allowed TCP ${port}."
    return
  fi
  if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="${port}/tcp"
    firewall-cmd --reload
    echo "firewalld is active; allowed TCP ${port}."
    return
  fi
  echo "No active local firewall was detected by this script."
  echo "If this is a cloud VPS, still open TCP ${port} in the provider security group."
}

check_port_mapping() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    if ss -lnt | awk '{print $4}' | grep -Eq "(^|:)${port}$"; then
      echo "TCP ${port} is listening locally."
    else
      echo "Warning: TCP ${port} is not visible in local listening sockets yet." >&2
    fi
  fi
}

print_version_summary() {
  local git_version="unknown"
  local health_json=""
  local health_version=""
  if command -v git >/dev/null 2>&1 && [ -d "$PROJECT_DIR/.git" ]; then
    git_version="$(git -C "$PROJECT_DIR" describe --tags --always --dirty 2>/dev/null || printf 'unknown')"
  fi
  health_json="$(curl -fsS "http://127.0.0.1:${server_port}/health" 2>/dev/null || true)"
  if [ -n "$health_json" ]; then
    health_version="$(printf '%s' "$health_json" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')"
  fi
  echo "=== Cloud version ==="
  echo "Configured APP_VERSION: v3.0.1-phase3-asr-quality"
  echo "Git code version: ${git_version}"
  if [ -n "$health_version" ]; then
    echo "Running /health version: ${health_version}"
  else
    echo "Running /health version: unavailable; check logs if the container is still starting"
  fi
  echo
}

main() {
  require_docker
  load_existing_env
  token="$(read_token)"
  server_port="$(read_port)"
  ai_api_key="$(read_ai_api_key)"
  check_firewall "$server_port"

  cat >"$ENV_FILE" <<EOF
SERVER_PORT=$server_port
WS_TOKEN=$token
ALLOW_EMPTY_TOKEN=false
AI_API_KEY=$ai_api_key
LOG_LEVEL=INFO
LOG_PAYLOADS=false
LOG_TO_FILE=true
LOG_RETENTION_DAYS=7
LOG_DIR=runtime/logs
MAX_WS_MESSAGE_BYTES=1048576
MAX_RECORDING_BYTES=384000
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_SAMPLE_WIDTH_BYTES=2
AUDIO_CHUNK_MS=40
VAD_MIN_RECORDING_MS=900
VAD_MAX_RECORDING_MS=12000
VAD_MIN_RECORDING_BYTES=32000
VAD_SILENCE_RMS=450
VAD_SILENCE_CHUNKS=12
VAD_PREROLL_MS=300
VAD_POSTROLL_MS=240
MOCK_TTS_DURATION_MS=900
MOCK_TTS_TONE_HZ=660
ASR_PROVIDER=auto
ASR_PRIMARY=configured_asr
ASR_FALLBACK=vosk
ASR_CONTEXT=小一小一,ESP32-S3,高数,数据结构,计算机科学与技术
ASR_LANGUAGE=zh
ASR_TIMEOUT_SECONDS=60
DASHSCOPE_API_KEY=
DASHSCOPE_ASR_MODEL=qwen3-asr-flash
DASHSCOPE_BASE_HTTP_API_URL=https://dashscope.aliyuncs.com/api/v1
LLM_PROVIDER=auto
TTS_PROVIDER=edge
DEEPSEEK_API_KEY=$ai_api_key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
AI_API_BASE=https://api.deepseek.com
AI_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=30
MODEL_CONFIG_PATH=runtime/config/models.json
TTS_TIMEOUT_SECONDS=45
SAVE_DEBUG_WAV=false
DEBUG_AUDIO_DIR=runtime/audio
SESSION_DIR=runtime/session
SESSION_RECORDINGS_DIR=runtime/session/录音
SESSION_TRANSCRIPTS_DIR=runtime/session/录音转文字
SESSION_ANSWERS_DIR=runtime/session/ai回答的文本
SESSION_AUDIO_REPORT_DIR=runtime/session/audio_report
SESSION_RETENTION_DAYS=3
CONVERSATION_DIR=runtime/session/录音转文字
VOSK_MODEL_DIR=runtime/models/vosk-model-small-cn-0.22
VOSK_MODEL_URL=https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
VOSK_AUTO_DOWNLOAD=true
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
FFMPEG_BIN=ffmpeg
ANSWER_MAX_CHARS=800
TTS_MAX_CHARS=500
SEND_ASR_TEXT=false
SEND_ANSWER_TEXT=true
APP_VERSION=v3.0.1-phase3-asr-quality
EOF

  configure_models_interactive || true

  cd "$PROJECT_DIR"
  docker compose up -d --build
  check_port_mapping "$server_port"

  public_ip="$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}' || true)"
  public_ip="${public_ip:-YOUR_VPS_PUBLIC_IP}"

  echo
  echo "Deployment complete."
  echo
  print_version_summary
  echo "=== ESP32 firmware config ==="
  echo "WebSocket URL: ws://${public_ip}:${server_port}/ws"
  echo "WebSocket token: $token"
  echo "Set ESP32 WS_HOST to: $public_ip"
  echo "Set ESP32 WS_PORT to: $server_port"
  echo "Set ESP32 WS_TOKEN to: $token"
  echo "Phase 3.0.1 audio format: PCM s16le, 16000 Hz, mono"
  echo
  echo "=== VPS common commands ==="
  echo "Cloud config file: $ENV_FILE"
  echo "Model config file: $PROJECT_DIR/runtime/config/models.json"
  echo "Open management menu: sudo bash $PROJECT_DIR/manage.sh"
  echo "Run health doctor: sudo bash $PROJECT_DIR/scripts/doctor.sh"
  echo "View service status: cd $PROJECT_DIR && docker compose ps"
  echo "View logs: cd $PROJECT_DIR && docker compose logs -f"
  echo "If this is a cloud VPS, open TCP ${server_port} in the provider security group."
}

main "$@"
