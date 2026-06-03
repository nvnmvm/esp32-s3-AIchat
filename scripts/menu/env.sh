#!/usr/bin/env bash

need_env() {
  if [ ! -f "$ENV_FILE" ]; then
    echo ".env not found: $ENV_FILE" >&2
    echo "Run deploy.sh first." >&2
    exit 1
  fi
}

load_env() {
  need_env
  # shellcheck disable=SC1090
  . "$ENV_FILE"
}

random_token() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  else
    date +%s%N | sha256sum | awk '{print $1}'
  fi
}

set_env_value() {
  local key="$1"
  local value="$2"
  local tmp_file
  tmp_file="$(mktemp)"
  if [ -f "$ENV_FILE" ] && grep -q "^${key}=" "$ENV_FILE"; then
    awk -v key="$key" -v value="$value" '
      BEGIN { updated = 0 }
      index($0, key "=") == 1 { print key "=" value; updated = 1; next }
      { print }
      END { if (!updated) print key "=" value }
    ' "$ENV_FILE" >"$tmp_file"
    mv "$tmp_file" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
    rm -f "$tmp_file"
  fi
}

validate_port() {
  local port="$1"
  case "$port" in
    ''|*[!0-9]*) echo "Port must be a number." >&2; return 1 ;;
  esac
  [ "$port" -ge 1 ] && [ "$port" -le 65535 ]
}

allow_firewall_port() {
  local port="$1"
  if command -v ufw >/dev/null 2>&1 && ufw status | grep -qi '^Status: active'; then
    ufw allow "${port}/tcp"
  fi
  if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="${port}/tcp"
    firewall-cmd --reload
  fi
}

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "python3"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s' "python"
    return
  fi
  return 1
}

model_config_file() {
  local path="${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  case "$path" in
    /*) printf '%s' "$path" ;;
    *) printf '%s/%s' "$PROJECT_DIR" "$path" ;;
  esac
}

run_model_cli() {
  local py
  py="$(python_bin)" || {
    echo "python3 is not available." >&2
    return 1
  }
  "$py" "$PROJECT_DIR/scripts/model_config_cli.py" --config "$(model_config_file)" "$@"
}

ensure_runtime_config() {
  mkdir -p "$PROJECT_DIR/runtime/config"
}
