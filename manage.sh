#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
MENU_DIR="$PROJECT_DIR/scripts/menu"
LATEST_VERSION="v4.0.0-realtime-foundation"

# shellcheck source=scripts/menu/env.sh
. "$MENU_DIR/env.sh"
# shellcheck source=scripts/menu/ui.sh
. "$MENU_DIR/ui.sh"
# shellcheck source=scripts/menu/i18n.sh
. "$MENU_DIR/i18n.sh"
# shellcheck source=scripts/menu/docker.sh
. "$MENU_DIR/docker.sh"
# shellcheck source=scripts/menu/dashboard.sh
. "$MENU_DIR/dashboard.sh"
# shellcheck source=scripts/menu/models.sh
. "$MENU_DIR/models.sh"
# shellcheck source=scripts/menu/logs.sh
. "$MENU_DIR/logs.sh"
# shellcheck source=scripts/menu/data.sh
. "$MENU_DIR/data.sh"
# shellcheck source=scripts/menu/network.sh
. "$MENU_DIR/network.sh"
# shellcheck source=scripts/menu/maintenance.sh
. "$MENU_DIR/maintenance.sh"

main_menu() {
  show_launch_help
  while true; do
    load_env
    load_language
    echo
    menu_title "$(t main_title)"
    echo "1) $(t dashboard)"
    echo "2) $(t models_voice)"
    echo "3) $(t service_control)"
    echo "4) $(t logs_diag)"
    echo "5) $(t data_storage)"
    echo "6) $(t network_security)"
    echo "7) $(t language)"
    echo "8) $(t maintenance)"
    echo "0) $(t exit)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1) dashboard_menu ;;
      2) models_voice_menu ;;
      3) service_control_menu ;;
      4) logs_menu ;;
      5) data_menu ;;
      6) network_menu ;;
      7) language_menu ;;
      8) maintenance_menu ;;
      0) exit 0 ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}

main_menu "$@"
