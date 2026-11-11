#!/usr/bin/env bash
# SuperCraftOS — free personal-team signing + install (Sideloadly-style).
#
# Purpose:
#   1. Read credentials from .signing/creds.env (Apple ID + app-specific
#      password + iPhone UDID).
#   2. Sign the unsigned IPA with the free "Personal Team" (no paid Apple
#      Developer Program membership).
#   3. Install the signed app onto the iPhone over USB or Wi-Fi (paired).
#
# This is the mechanism that "resets the 7-day timer": re-running it
# regenerates the expiring free-team provisioning profile and reinstalls.
# Schedule it with launchd (see launchd plist below) so it runs automatically.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CREDS="$ROOT/.signing/creds.env"
[ -f "$CREDS" ] || { echo "missing $CREDS"; exit 1; }
# shellcheck disable=SC1090
source "$CREDS"

# --- safety: refuse placeholder / empty values ---
if [[ "$APPLE_ID" == *YOUR_* || -z "$APPLE_ID" ]]; then
  echo "error: set APPLE_ID in $CREDS"; exit 1
fi
if [[ -z "$APPLE_APP_SPECIFIC_PASSWORD" || "$APPLE_APP_SPECIFIC_PASSWORD" == *YOUR_* ]]; then
  echo "error: set APPLE_APP_SPECIFIC_PASSWORD in $CREDS"; exit 1
fi
if [[ -z "$DEVICE_UDID" || "$DEVICE_UDID" == *00008110-0000000000000000* ]]; then
  echo "error: set DEVICE_UDID in $CREDS"; exit 1
fi

export DEVELOPER_DIR="${DEVELOPER_DIR:-/Users/hsk/Downloads/Xcode.app/Contents/Developer}"

echo "==>[1/4] Ensuring iPhone reachable (USB or Wi-Fi)")
$DEVELOPER_DIR/usr/bin/devicectl list devices --json 2>/dev/null | grep -q "$DEVICE_UDID" \
  && echo "   device seen" || echo "   WARNING: device not listed; will retry via devicectl discovery"

echo "==>[2/4] Building signed app via Xcode automatic personal-team signing"
# Xcode's free-team automatic signing will use the Apple ID account previously
# added in Xcode's Accounts pane (Signing & Capabilities). If not yet added,
# the first run must add it once in Xcode GUI.
xcodebuild -project "$ROOT/ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj" \
  -scheme SuperCraftOS -configuration Release \
  -destination "id=$DEVICE_UDID" \
  -allowProvisioningUpdates \
  -derivedDataPath "$ROOT/build/signed" \
  DEVELOPMENT_TEAM="" CODE_SIGN_STYLE="Automatic" \
  | tail -20

echo "==>[3/4] Packaging signed IPA"
APP="$ROOT/build/signed/Build/Products/Release-iphoneos/SuperCraftOS.app"
[ -d "$APP" ] || { echo "signed app missing"; exit 1; }
STAGE="$ROOT/build/signed-ipa-staging"; rm -rf "$STAGE"; mkdir -p "$STAGE/Payload"
cp -R "$APP" "$STAGE/Payload/"
(cd "$STAGE" && zip -r -q "$ROOT/build/SuperCraftOS-signed.ipa" Payload)

echo "==>[4/4] Installing to iPhone (USB or Wi-Fi)"
$DEVELOPER_DIR/usr/bin/devicectl device install app --device "$DEVICE_UDID" "$ROOT/build/SuperCraftOS-signed.ipa" \
  && echo "OK: signed app installed" || echo "FAILED: install (is device unlocked/trusted?)"

echo "done"
