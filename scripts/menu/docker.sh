#!/usr/bin/env bash

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

compose_ps() {
  cd "$PROJECT_DIR"
  docker compose ps
}

health_json() {
  load_env
  curl -fsS "http://127.0.0.1:${SERVER_PORT:-8000}/health" 2>/dev/null || true
}

print_health_summary() {
  local body py
  body="$(health_json)"
  if [ -z "$body" ]; then
    echo "Health: unavailable"
    return
  fi
  py="$(python_bin 2>/dev/null || true)"
  if [ -n "$py" ]; then
    printf '%s' "$body" | "$py" -c '
import json, sys
data = json.load(sys.stdin)
print("Health: ok=%s version=%s phase=%s" % (data.get("ok"), data.get("version"), data.get("phase")))
print("ASR: provider=%s strategy=%s chain=%s" % (data.get("asr_provider"), data.get("asr_strategy", "cloud_first"), data.get("asr_provider_chain")))
print("LLM: provider=%s configured=%s" % (data.get("llm_provider"), data.get("ai_api_key_configured")))
readiness = data.get("model_readiness") or {}
print("Readiness: asr_configured=%s llm_configured=%s local_fallback=%s" % (
    readiness.get("asr_configured"),
    readiness.get("llm_configured"),
    readiness.get("using_local_fallback"),
))
for warning in readiness.get("warnings") or []:
    print("Warning: %s" % warning)
print("TTS: %s / %s" % (data.get("tts_provider"), data.get("tts_mode")))
'
  else
    printf '%s\n' "$body"
  fi
}

service_control_menu() {
  while true; do
    load_env
    echo
    menu_title "$(t service_control)"
    echo "1) Start / rebuild WebSocket service"
    echo "2) Stop WebSocket service"
    echo "3) Restart WebSocket service"
    echo "4) Docker compose status"
    echo "5) Health summary"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1) compose_up ;;
      2) compose_stop ;;
      3) compose_down; compose_up ;;
      4) compose_ps ;;
      5) print_health_summary ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}
