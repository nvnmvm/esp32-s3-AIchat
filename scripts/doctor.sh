#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/esp32-ai-voice-cloud}"
PORT="${SERVER_PORT:-8000}"

if [ -f "$PROJECT_DIR/.env" ]; then
  # shellcheck disable=SC1090
  . "$PROJECT_DIR/.env"
  PORT="${SERVER_PORT:-$PORT}"
fi

ok() {
  echo "[OK] $*"
}

warn() {
  echo "[WARN] $*" >&2
}

fail() {
  echo "[FAIL] $*" >&2
  exit 1
}

check_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is not installed"
  ok "$1 is installed"
}

check_project_files() {
  [ -d "$PROJECT_DIR" ] || fail "Project directory not found: $PROJECT_DIR"
  [ -f "$PROJECT_DIR/docker-compose.yml" ] || fail "docker-compose.yml not found in $PROJECT_DIR"
  [ -f "$PROJECT_DIR/.env" ] || warn ".env not found in $PROJECT_DIR"
  ok "Project directory looks valid: $PROJECT_DIR"
}

check_container() {
  cd "$PROJECT_DIR"
  docker compose ps
}

check_health() {
  curl -fsS "http://127.0.0.1:${PORT}/health" >/tmp/esp32-ai-health.json
  ok "Local health endpoint is reachable: http://127.0.0.1:${PORT}/health"
  cat /tmp/esp32-ai-health.json
  echo
}

check_port() {
  if command -v ss >/dev/null 2>&1; then
    if ss -lnt | awk '{print $4}' | grep -Eq "(^|:)${PORT}$"; then
      ok "TCP ${PORT} is listening locally"
    else
      warn "TCP ${PORT} is not visible in local listening sockets"
    fi
  else
    warn "ss command is unavailable; skipped listening port check"
  fi
}

check_firewall() {
  if command -v ufw >/dev/null 2>&1; then
    ufw status || true
  fi

  if command -v firewall-cmd >/dev/null 2>&1; then
    firewall-cmd --state >/dev/null 2>&1 && firewall-cmd --list-ports || true
  fi

  warn "Cloud provider security groups cannot be checked from inside the VPS. Open TCP ${PORT} in the provider console."
}

main() {
  check_command docker
  docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is not installed"
  ok "Docker Compose plugin is installed"
  check_command curl
  check_project_files
  check_container
  check_health
  check_port
  check_firewall
  ok "Doctor check complete"
}

main "$@"
