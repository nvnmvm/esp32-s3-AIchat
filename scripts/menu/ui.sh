#!/usr/bin/env bash

menu_title() {
  printf '\n=== %s ===\n' "$1"
}

warn() {
  printf '%s\n' "$1" >&2
}

press_enter() {
  local prompt="${1:-Press Enter to continue...}"
  read -r -p "$prompt" _
}

mask_secret() {
  local value="${1:-}"
  if [ -z "$value" ]; then
    printf '<empty>'
    return
  fi
  if [ "${#value}" -le 8 ]; then
    printf '<configured>'
    return
  fi
  printf '%s...%s' "${value:0:4}" "${value: -4}"
}

confirm_phrase() {
  local phrase="$1"
  local prompt="$2"
  local answer
  read -r -p "$prompt" answer
  [ "$answer" = "$phrase" ]
}

show_launch_help() {
  cat <<EOF

Quick management:

  cd $PROJECT_DIR
  sudo bash manage.sh

Logs:

  cd $PROJECT_DIR
  docker compose logs -f

EOF
}
