#!/usr/bin/env bash
# Prepare the cloud-built IPA for interactive free-account signing on this Mac.
# This does not install the app until you complete Sideloadly's local UI.
# See docs/FREE_APPLE_INSTALL.md. No Apple credentials are read by this script.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER="$SCRIPT_DIR/ios_device_install.py"
if [ ! -f "$HELPER" ]; then
  echo "error: run this script from a complete SuperCraftOS checkout." >&2
  echo "Alternatively download the unsigned IPA and sign/install it locally with https://sideloadly.io." >&2
  echo "Free-account signing expires after 7 days. See docs/FREE_APPLE_INSTALL.md." >&2
  exit 2
fi
exec python3 "$HELPER" prepare "$@"
