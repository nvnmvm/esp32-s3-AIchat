#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
LATEST_VERSION="v3.0.1-phase3-asr-quality"

need_env() {
  if [ ! -f "$ENV_FILE" ]; then
    echo ".env not found: $ENV_FILE" >&2
    echo "Run deploy.sh first." >&2
    exit 1
  fi
}

load_env() {
  need_env
  # shellcheck disable=SC1090
  . "$ENV_FILE"
}

random_token() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  else
    date +%s%N | sha256sum | awk '{print $1}'
  fi
}

set_env_value() {
  local key="$1"
  local value="$2"
  local tmp_file
  tmp_file="$(mktemp)"
  if grep -q "^${key}=" "$ENV_FILE"; then
    awk -v key="$key" -v value="$value" '
      BEGIN { updated = 0 }
      index($0, key "=") == 1 { print key "=" value; updated = 1; next }
      { print }
      END { if (!updated) print key "=" value }
    ' "$ENV_FILE" >"$tmp_file"
    mv "$tmp_file" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
    rm -f "$tmp_file"
  fi
}

validate_port() {
  local port="$1"
  case "$port" in
    ''|*[!0-9]*) echo "Port must be a number." >&2; return 1 ;;
  esac
  [ "$port" -ge 1 ] && [ "$port" -le 65535 ]
}

allow_firewall_port() {
  local port="$1"
  if command -v ufw >/dev/null 2>&1 && ufw status | grep -qi '^Status: active'; then
    ufw allow "${port}/tcp"
  fi
  if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="${port}/tcp"
    firewall-cmd --reload
  fi
}

compose_up() {
  cd "$PROJECT_DIR"
  docker compose up -d --build
}

compose_stop() {
  cd "$PROJECT_DIR"
  docker compose stop
}

compose_down() {
  cd "$PROJECT_DIR"
  docker compose down --remove-orphans
}

show_launch_help() {
  cat <<EOF

Quick management:

  cd $PROJECT_DIR
  sudo bash manage.sh

Logs:

  cd $PROJECT_DIR
  docker compose logs -f

EOF
}

show_config() {
  load_env
  echo
  echo "Config file: $ENV_FILE"
  echo "APP_VERSION=${APP_VERSION:-unknown}"
  echo "SERVER_PORT=${SERVER_PORT:-8000}"
  echo "WS_TOKEN=${WS_TOKEN:-}"
  echo "LLM_PROVIDER=${LLM_PROVIDER:-auto}"
  echo "MODEL_CONFIG_PATH=${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  echo "ASR_PROVIDER=${ASR_PROVIDER:-auto}"
  echo "ASR_PRIMARY=${ASR_PRIMARY:-configured_asr}"
  echo "ASR_FALLBACK=${ASR_FALLBACK:-vosk}"
  echo "TTS_PROVIDER=${TTS_PROVIDER:-edge}"
  echo "SEND_ASR_TEXT=${SEND_ASR_TEXT:-false}"
  echo "SEND_ANSWER_TEXT=${SEND_ANSWER_TEXT:-true}"
  echo "SESSION_DIR=${SESSION_DIR:-runtime/session}"
  echo "SESSION_RECORDINGS_DIR=${SESSION_RECORDINGS_DIR:-runtime/session/录音}"
  echo "SESSION_TRANSCRIPTS_DIR=${SESSION_TRANSCRIPTS_DIR:-runtime/session/录音转文字}"
  echo "SESSION_ANSWERS_DIR=${SESSION_ANSWERS_DIR:-runtime/session/ai回答的文本}"
  echo "SESSION_AUDIO_REPORT_DIR=${SESSION_AUDIO_REPORT_DIR:-runtime/session/audio_report}"
  echo "SESSION_RETENTION_DAYS=${SESSION_RETENTION_DAYS:-3}"
  echo "VOSK_MODEL_DIR=${VOSK_MODEL_DIR:-runtime/models/vosk-model-small-cn-0.22}"
  echo "DASHSCOPE_ASR_MODEL=${DASHSCOPE_ASR_MODEL:-qwen3-asr-flash}"
  echo "EDGE_TTS_VOICE=${EDGE_TTS_VOICE:-zh-CN-XiaoxiaoNeural}"
  echo "LOG_LEVEL=${LOG_LEVEL:-INFO}"
  echo "LOG_TO_FILE=${LOG_TO_FILE:-true}"
  echo "LOG_RETENTION_DAYS=${LOG_RETENTION_DAYS:-7}"
  echo "LOG_DIR=${LOG_DIR:-runtime/logs}"
  echo
  model_list || true
  echo
}

change_port() {
  local port
  read -r -p "New WebSocket port: " port
  validate_port "$port" || exit 1
  set_env_value SERVER_PORT "$port"
  allow_firewall_port "$port"
  compose_up
  echo "Port updated to ${port}."
  echo "Also open TCP ${port} in your cloud provider security group."
}

change_token() {
  local mode token
  echo "1) Random token"
  echo "2) Custom token"
  read -r -p "Select [1]: " mode
  mode="${mode:-1}"
  if [ "$mode" = "2" ]; then
    read -r -p "New WebSocket token: " token
    [ -n "$token" ] || { echo "Token cannot be empty." >&2; exit 1; }
  else
    token="$(random_token)"
  fi
  set_env_value WS_TOKEN "$token"
  compose_up
  echo "Token updated."
  echo "Set ESP32 WS_TOKEN to: $token"
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

model_config_file() {
  local path="${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  case "$path" in
    /*) printf '%s' "$path" ;;
    *) printf '%s/%s' "$PROJECT_DIR" "$path" ;;
  esac
}

run_model_cli() {
  local py
  py="$(python_bin)" || {
    echo "python3 is not available." >&2
    return 1
  }
  "$py" "$PROJECT_DIR/scripts/model_config_cli.py" --config "$(model_config_file)" "$@"
}

model_list() {
  load_env
  run_model_cli list
}

add_llm_model() {
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
    *) echo "Unknown brand." >&2; return ;;
  esac
  read -r -p "API key: " api_key
  [ -n "$api_key" ] || { echo "API key cannot be empty." >&2; return; }
  read -r -p "Model name [${default_model}]: " model
  model="${model:-$default_model}"
  [ -n "$model" ] || { echo "Model name cannot be empty." >&2; return; }
  run_model_cli add-llm --brand "$brand" --base-url "$base_url" --api-key "$api_key" --model "$model" --activate >/dev/null
  set_env_value LLM_PROVIDER "auto"
  set_env_value MODEL_CONFIG_PATH "${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  compose_up
  echo "Added and activated LLM model: ${brand}/${model}"
}

add_asr_model() {
  local choice brand provider base_http_api_url base_url default_model model api_key language
  echo
  echo "Choose ASR source:"
  echo "1) Qwen DashScope ASR"
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
    *) echo "Unknown ASR source." >&2; return ;;
  esac
  read -r -p "API key: " api_key
  [ -n "$api_key" ] || { echo "API key cannot be empty." >&2; return; }
  read -r -p "Model name [${default_model}]: " model
  model="${model:-$default_model}"
  [ -n "$model" ] || { echo "Model name cannot be empty." >&2; return; }
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
  set_env_value ASR_PROVIDER "auto"
  set_env_value ASR_PRIMARY "configured_asr"
  set_env_value ASR_FALLBACK "vosk"
  set_env_value MODEL_CONFIG_PATH "${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  compose_up
  echo "Added and activated ASR model: ${brand}/${model}"
}

deployed_model_menu() {
  local kind model_id action
  while true; do
    echo
    model_list || true
    echo
    echo "1) Select LLM by ID"
    echo "2) Select ASR by ID"
    echo "0) Back"
    read -r -p "Select: " kind
    case "$kind" in
      1) kind="llm" ;;
      2) kind="asr" ;;
      0) return ;;
      *) echo "Unknown option." >&2; continue ;;
    esac
    read -r -p "Model ID: " model_id
    [ -n "$model_id" ] || continue
    echo "1) Switch to this model"
    echo "2) Delete this model"
    echo "0) Back"
    read -r -p "Select: " action
    case "$action" in
      1)
        run_model_cli switch "$kind" "$model_id"
        if [ "$kind" = "llm" ]; then
          set_env_value LLM_PROVIDER "auto"
        else
          set_env_value ASR_PROVIDER "auto"
          set_env_value ASR_PRIMARY "configured_asr"
        fi
        compose_up
        ;;
      2)
        run_model_cli delete "$kind" "$model_id"
        compose_up
        ;;
      0) ;;
      *) echo "Unknown option." >&2 ;;
    esac
  done
}

large_model_menu() {
  while true; do
    load_env
    echo
    echo "Large Model Brands"
    echo "1) Deployed models"
    echo "2) Add LLM dialogue model"
    echo "3) Add ASR transcription model"
    echo "0) Back"
    read -r -p "Select: " choice
    case "$choice" in
      1) deployed_model_menu ;;
      2) add_llm_model ;;
      3) add_asr_model ;;
      0) return ;;
      *) echo "Unknown option." >&2 ;;
    esac
  done
}

show_status() {
  load_env
  cd "$PROJECT_DIR"
  docker compose ps
  echo
  curl -fsS "http://127.0.0.1:${SERVER_PORT:-8000}/health" || true
  echo
}

show_recent_logs() {
  cd "$PROJECT_DIR"
  docker compose logs --tail=120
}

follow_logs() {
  cd "$PROJECT_DIR"
  docker compose logs -f
}

show_file_logs() {
  local log_dir="${LOG_DIR:-runtime/logs}"
  if [ -f "$PROJECT_DIR/$log_dir/cloud.log" ]; then
    tail -n 120 "$PROJECT_DIR/$log_dir/cloud.log"
  else
    echo "File log not found: $PROJECT_DIR/$log_dir/cloud.log"
  fi
}

set_log_retention_days() {
  local days="$1"
  set_env_value LOG_RETENTION_DAYS "$days"
  set_env_value LOG_TO_FILE "true"
  compose_up
  echo "Log retention updated to ${days} day(s)."
}

logs_menu() {
  while true; do
    load_env
    echo
    echo "Logs"
    echo "File logging: ${LOG_TO_FILE:-true}"
    echo "Retention: ${LOG_RETENTION_DAYS:-7} day(s)"
    echo "Log dir: ${LOG_DIR:-runtime/logs}"
    echo "1) Keep logs 7 days"
    echo "2) Keep logs 3 days"
    echo "3) Keep logs 1 day"
    echo "4) Follow realtime logs"
    echo "5) Show recent Docker logs"
    echo "6) Show recent file logs"
    echo "7) Disable file logs"
    echo "8) Enable file logs"
    echo "0) Back"
    read -r -p "Select: " choice
    case "$choice" in
      1) set_log_retention_days 7 ;;
      2) set_log_retention_days 3 ;;
      3) set_log_retention_days 1 ;;
      4) follow_logs ;;
      5) show_recent_logs ;;
      6) show_file_logs ;;
      7) set_env_value LOG_TO_FILE "false"; compose_up ;;
      8) set_env_value LOG_TO_FILE "true"; compose_up ;;
      0) return ;;
      *) echo "Unknown option." >&2 ;;
    esac
  done
}

set_session_retention_days() {
  local days="$1"
  set_env_value SESSION_RETENTION_DAYS "$days"
  compose_up
  echo "Session file retention updated to ${days} day(s)."
}

session_menu() {
  while true; do
    load_env
    echo
    echo "Session Files"
    echo "Root: ${SESSION_DIR:-runtime/session}"
    echo "Recordings: ${SESSION_RECORDINGS_DIR:-runtime/session/录音}"
    echo "Transcripts: ${SESSION_TRANSCRIPTS_DIR:-runtime/session/录音转文字}"
    echo "Answers: ${SESSION_ANSWERS_DIR:-runtime/session/ai回答的文本}"
    echo "Audio reports: ${SESSION_AUDIO_REPORT_DIR:-runtime/session/audio_report}"
    echo "Retention: ${SESSION_RETENTION_DAYS:-3} day(s)"
    echo "1) Keep 1 day"
    echo "2) Keep 3 days"
    echo "3) Keep 7 days"
    echo "4) Keep 30 days"
    echo "0) Back"
    read -r -p "Select: " choice
    case "$choice" in
      1) set_session_retention_days 1 ;;
      2) set_session_retention_days 3 ;;
      3) set_session_retention_days 7 ;;
      4) set_session_retention_days 30 ;;
      0) return ;;
      *) echo "Unknown option." >&2 ;;
    esac
  done
}

run_doctor() {
  bash "$PROJECT_DIR/scripts/doctor.sh"
}

can_preserve_update() {
  local version="${APP_VERSION:-}"
  case "$version" in
    v2.0.1-phase2|v2.0.2-phase2|v2.1.*|v3.*) return 0 ;;
    *) return 1 ;;
  esac
}

git_update_code() {
  if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo "This install is not a git checkout. Re-run install.sh for updates." >&2
    exit 1
  fi
  git -C "$PROJECT_DIR" fetch --tags origin
  git -C "$PROJECT_DIR" checkout main
  git -C "$PROJECT_DIR" pull --ff-only origin main
}

update_preserve_data() {
  load_env
  if ! can_preserve_update; then
    echo "Current version ${APP_VERSION:-unknown} cannot be updated in place safely."
    return
  fi
  echo "Preserving .env and runtime/ while updating to latest main."
  compose_down || true
  git_update_code
  set_env_value APP_VERSION "$LATEST_VERSION"
  compose_up
  echo "Updated with data preserved."
}

update_clean_data() {
  load_env
  cat <<EOF

This will update code and remove runtime data:
  $PROJECT_DIR/runtime

.env will be kept so WebSocket token, port, and model settings remain configured.
EOF
  read -r -p "Type UPDATE to continue: " confirm
  [ "$confirm" = "UPDATE" ] || { echo "Cancelled."; return; }
  compose_down || true
  rm -rf -- "$PROJECT_DIR/runtime"
  git_update_code
  set_env_value APP_VERSION "$LATEST_VERSION"
  compose_up
  echo "Updated after removing runtime data."
}

uninstall_service() {
  echo "This will uninstall the WebSocket cloud service from: $PROJECT_DIR"
  read -r -p "Type UNINSTALL to continue: " confirm
  [ "$confirm" = "UNINSTALL" ] || { echo "Cancelled."; return; }
  if [ "$(id -u)" -ne 0 ]; then
    echo "Please run: sudo bash $PROJECT_DIR/uninstall.sh --dir $PROJECT_DIR" >&2
    return
  fi
  bash "$PROJECT_DIR/uninstall.sh" --dir "$PROJECT_DIR"
  exit 0
}

menu() {
  show_launch_help
  while true; do
    load_env
    echo
    echo "ESP32-S3 AI Chat Cloud Management"
    echo "1) Show config"
    echo "2) Change WebSocket port"
    echo "3) Change WebSocket token"
    echo "4) Large model brands"
    echo "5) Start / rebuild WebSocket service"
    echo "6) Stop WebSocket service"
    echo "7) Restart WebSocket service"
    echo "8) Show status"
    echo "9) Logs"
    echo "10) Run doctor"
    echo "11) Update, preserve data"
    echo "12) Update, remove runtime data"
    echo "13) Uninstall WebSocket service"
    echo "14) Session file retention"
    echo "0) Exit"
    read -r -p "Select: " choice
    case "$choice" in
      1) show_config ;;
      2) change_port ;;
      3) change_token ;;
      4) large_model_menu ;;
      5) compose_up ;;
      6) compose_stop ;;
      7) compose_down; compose_up ;;
      8) show_status ;;
      9) logs_menu ;;
      10) run_doctor ;;
      11) update_preserve_data ;;
      12) update_clean_data ;;
      13) uninstall_service ;;
      14) session_menu ;;
      0) exit 0 ;;
      *) echo "Unknown option." >&2 ;;
    esac
  done
}

menu
