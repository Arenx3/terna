#!/bin/sh
# Generates the local secrets on first start, so the stack needs no configuration.
# Existing secrets are never overwritten. To rotate them, remove the volume:
#   docker compose down && docker volume rm terna_secrets
set -eu

dir="${SECRETS_DIR:-/run/secrets}"
mkdir -p "$dir"

generate() {
  name="$1"
  length="$2"
  file="$dir/$name"

  if [ -s "$file" ]; then
    echo "secrets-init: keeping $name"
    return
  fi

  # Alphanumeric only, so the values are safe inside URLs and connection strings.
  value=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$length")
  if [ "${#value}" -ne "$length" ]; then
    echo "secrets-init: could not generate $name" >&2
    exit 1
  fi

  # Written to a temporary file first, so a crash never leaves a half-written secret.
  printf '%s' "$value" >"$file.tmp"
  chmod 0444 "$file.tmp"
  mv "$file.tmp" "$file"
  echo "secrets-init: generated $name"
}

generate django_secret_key 64
generate postgres_password 32
generate redis_password 32
generate storage_access_key 20
generate storage_secret_key 40
