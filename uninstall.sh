#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/esp32-ai-voice-cloud"
REMOVE_IMAGES=false
REMOVE_DOCKER=false

usage() {
  cat <<'EOF'
Usage:
  sudo bash uninstall.sh
  sudo bash uninstall.sh --dir /opt/esp32-ai-voice-cloud
  sudo bash uninstall.sh --remove-images
  sudo bash uninstall.sh --remove-docker

Options:
  --dir PATH         Project directory to remove. Default: /opt/esp32-ai-voice-cloud
  --remove-images   Also remove locally built Docker images for this project.
  --remove-docker   Also remove Docker packages installed on this VPS.
  -h, --help        Show this help.

Notes:
  By default this script only removes the ESP32-S3 AI chat cloud service.
  Docker is kept because other services on the VPS may also use it.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dir)
      INSTALL_DIR="${2:-}"
      shift 2
      ;;
    --remove-images)
      REMOVE_IMAGES=true
      shift
      ;;
    --remove-docker)
      REMOVE_DOCKER=true
      shift
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
    echo "Please run as root: sudo bash uninstall.sh ..." >&2
    exit 1
  fi
}

guard_install_dir() {
  if [ -z "$INSTALL_DIR" ]; then
    echo "Install directory cannot be empty." >&2
    exit 1
  fi

  case "$INSTALL_DIR" in
    /|/opt|/usr|/usr/local|/home|/root)
      echo "Refusing to remove unsafe directory: $INSTALL_DIR" >&2
      exit 1
      ;;
  esac
}

stop_project() {
  if [ ! -d "$INSTALL_DIR" ]; then
    echo "Project directory does not exist: $INSTALL_DIR"
    return
  fi

  if [ -f "$INSTALL_DIR/docker-compose.yml" ] && command -v docker >/dev/null 2>&1; then
    cd "$INSTALL_DIR"
    if docker compose version >/dev/null 2>&1; then
      if [ "$REMOVE_IMAGES" = true ]; then
        docker compose down --remove-orphans --rmi local
      else
        docker compose down --remove-orphans
      fi
    else
      echo "Docker Compose plugin is unavailable; skipping compose cleanup." >&2
    fi
  fi
}

remove_project_files() {
  if [ -d "$INSTALL_DIR" ]; then
    rm -rf -- "$INSTALL_DIR"
    echo "Removed project directory: $INSTALL_DIR"
  fi
}

remove_docker_packages() {
  if [ "$REMOVE_DOCKER" != true ]; then
    echo "Docker was kept. Use --remove-docker only if this VPS does not need Docker for other services."
    return
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    echo "Cannot remove Docker automatically because apt-get is unavailable." >&2
    return
  fi

  apt-get remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker.io docker-doc docker-compose podman-docker containerd runc || true
  apt-get autoremove -y || true
  echo "Docker packages were removed."
}

main() {
  need_root
  guard_install_dir
  stop_project
  remove_project_files
  remove_docker_packages
  echo "Uninstall complete."
}

main "$@"
