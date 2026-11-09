#!/bin/bash
# simulator [device-name]        build/install using a compatible local Xcode
# free [prepare options]        prepare cloud IPA for local Sideloadly signing
# device --ipa FILE --udid UDID  verify an already signed IPA and install by USB
# See docs/FREE_APPLE_INSTALL.md; free-account profiles expire after 7 days.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-simulator}"
if [ "$#" -gt 0 ]; then shift; fi
case "$MODE" in
  free)
    exec python3 "$ROOT/scripts/ios_device_install.py" prepare "$@"
    ;;
  device)
    exec python3 "$ROOT/scripts/ios_device_install.py" install-signed "$@"
    ;;
  simulator)
    DEVICE="${1:-iPhone 16}"
    "$ROOT/scripts/ios_release.sh" simulator
    APP="$ROOT/build/ios/simulator/Build/Products/Debug-iphonesimulator/SuperCraftOS.app"
    xcrun simctl boot "$DEVICE" 2>/dev/null || true
    open -a Simulator 2>/dev/null || true
    xcrun simctl install booted "$APP"
    xcrun simctl launch booted com.supercraftos.control
    echo "Simulator launched. This does not verify a physical-device install."
    ;;
  *)
    echo "usage: $0 {simulator [device-name]|free [options]|device --ipa FILE --udid UDID [options]}" >&2
    exit 2
    ;;
esac
