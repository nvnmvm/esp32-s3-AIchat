#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

random_token() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  else
    tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48
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

main() {
  require_docker

  token="$(read_token)"
  server_port="${SERVER_PORT:-8000}"
  ai_api_key="${AI_API_KEY:-replace-in-next-phase}"

  cat >"$ENV_FILE" <<EOF
SERVER_PORT=$server_port
WS_TOKEN=$token
ALLOW_EMPTY_TOKEN=false
AI_API_KEY=$ai_api_key
LOG_LEVEL=INFO
EOF

  cd "$PROJECT_DIR"
  docker compose up -d --build

  public_ip="$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"

  echo
  echo "Deployment complete."
  echo "WebSocket URL: ws://${public_ip}:${server_port}/ws"
  echo "WebSocket token: $token"
  echo "Set ESP32 WS_HOST to: $public_ip"
  echo "Set ESP32 WS_PORT to: $server_port"
  echo "Set ESP32 WS_TOKEN to: $token"
}

main "$@"
