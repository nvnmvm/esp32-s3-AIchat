#!/usr/bin/env bash

can_preserve_update() {
  local version="${APP_VERSION:-}"
  case "$version" in
    v2.0.1-phase2|v2.0.2-phase2|v2.1.*|v3.*) return 0 ;;
    *) return 1 ;;
  esac
}

git_update_code() {
  if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo "This install is not a git checkout. Re-run install.sh for updates." >&2
    return 1
  fi
  git -C "$PROJECT_DIR" fetch --tags origin
  git -C "$PROJECT_DIR" checkout main
  git -C "$PROJECT_DIR" pull --ff-only origin main
}

update_preserve_data() {
  load_env
  if ! can_preserve_update; then
    echo "Current version ${APP_VERSION:-unknown} cannot be updated in place safely."
    return
  fi
  echo "Preserving .env and runtime/ while updating to latest main."
  compose_down || true
  git_update_code
  set_env_value APP_VERSION "$LATEST_VERSION"
  compose_up
  echo "Updated with data preserved."
}

update_clean_data() {
  load_env
  cat <<EOF

This will update code and remove runtime data:
  $PROJECT_DIR/runtime

.env will be kept so WebSocket token, port, and model settings remain configured.
EOF
  confirm_phrase "UPDATE" "Type UPDATE to continue: " || { echo "Cancelled."; return; }
  compose_down || true
  rm -rf -- "$PROJECT_DIR/runtime"
  git_update_code
  set_env_value APP_VERSION "$LATEST_VERSION"
  compose_up
  echo "Updated after removing runtime data."
}

uninstall_service() {
  echo "This will uninstall the WebSocket cloud service from: $PROJECT_DIR"
  confirm_phrase "UNINSTALL" "Type UNINSTALL to continue: " || { echo "Cancelled."; return; }
  if [ "$(id -u)" -ne 0 ]; then
    echo "Please run: sudo bash $PROJECT_DIR/uninstall.sh --dir $PROJECT_DIR" >&2
    return
  fi
  bash "$PROJECT_DIR/uninstall.sh" --dir "$PROJECT_DIR"
  exit 0
}

maintenance_menu() {
  while true; do
    load_env
    echo
    menu_title "$(t maintenance)"
    echo "Latest release target: $LATEST_VERSION"
    echo "Current APP_VERSION: ${APP_VERSION:-unknown}"
    echo "1) Update, preserve .env and runtime data"
    echo "2) Update, remove runtime data"
    echo "3) Uninstall WebSocket service"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1) update_preserve_data ;;
      2) update_clean_data ;;
      3) uninstall_service ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}
