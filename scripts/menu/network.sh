#!/usr/bin/env bash

show_safe_config() {
  load_env
  echo
  echo "Config file: $ENV_FILE"
  echo "APP_VERSION=${APP_VERSION:-unknown}"
  echo "SERVER_PORT=${SERVER_PORT:-8000}"
  echo "WS_TOKEN=$(mask_secret "${WS_TOKEN:-}")"
  echo "ALLOW_EMPTY_TOKEN=${ALLOW_EMPTY_TOKEN:-false}"
  echo "MENU_LANG=${MENU_LANG:-zh_CN}"
  echo "LLM_PROVIDER=${LLM_PROVIDER:-auto}"
  echo "LLM_DEFAULT_VENDOR=${LLM_DEFAULT_VENDOR:-}"
  echo "MODEL_CONFIG_PATH=${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  echo "ASR_PROVIDER=${ASR_PROVIDER:-auto}"
  echo "ASR_STRATEGY=${ASR_STRATEGY:-cloud_first}"
  echo "ASR_PRIMARY=${ASR_PRIMARY:-configured_asr}"
  echo "ASR_FALLBACK=${ASR_FALLBACK:-vosk}"
  echo "ASR_DEFAULT_VENDOR=${ASR_DEFAULT_VENDOR:-}"
  echo "TTS_PROVIDER=${TTS_PROVIDER:-edge}"
  echo "SEND_ASR_TEXT=${SEND_ASR_TEXT:-false}"
  echo "SEND_ANSWER_TEXT=${SEND_ANSWER_TEXT:-true}"
  echo "LOG_TO_FILE=${LOG_TO_FILE:-true}"
  echo "SESSION_RETENTION_DAYS=${SESSION_RETENTION_DAYS:-3}"
  echo
  model_list || true
}

show_sensitive_config() {
  confirm_phrase "SHOW" "This prints secrets. Type SHOW to continue: " || { echo "Cancelled."; return; }
  sed -n '1,220p' "$ENV_FILE"
  echo
  if [ -f "$(model_config_file)" ]; then
    sed -n '1,260p' "$(model_config_file)"
  fi
}

change_port() {
  local port
  read -r -p "New WebSocket port: " port
  validate_port "$port" || { echo "Invalid port." >&2; return 1; }
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
    token="$(read_required "New WebSocket token: ")" || return 1
  else
    token="$(random_token)"
  fi
  case "$token" in
    *[[:space:]]*) echo "Token cannot contain whitespace." >&2; return 1 ;;
  esac
  set_env_value WS_TOKEN "$token"
  compose_up
  echo "Token updated."
  echo "Set ESP32 WS_TOKEN to: $token"
}

show_esp32_config_hint() {
  load_env
  local public_ip
  public_ip="$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}' || true)"
  public_ip="${public_ip:-YOUR_VPS_PUBLIC_IP}"
  echo "WebSocket URL: ws://${public_ip}:${SERVER_PORT:-8000}/ws"
  echo "WS_HOST: $public_ip"
  echo "WS_PORT: ${SERVER_PORT:-8000}"
  echo "WS_TOKEN: ${WS_TOKEN:-}"
}

network_menu() {
  while true; do
    load_env
    echo
    menu_title "$(t network_security)"
    echo "Port: ${SERVER_PORT:-8000}"
    echo "Token: $(mask_secret "${WS_TOKEN:-}")"
    echo "1) Show safe config"
    echo "2) Change WebSocket port"
    echo "3) Regenerate / set WebSocket token"
    echo "4) Show ESP32 firmware config"
    echo "5) Show sensitive config"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1) show_safe_config ;;
      2) change_port ;;
      3) change_token ;;
      4) show_esp32_config_hint ;;
      5) show_sensitive_config ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}
