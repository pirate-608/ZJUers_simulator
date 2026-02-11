#!/usr/bin/env bash
set -euo pipefail

# Update UFW to allow HTTP/HTTPS only from current Cloudflare IP ranges (IPv4 + IPv6).
# Idempotent: skips rules that already exist. Does not delete old rules.

CF_V4_URL="https://www.cloudflare.com/ips-v4"
CF_V6_URL="https://www.cloudflare.com/ips-v6"
PORTS=(80 443)

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1" >&2; exit 1; }; }

download_list() {
  local url="$1"
  curl -fsSL "$url"
}

rule_exists() {
  local cidr="$1" port="$2"
  ufw status | grep -F "${cidr}" | grep -F "${port}" >/dev/null 2>&1
}

add_rule() {
  local cidr="$1" port="$2"
  if rule_exists "$cidr" "$port"; then
    echo "exists: $cidr port $port"
  else
    ufw allow proto tcp from "$cidr" to any port "$port" comment "cloudflare-$port"
  fi
}

main() {
  need_cmd curl
  need_cmd ufw

  echo "Fetching Cloudflare IP ranges..."
  mapfile -t CF_V4 < <(download_list "$CF_V4_URL")
  mapfile -t CF_V6 < <(download_list "$CF_V6_URL")

  echo "Applying IPv4 rules..."
  for cidr in "${CF_V4[@]}"; do
    for port in "${PORTS[@]}"; do
      add_rule "$cidr" "$port"
    done
  done

  echo "Applying IPv6 rules..."
  for cidr in "${CF_V6[@]}"; do
    for port in "${PORTS[@]}"; do
      add_rule "$cidr" "$port"
    done
  done

  echo "Reloading ufw..."
  ufw reload
  echo "Done."
}

main "$@"
