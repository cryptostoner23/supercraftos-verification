#!/usr/bin/env bash
# SuperCraftOS — provision a free cloud backend and bake the connection into the
# iOS app.
#
# Flow:
#   1. Generate (or read) a 32+ char access key.
#   2. Instruct on setting it as SUPERCRAFTOS_ACCESS_KEY on the cloud service
#      (Render / Railway / alwaysdata / Fly). The gateway reads it from env so
#      the SAME key authorizes the app.
#   3. Build the iOS app with that key + the cloud URL baked in.
#   4. Install the signed build to the iPhone (USB/Wi-Fi) via pymobiledevice3.
#
# Usage:
#   CLOUD_URL=https://your-backend.onrender.com bash scripts/provision_cloud_backend.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLOUD_URL="${CLOUD_URL:-}"
[ -n "$CLOUD_URL" ] || { echo "set CLOUD_URL (the deployed backend https URL)"; exit 1; }

# 1. Access key
KEY_FILE="$ROOT/.signing/cloud_access_key.txt"
if [ -s "$KEY_FILE" ]; then
  ACCESS_KEY="$(cat "$KEY_FILE")"
else
  ACCESS_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  printf '%s' "$ACCESS_KEY" > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
fi
echo "access key ready (stored .signing/cloud_access_key.txt, mode 600)"

echo "==> On your cloud service, set env:"
echo "    SUPERCRAFTOS_ACCESS_KEY=<the value in .signing/cloud_access_key.txt>"
echo "    SUPERCRAFTOS_PUBLIC_ORIGIN=$CLOUD_URL"
echo "    SUPERCRAFTOS_EMBEDDED_WORKER=0"
read -r -p "Press Enter once the env var is set on the deployed service..." _

# 2. Bake into the iOS app
echo "==> Building iOS app with baked backend+key"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Users/hsk/Downloads/Xcode.app/Contents/Developer}"
cd "$ROOT/ios_app_dist/ci_xcode"
xcodebuild build \
  -project SuperCraftOS.xcodeproj -scheme SuperCraftOS -configuration Release \
  -sdk iphoneos -destination 'generic/platform=iOS' \
  -derivedDataPath "$ROOT/build/cloud"
  CODE_SIGN_STYLE=Automatic CODE_SIGNING_ALLOWED=YES \
  DEVELOPMENT_TEAM=9GXQGAM6KB -allowProvisioningUpdates \
  SUPERCRAFTOS_BACKEND_URL="$CLOUD_URL" SUPERCRAFTOS_ACCESS_KEY="$ACCESS_KEY" \
  | tail -8

APP="$ROOT/build/cloud/Build/Products/Release-iphoneos/SuperCraftOS.app"
STAGE="$ROOT/build/cloud-ipa-staging"; rm -rf "$STAGE"; mkdir -p "$STAGE/Payload"
cp -R "$APP" "$STAGE/Payload/"
(cd "$STAGE" && zip -r -q "$ROOT/build/SuperCraftOS-cloud-signed.ipa" Payload)

echo "==> Installing to iPhone"
"$ROOT/.venv/bin/pymobiledevice3" apps install "$ROOT/build/SuperCraftOS-cloud-signed.ipa"

echo "done — app connects to $CLOUD_URL with the provisioned key."
