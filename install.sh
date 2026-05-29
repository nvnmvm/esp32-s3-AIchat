#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/esp32-ai-voice-cloud"
REPO_URL=""

usage() {
  cat <<'EOF'
Usage:
  sudo bash install.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git
  sudo bash install.sh --dir /opt/esp32-ai-voice-cloud

Options:
  --repo URL    Git repository to clone or update before deployment.
  --dir PATH    Install directory. Default: /opt/esp32-ai-voice-cloud
  -h, --help    Show this help.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --repo)
      REPO_URL="${2:-}"
      shift 2
      ;;
    --dir)
      INSTALL_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root: sudo bash install.sh ..." >&2
    exit 1
  fi
}

install_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y ca-certificates curl git openssl docker.io docker-compose-plugin
    systemctl enable --now docker
  else
    echo "This installer currently supports Debian/Ubuntu VPS systems with apt-get." >&2
    exit 1
  fi
}

fetch_project() {
  if [ -z "$REPO_URL" ]; then
    if [ -f "./docker-compose.yml" ] && [ -f "./deploy.sh" ]; then
      INSTALL_DIR="$(pwd)"
      return
    fi

    read -r -p "Git repository URL: " REPO_URL
    if [ -z "$REPO_URL" ]; then
      echo "Repository URL is required when install.sh is not run inside the project directory." >&2
      exit 1
    fi
  fi

  if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull --ff-only
  else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
}

main() {
  need_root
  install_packages
  fetch_project
  chmod +x "$INSTALL_DIR/deploy.sh"
  "$INSTALL_DIR/deploy.sh"
}

main "$@"
