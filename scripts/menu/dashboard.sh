#!/usr/bin/env bash

dashboard_menu() {
  load_env
  echo
  menu_title "$(t dashboard)"
  echo "APP_VERSION=${APP_VERSION:-unknown}"
  echo "SERVER_PORT=${SERVER_PORT:-8000}"
  echo "MENU_LANG=${MENU_LANG:-zh_CN}"
  echo "WS_TOKEN=$(mask_secret "${WS_TOKEN:-}")"
  echo "MODEL_CONFIG_PATH=${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  echo
  echo "Configured providers:"
  echo "  LLM_PROVIDER=${LLM_PROVIDER:-auto}"
  echo "  ASR_PROVIDER=${ASR_PROVIDER:-auto}"
  echo "  ASR_STRATEGY=${ASR_STRATEGY:-cloud_first}"
  echo "  ASR_PRIMARY=${ASR_PRIMARY:-configured_asr}"
  echo "  ASR_FALLBACK=${ASR_FALLBACK:-vosk}"
  echo "  TTS_PROVIDER=${TTS_PROVIDER:-edge}"
  echo
  echo "Docker:"
  compose_ps || true
  echo
  print_health_summary || true
  echo
  run_model_cli list || true
  echo
  press_enter "$(t back): "
}
