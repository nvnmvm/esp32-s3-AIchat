#!/usr/bin/env bash

show_recent_logs() {
  cd "$PROJECT_DIR"
  docker compose logs --tail=120
}

follow_logs() {
  cd "$PROJECT_DIR"
  docker compose logs -f
}

show_file_logs() {
  local log_dir="${LOG_DIR:-runtime/logs}"
  if [ -f "$PROJECT_DIR/$log_dir/cloud.log" ]; then
    tail -n 120 "$PROJECT_DIR/$log_dir/cloud.log"
  else
    echo "File log not found: $PROJECT_DIR/$log_dir/cloud.log"
  fi
}

set_log_retention_days() {
  local days="$1"
  set_env_value LOG_RETENTION_DAYS "$days"
  set_env_value LOG_TO_FILE "true"
  compose_up
  echo "Log retention updated to ${days} day(s)."
}

run_doctor() {
  bash "$PROJECT_DIR/scripts/doctor.sh"
}

logs_menu() {
  while true; do
    load_env
    echo
    menu_title "$(t logs_diag)"
    echo "File logging: ${LOG_TO_FILE:-true}"
    echo "Retention: ${LOG_RETENTION_DAYS:-7} day(s)"
    echo "Log dir: ${LOG_DIR:-runtime/logs}"
    echo "1) Run doctor"
    echo "2) Health summary"
    echo "3) Follow realtime Docker logs"
    echo "4) Show recent Docker logs"
    echo "5) Show recent file logs"
    echo "6) Keep logs 7 days"
    echo "7) Keep logs 3 days"
    echo "8) Keep logs 1 day"
    echo "9) Disable file logs"
    echo "10) Enable file logs"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1) run_doctor ;;
      2) print_health_summary ;;
      3) follow_logs ;;
      4) show_recent_logs ;;
      5) show_file_logs ;;
      6) set_log_retention_days 7 ;;
      7) set_log_retention_days 3 ;;
      8) set_log_retention_days 1 ;;
      9) set_env_value LOG_TO_FILE "false"; compose_up ;;
      10) set_env_value LOG_TO_FILE "true"; compose_up ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}
