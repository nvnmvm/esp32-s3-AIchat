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
  [ -f "$PROJECT_DIR/scripts/model_config_cli.py" ] || fail "model_config_cli.py not found"
  [ -f "$PROJECT_DIR/scripts/inspect_wav.py" ] || fail "inspect_wav.py not found"
  ok "Project directory looks valid: $PROJECT_DIR"
}

check_container() {
  cd "$PROJECT_DIR"
  docker compose ps
}

check_health() {
  local attempt
  for attempt in 1 2 3 4 5; do
    if curl -fsS "http://127.0.0.1:${PORT}/health" >/tmp/esp32-ai-health.json; then
      ok "Local health endpoint is reachable: http://127.0.0.1:${PORT}/health"
      cat /tmp/esp32-ai-health.json
      echo
      return
    fi
    warn "Health endpoint is not ready yet; retry ${attempt}/5"
    sleep 2
  done
  fail "Local health endpoint is not reachable: http://127.0.0.1:${PORT}/health"
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

check_resources() {
  local avail_kb
  local swap_total_kb
  if command -v df >/dev/null 2>&1; then
    avail_kb="$(df -Pk "$PROJECT_DIR" 2>/dev/null | awk 'NR == 2 { print $4 }')"
    if [ -n "$avail_kb" ] && [ "$avail_kb" -lt 1048576 ]; then
      warn "Less than 1 GiB free near $PROJECT_DIR. Vosk model download and Docker rebuilds may fail."
    else
      ok "Disk space near $PROJECT_DIR is acceptable"
    fi
  fi
  if command -v free >/dev/null 2>&1; then
    swap_total_kb="$(free -k | awk '$1 == "Swap:" { print $2 }')"
    if [ -z "$swap_total_kb" ] || [ "$swap_total_kb" -eq 0 ]; then
      warn "No swap is configured. A 1C1G VPS should add about 1 GiB swap for Vosk/model downloads."
    else
      ok "Swap is configured"
    fi
  fi
}

check_session_config() {
  echo "Session root: ${SESSION_DIR:-runtime/session}"
  echo "Recordings: ${SESSION_RECORDINGS_DIR:-runtime/session/录音}"
  echo "Transcripts: ${SESSION_TRANSCRIPTS_DIR:-runtime/session/录音转文字}"
  echo "Answers: ${SESSION_ANSWERS_DIR:-runtime/session/ai回答的文本}"
  echo "Audio reports: ${SESSION_AUDIO_REPORT_DIR:-runtime/session/audio_report}"
  echo "Session retention days: ${SESSION_RETENTION_DAYS:-3}"
  echo "Model config: ${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  echo "ASR provider: ${ASR_PROVIDER:-auto}"
  echo "ASR primary: ${ASR_PRIMARY:-configured_asr}"
  echo "ASR fallback: ${ASR_FALLBACK:-vosk}"
  echo "TTS provider: ${TTS_PROVIDER:-edge}"
  echo "LLM provider: ${LLM_PROVIDER:-auto}"
  if [ "${ASR_FALLBACK:-vosk}" = "vosk" ] || [ "${ASR_PROVIDER:-auto}" = "vosk" ]; then
    echo "Vosk model dir: ${VOSK_MODEL_DIR:-runtime/models/vosk-model-small-cn-0.22}"
  fi
  local model_config="${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  case "$model_config" in
    /*) ;;
    *) model_config="$PROJECT_DIR/$model_config" ;;
  esac
  if [ -f "$model_config" ]; then
    if command -v python3 >/dev/null 2>&1; then
      python3 "$PROJECT_DIR/scripts/model_config_cli.py" --config "$model_config" list || true
    fi
  else
    warn "Model config file not found yet. Use manage.sh > Large model brands to add one."
  fi
}

main() {
  check_command docker
  docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is not installed"
  ok "Docker Compose plugin is installed"
  check_command curl
  check_project_files
  check_resources
  check_session_config
  check_container
  check_health
  check_port
  check_firewall
  ok "Doctor check complete"
}

main "$@"
