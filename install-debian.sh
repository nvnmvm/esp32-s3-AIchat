#!/usr/bin/env bash
set -euo pipefail

EXPECTED_OS="debian"
INSTALL_DIR="/opt/esp32-ai-voice-cloud"
REPO_URL=""

usage() {
  cat <<'EOF'
Usage:
  sudo bash install-debian.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git
  sudo bash install-debian.sh --dir /opt/esp32-ai-voice-cloud

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
    echo "Please run as root: sudo bash install-debian.sh ..." >&2
    exit 1
  fi
}

require_expected_os() {
  if [ ! -r /etc/os-release ]; then
    echo "Cannot detect OS. This script supports Debian only." >&2
    exit 1
  fi

  . /etc/os-release
  if [ "${ID:-}" != "$EXPECTED_OS" ]; then
    echo "Unsupported OS: ${PRETTY_NAME:-unknown}. Please use install-debian.sh only on Debian." >&2
    exit 1
  fi
}

start_docker() {
  if command -v systemctl >/dev/null 2>&1 && systemctl enable --now docker; then
    return
  fi

  if command -v service >/dev/null 2>&1; then
    service docker start
  else
    echo "Docker installed, but this system has neither systemctl nor service. Start Docker manually if it is not running." >&2
  fi
}

install_docker_from_distro_repo() {
  apt-get install -y docker.io docker-compose-plugin
}

remove_conflicting_docker_packages() {
  apt-get remove -y docker.io docker-doc docker-compose podman-docker containerd runc >/dev/null 2>&1 || true
}

install_docker_from_official_repo() {
  . /etc/os-release
  codename="${VERSION_CODENAME:-}"

  if [ -z "$codename" ]; then
    echo "Cannot detect Debian codename for Docker repository setup." >&2
    exit 1
  fi

  remove_conflicting_docker_packages

  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc

  arch="$(dpkg --print-architecture)"
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${codename} stable" \
    >/etc/apt/sources.list.d/docker.list

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

install_packages() {
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "This installer requires apt-get." >&2
    exit 1
  fi

  apt-get update
  apt-get install -y ca-certificates curl git gnupg openssl

  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    start_docker
    return
  fi

  if ! install_docker_from_distro_repo; then
    echo "Debian Docker packages unavailable; falling back to Docker official repository." >&2
    install_docker_from_official_repo
  fi

  start_docker

  if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose plugin is still unavailable after installation." >&2
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
      echo "Repository URL is required when this script is not run inside the project directory." >&2
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
  require_expected_os
  install_packages
  fetch_project
  chmod +x "$INSTALL_DIR/deploy.sh"
  "$INSTALL_DIR/deploy.sh"
}

main "$@"
