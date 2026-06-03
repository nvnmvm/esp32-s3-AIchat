#!/usr/bin/env bash

load_language() {
  local lang="${MENU_LANG:-zh_CN}"
  case "$lang" in
    zh_CN|en_US) ;;
    *) lang="zh_CN" ;;
  esac
  # shellcheck disable=SC1090
  . "$MENU_DIR/lang/${lang}.sh"
}

t() {
  local key="$1"
  local var="MSG_${key}"
  printf '%s' "${!var:-$key}"
}

language_menu() {
  while true; do
    load_env
    load_language
    echo
    menu_title "$(t language)"
    echo "Current: ${MENU_LANG:-zh_CN}"
    echo "1) 简体中文 / Chinese"
    echo "2) English"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1) set_env_value MENU_LANG "zh_CN"; load_env; load_language; echo "已切换为中文。" ;;
      2) set_env_value MENU_LANG "en_US"; load_env; load_language; echo "Switched to English." ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}
