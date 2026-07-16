#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
MENU_DIR="$PROJECT_DIR/scripts/menu"

# shellcheck source=scripts/menu/env.sh
. "$MENU_DIR/env.sh"
# shellcheck source=scripts/menu/ui.sh
. "$MENU_DIR/ui.sh"
# shellcheck source=scripts/menu/i18n.sh
. "$MENU_DIR/i18n.sh"
# shellcheck source=scripts/menu/docker.sh
. "$MENU_DIR/docker.sh"
# shellcheck source=scripts/menu/models.sh
. "$MENU_DIR/models.sh"

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
  validate_port "$port" || { echo "Port must be between 1 and 65535." >&2; exit 1; }
  printf '%s' "$port"
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

read_model_wizard_choice() {
  local answer
  echo >&2
  echo "Model API configuration is optional." >&2
  echo "You can start the service first, then run manage.sh > Models & Voice > First-run setup wizard." >&2
  read -r -p "Open the first-run ASR/LLM setup wizard now? [y/N]: " answer
  case "$answer" in
    y|Y) printf '%s' "true" ;;
    *) printf '%s' "false" ;;
  esac
}

print_version_summary() {
  local git_version="unknown"
  local health_version=""
  local body
  if command -v git >/dev/null 2>&1 && [ -d "$PROJECT_DIR/.git" ]; then
    git_version="$(git -C "$PROJECT_DIR" describe --tags --always --dirty 2>/dev/null || printf 'unknown')"
  fi
  body="$(curl -fsS "http://127.0.0.1:${server_port}/health" 2>/dev/null || true)"
  if [ -n "$body" ] && command -v python3 >/dev/null 2>&1; then
    health_version="$(printf '%s' "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("version",""))' 2>/dev/null || true)"
  fi
  echo "=== Cloud version ==="
  echo "Expected code version: v4.1.0-streaming-pipeline"
  echo "Git code version: ${git_version}"
  if [ -n "$health_version" ]; then
    echo "Running /health version: ${health_version}"
  else
    echo "Running /health version: unavailable; check logs if the container is still starting"
  fi
  echo
}

write_env_file() {
  local server_port="$1"
  local token="$2"
  local ai_api_key="${AI_API_KEY:-${DEEPSEEK_API_KEY:-}}"
  cat >"$ENV_FILE" <<EOF
SERVER_PORT=$server_port
WS_TOKEN=$token
ALLOW_EMPTY_TOKEN=false
MENU_LANG=zh_CN
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
VAD_SILENCE_RMS=450
VAD_SILENCE_CHUNKS=12
VAD_PREROLL_MS=300
VAD_POSTROLL_MS=240
MOCK_TTS_DURATION_MS=900
MOCK_TTS_TONE_HZ=660
ASR_PROVIDER=auto
ASR_STRATEGY=cloud_first
ASR_PRIMARY=configured_asr
ASR_FALLBACK=vosk
ASR_DEFAULT_VENDOR=qwen
ASR_CONTEXT=小一小一,ESP32-S3,高数,数据结构,计算机科学与技术
ASR_LANGUAGE=zh
ASR_TIMEOUT_SECONDS=60
DASHSCOPE_API_KEY=
DASHSCOPE_ASR_MODEL=qwen3-asr-flash
DASHSCOPE_BASE_HTTP_API_URL=https://dashscope.aliyuncs.com/api/v1
QWEN_REALTIME_ENABLED=true
QWEN_REALTIME_WORKSPACE_ID=
QWEN_REALTIME_REGION=cn-beijing
QWEN_REALTIME_WS_URL=
QWEN_REALTIME_MODEL=qwen3-asr-flash-realtime
QWEN_REALTIME_VAD_SILENCE_MS=400
QWEN_REALTIME_CONNECT_TIMEOUT_SECONDS=10
QWEN_REALTIME_FINISH_TIMEOUT_SECONDS=8
LLM_PROVIDER=auto
LLM_DEFAULT_VENDOR=deepseek
TTS_PROVIDER=edge
DEEPSEEK_API_KEY=$ai_api_key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
AI_API_BASE=https://api.deepseek.com
AI_MODEL=deepseek-v4-flash
LLM_TIMEOUT_SECONDS=30
LLM_MAX_TOKENS=512
LLM_STREAMING_ENABLED=true
LLM_DISABLE_THINKING=true
LLM_SENTENCE_MAX_CHARS=80
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
CONVERSATION_MAX_TURNS=5
VOSK_MODEL_DIR=runtime/models/vosk-model-small-cn-0.22
VOSK_MODEL_URL=https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
VOSK_AUTO_DOWNLOAD=true
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
FFMPEG_BIN=ffmpeg
ANSWER_MAX_CHARS=800
TTS_MAX_CHARS=500
TTS_PCM_CHUNK_MS=80
TTS_SENTENCE_QUEUE_SIZE=4
SEND_ASR_TEXT=false
SEND_ANSWER_TEXT=true
APP_VERSION=v4.1.0-streaming-pipeline
EOF
}

main() {
  require_docker
  load_existing_env
  token="$(read_token)"
  server_port="$(read_port)"
  configure_models_now="$(read_model_wizard_choice)"
  check_firewall "$server_port"
  write_env_file "$server_port" "$token"

  load_env
  load_language

  cd "$PROJECT_DIR"
  docker compose up -d --build
  if [ "$configure_models_now" = "true" ]; then
    first_run_model_wizard || true
  fi
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
  echo "Phase 3.0.3 audio format: PCM s16le, 16000 Hz, mono"
  echo
  echo "Next model step: sudo bash $PROJECT_DIR/manage.sh > Models & Voice > First-run setup wizard"
  echo "If you skip model APIs, the cloud still starts for ESP32 recording, OLED and speaker loopback tests."
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
