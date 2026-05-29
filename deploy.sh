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
  echo "Choose WebSocket token mode:" >&2
  echo "1) Random token" >&2
  echo "2) Custom token" >&2
  read -r -p "Select [1]: " mode
  mode="${mode:-1}"

  if [ "$mode" = "2" ]; then
    read -r -p "Enter custom WebSocket token: " token
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
  else
    token="$(random_token)"
  fi

  printf '%s' "$token"
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

  token="$(read_token)"
  server_port="${SERVER_PORT:-8000}"
  ai_api_key="${AI_API_KEY:-replace-in-next-phase}"

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
}

main "$@"
