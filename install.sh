#!/usr/bin/env bash
set -euo pipefail

RAW_BASE="https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -r /etc/os-release ]; then
  echo "Cannot detect OS. Please use install-debian.sh or install-ubuntu.sh manually." >&2
  exit 1
fi

. /etc/os-release

case "${ID:-}" in
  debian)
    target_script="install-debian.sh"
    ;;
  ubuntu)
    target_script="install-ubuntu.sh"
    ;;
  *)
    echo "Unsupported OS: ${PRETTY_NAME:-unknown}. This project supports Debian and Ubuntu." >&2
    exit 1
    ;;
esac

if [ -f "${SCRIPT_DIR}/${target_script}" ]; then
  exec bash "${SCRIPT_DIR}/${target_script}" "$@"
fi

tmp_script="$(mktemp)"
trap 'rm -f "$tmp_script"' EXIT
curl -fsSL "${RAW_BASE}/${target_script}" -o "$tmp_script"
exec bash "$tmp_script" "$@"
