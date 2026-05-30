#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
LATEST_VERSION="v2.1.0-phase2-complete"

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
    ''|*[!0-9]*)
      echo "Port must be a number." >&2
      return 1
      ;;
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

快捷管理界面调出方法：

  cd $PROJECT_DIR
  sudo bash manage.sh

常用日志命令：

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
  if [ -n "${AI_API_KEY:-}" ]; then
    echo "AI_API_KEY=<configured>"
  else
    echo "AI_API_KEY=<empty>"
  fi
  echo "LLM_PROVIDER=${LLM_PROVIDER:-phase2}"
  echo "ASR_PROVIDER=${ASR_PROVIDER:-phase2}"
  echo "TTS_PROVIDER=${TTS_PROVIDER:-tone}"
  echo "SAVE_DEBUG_WAV=${SAVE_DEBUG_WAV:-false}"
  echo "CONVERSATION_DIR=${CONVERSATION_DIR:-runtime/conversations}"
  echo "DEBUG_AUDIO_DIR=${DEBUG_AUDIO_DIR:-runtime/audio}"
  echo "LOG_LEVEL=${LOG_LEVEL:-INFO}"
  echo "LOG_PAYLOADS=${LOG_PAYLOADS:-false}"
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
    if [ -z "$token" ]; then
      echo "Token cannot be empty." >&2
      exit 1
    fi
  else
    token="$(random_token)"
  fi

  set_env_value WS_TOKEN "$token"
  compose_up
  echo "Token updated."
  echo "Set ESP32 WS_TOKEN to: $token"
}

change_ai_key() {
  local api_key

  read -r -p "New AI API key, empty to clear: " api_key
  set_env_value AI_API_KEY "$api_key"
  set_env_value DEEPSEEK_API_KEY "$api_key"
  if [ -n "$api_key" ]; then
    set_env_value LLM_PROVIDER "deepseek"
  else
    set_env_value LLM_PROVIDER "phase2"
  fi
  compose_up
  echo "AI API key updated."
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

run_doctor() {
  bash "$PROJECT_DIR/scripts/doctor.sh"
}

can_preserve_update() {
  local version="${APP_VERSION:-}"
  case "$version" in
    v2.0.1-phase2|v2.0.2-phase2|v2.1.*)
      return 0
      ;;
    *)
      return 1
      ;;
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
    cat <<EOF

当前版本：${APP_VERSION:-unknown}
目标版本：$LATEST_VERSION

此版本跨度不能直接保留数据更新。建议：
1. 先自行备份 $PROJECT_DIR/.env 和 $PROJECT_DIR/runtime
2. 选择“不保留运行数据更新”
3. 或先更新到兼容的中间版本后再更新

EOF
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

.env will be kept so WebSocket token, port, and AI key remain configured.
EOF
  read -r -p "Type UPDATE to continue: " confirm
  if [ "$confirm" != "UPDATE" ]; then
    echo "Cancelled."
    return
  fi

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
  if [ "$confirm" != "UNINSTALL" ]; then
    echo "Cancelled."
    return
  fi

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
    echo "4) Change AI API key"
    echo "5) Start / rebuild WebSocket service"
    echo "6) Stop WebSocket service"
    echo "7) Restart WebSocket service"
    echo "8) Show status"
    echo "9) Show recent logs"
    echo "10) Follow realtime logs"
    echo "11) Run doctor"
    echo "12) Update, preserve data"
    echo "13) Update, remove runtime data"
    echo "14) Uninstall WebSocket service"
    echo "0) Exit"
    read -r -p "Select: " choice

    case "$choice" in
      1) show_config ;;
      2) change_port ;;
      3) change_token ;;
      4) change_ai_key ;;
      5) compose_up ;;
      6) compose_stop ;;
      7) compose_down; compose_up ;;
      8) show_status ;;
      9) show_recent_logs ;;
      10) follow_logs ;;
      11) run_doctor ;;
      12) update_preserve_data ;;
      13) update_clean_data ;;
      14) uninstall_service ;;
      0) exit 0 ;;
      *) echo "Unknown option." >&2 ;;
    esac
  done
}

menu
