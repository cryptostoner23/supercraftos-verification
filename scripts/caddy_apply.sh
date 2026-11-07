#!/usr/bin/env bash
# Caddy runs from /etc/caddy/config.json. The Caddyfile is the source of
# truth, so this adapts it, validates the result and reloads Caddy.
#
#   scripts/caddy_apply.sh
#
# The previous configuration is kept next to the new one, so a bad change can
# be undone in one command.
set -euo pipefail

CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
CONFIG="${CONFIG:-/etc/caddy/config.json}"
STAMP="$(date +%s)"

if [ ! -f "$CADDYFILE" ]; then
  echo "error: $CADDYFILE is missing" >&2
  exit 1
fi

cp "$CONFIG" "$CONFIG.bak-$STAMP"
caddy adapt --config "$CADDYFILE" --pretty > /tmp/caddy-adapt.json
caddy validate --config /tmp/caddy-adapt.json >/dev/null
cp /tmp/caddy-adapt.json "$CONFIG"
systemctl reload caddy
sleep 2
echo "caddy reloaded from $CADDYFILE (previous config kept as $CONFIG.bak-$STAMP)"
