#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

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

restart_service() {
  cd "$PROJECT_DIR"
  docker compose up -d --build
}

show_config() {
  load_env
  echo
  echo "Config file: $ENV_FILE"
  echo "SERVER_PORT=${SERVER_PORT:-8000}"
  echo "WS_TOKEN=${WS_TOKEN:-}"
  if [ -n "${AI_API_KEY:-}" ]; then
    echo "AI_API_KEY=<configured>"
  else
    echo "AI_API_KEY=<empty>"
  fi
  echo "LOG_LEVEL=${LOG_LEVEL:-INFO}"
  echo "LOG_PAYLOADS=${LOG_PAYLOADS:-false}"
  echo "MAX_WS_MESSAGE_BYTES=${MAX_WS_MESSAGE_BYTES:-1048576}"
  echo
}

change_port() {
  local port

  read -r -p "New WebSocket port: " port
  validate_port "$port" || exit 1
  set_env_value SERVER_PORT "$port"
  allow_firewall_port "$port"
  restart_service
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
  restart_service
  echo "Token updated."
  echo "Set ESP32 WS_TOKEN to: $token"
}

change_ai_key() {
  local api_key

  read -r -p "New AI API key, empty to clear: " api_key
  set_env_value AI_API_KEY "$api_key"
  restart_service
  echo "AI API key updated."
}

show_status() {
  cd "$PROJECT_DIR"
  docker compose ps
  echo
  curl -fsS "http://127.0.0.1:${SERVER_PORT:-8000}/health" || true
  echo
}

show_logs() {
  cd "$PROJECT_DIR"
  docker compose logs -f
}

run_doctor() {
  bash "$PROJECT_DIR/scripts/doctor.sh"
}

menu() {
  while true; do
    load_env
    echo
    echo "ESP32-S3 AI Chat Cloud Management"
    echo "1) Show config"
    echo "2) Change WebSocket port"
    echo "3) Change WebSocket token"
    echo "4) Change AI API key"
    echo "5) Restart service"
    echo "6) Show status"
    echo "7) Follow logs"
    echo "8) Run doctor"
    echo "0) Exit"
    read -r -p "Select: " choice

    case "$choice" in
      1) show_config ;;
      2) change_port ;;
      3) change_token ;;
      4) change_ai_key ;;
      5) restart_service ;;
      6) show_status ;;
      7) show_logs ;;
      8) run_doctor ;;
      0) exit 0 ;;
      *) echo "Unknown option." >&2 ;;
    esac
  done
}

menu
