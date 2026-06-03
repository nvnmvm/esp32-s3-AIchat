#!/usr/bin/env bash

set_session_retention_days() {
  local days="$1"
  set_env_value SESSION_RETENTION_DAYS "$days"
  compose_up
  echo "Session file retention updated to ${days} day(s)."
}

list_recent_files() {
  local dir="$1"
  local label="$2"
  echo
  echo "$label: $dir"
  if [ -d "$PROJECT_DIR/$dir" ]; then
    find "$PROJECT_DIR/$dir" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM %f\n' 2>/dev/null | sort -r | head -20 || true
  else
    echo "Not found."
  fi
}

show_session_dirs() {
  load_env
  echo "Root: ${SESSION_DIR:-runtime/session}"
  echo "Recordings: ${SESSION_RECORDINGS_DIR:-runtime/session/录音}"
  echo "Transcripts: ${SESSION_TRANSCRIPTS_DIR:-runtime/session/录音转文字}"
  echo "Answers: ${SESSION_ANSWERS_DIR:-runtime/session/ai回答的文本}"
  echo "Audio reports: ${SESSION_AUDIO_REPORT_DIR:-runtime/session/audio_report}"
  echo "Retention: ${SESSION_RETENTION_DAYS:-3} day(s)"
}

cleanup_old_session_files_now() {
  local py
  py="$(python_bin)" || { echo "python3 is not available." >&2; return 1; }
  cd "$PROJECT_DIR"
  "$py" - <<'PY'
from app.main import cleanup_old_session_files
cleanup_old_session_files()
print("Old session files cleaned according to SESSION_RETENTION_DAYS.")
PY
}

data_menu() {
  while true; do
    load_env
    echo
    menu_title "$(t data_storage)"
    show_session_dirs
    echo "1) Show session directories"
    echo "2) List recent recordings"
    echo "3) List recent transcripts"
    echo "4) List recent answers"
    echo "5) List recent audio reports"
    echo "6) Keep sessions 1 day"
    echo "7) Keep sessions 3 days"
    echo "8) Keep sessions 7 days"
    echo "9) Keep sessions 30 days"
    echo "10) Cleanup old session files now"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1) show_session_dirs ;;
      2) list_recent_files "${SESSION_RECORDINGS_DIR:-runtime/session/录音}" "Recordings" ;;
      3) list_recent_files "${SESSION_TRANSCRIPTS_DIR:-runtime/session/录音转文字}" "Transcripts" ;;
      4) list_recent_files "${SESSION_ANSWERS_DIR:-runtime/session/ai回答的文本}" "Answers" ;;
      5) list_recent_files "${SESSION_AUDIO_REPORT_DIR:-runtime/session/audio_report}" "Audio reports" ;;
      6) set_session_retention_days 1 ;;
      7) set_session_retention_days 3 ;;
      8) set_session_retention_days 7 ;;
      9) set_session_retention_days 30 ;;
      10) cleanup_old_session_files_now ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}
