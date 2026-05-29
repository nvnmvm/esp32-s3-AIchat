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

read_token() {
  if [ -n "${WS_TOKEN:-}" ]; then
    echo "Choose WebSocket token mode:" >&2
    echo "1) Keep existing token" >&2
    echo "2) Random token" >&2
    echo "3) Custom token" >&2
    read -r -p "Select [1]: " mode
    mode="${mode:-1}"

    case "$mode" in
      1)
        printf '%s' "$WS_TOKEN"
        return
        ;;
      2)
        token="$(random_token)"
        ;;
      3)
        read -r -p "Enter custom WebSocket token: " token
        ;;
      *)
        echo "Unknown token mode." >&2
        exit 1
        ;;
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
    *[[:space:]]*)
      echo "Token cannot contain whitespace." >&2
      exit 1
      ;;
  esac

  printf '%s' "$token"
}

load_existing_env() {
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$ENV_FILE"
  fi
}

read_port() {
  local default_port="${SERVER_PORT:-8000}"
  local port

  read -r -p "Enter WebSocket server port [${default_port}]: " port
  port="${port:-$default_port}"

  case "$port" in
    ''|*[!0-9]*)
      echo "Port must be a number." >&2
      exit 1
      ;;
  esac

  if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
    echo "Port must be between 1 and 65535." >&2
    exit 1
  fi

  printf '%s' "$port"
}

read_ai_api_key() {
  local api_key

  read -r -p "Enter AI API key [optional, press Enter to skip]: " api_key
  if [ -z "$api_key" ]; then
    api_key="${AI_API_KEY:-}"
  fi

  printf '%s' "$api_key"
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

  if command -v ufw >/dev/null 2>&1; then
    if ufw status | grep -qi '^Status: active'; then
      ufw allow "${port}/tcp"
      echo "ufw is active; allowed TCP ${port}."
      return
    fi
    echo "ufw is installed but inactive."
  fi

  if command -v firewall-cmd >/dev/null 2>&1; then
    if firewall-cmd --state >/dev/null 2>&1; then
      firewall-cmd --permanent --add-port="${port}/tcp"
      firewall-cmd --reload
      echo "firewalld is active; allowed TCP ${port}."
      return
    fi
    echo "firewalld is installed but inactive."
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
MAX_WS_MESSAGE_BYTES=1048576
APP_VERSION=v1.0.0-phase1
EOF

  cd "$PROJECT_DIR"
  docker compose up -d --build
  check_port_mapping "$server_port"

  public_ip="$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}' || true)"
  public_ip="${public_ip:-YOUR_VPS_PUBLIC_IP}"

  echo
  echo "Deployment complete."
  echo "WebSocket URL: ws://${public_ip}:${server_port}/ws"
  echo "WebSocket token: $token"
  echo "Set ESP32 WS_HOST to: $public_ip"
  echo "Set ESP32 WS_PORT to: $server_port"
  echo "Set ESP32 WS_TOKEN to: $token"
  echo "Cloud config file: $ENV_FILE"
  echo "Management menu: sudo bash $PROJECT_DIR/manage.sh"
  echo "If this is a cloud VPS, open TCP ${server_port} in the provider security group."
}

main "$@"
