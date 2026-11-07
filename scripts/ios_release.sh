#!/bin/bash
# Build a signed SuperCraftOS archive and export an IPA on a Mac with Xcode.
#
#   scripts/ios_release.sh simulator     unsigned simulator app, installable with simctl
#   scripts/ios_release.sh device        signed development IPA, installable on a device
#   scripts/ios_release.sh testflight    signed App Store Connect IPA, uploadable to TestFlight
#
# Requirements for the signed modes: Xcode, an Apple Developer account, and
# either automatic signing with a connected team or a distribution certificate
# and a provisioning profile in the keychain. The App Group
# group.com.supercraftos.control must be enabled for both bundle identifiers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/ios_app_dist/ci_xcode/project.yml"
PROJECT="$ROOT/ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj"
SCHEME="SuperCraftOS"
BUNDLE_ID="com.supercraftos.control"
KEYBOARD_ID="com.supercraftos.control.keyboard"
MODE="${1:-simulator}"
BUILD_DIR="$ROOT/build/ios"
ARCHIVE="$BUILD_DIR/SuperCraftOS.xcarchive"

# The backend the keyboard extension talks to. Baked into the extension bundle
# so it can reach the agent with no App Group entitlement, which is what a
# free personal team can sign. Leave empty when the host app publishes the
# address through the App Group instead.
BACKEND_URL="${SUPERCRAFTOS_BACKEND_URL:-}"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "error: $1 is required" >&2; exit 1; }
}

require xcodebuild
[ "$(uname -s)" = "Darwin" ] || { echo "error: this script needs macOS with Xcode" >&2; exit 1; }

if ! command -v xcodegen >/dev/null 2>&1; then
  echo "==> installing xcodegen"
  brew install xcodegen
fi

echo "==> generating the Xcode project"
if [ "$MODE" = "full" ]; then
  python3 "$ROOT/scripts/xcode_project.py" --embed-keyboard
else
  python3 "$ROOT/scripts/xcode_project.py"
fi

case "$MODE" in
  full)
    echo "==> archiving the full app with the keyboard embedded"
    rm -rf "$BUILD_DIR"
    xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration Release \
      -archivePath "$ARCHIVE" -destination 'generic/platform=iOS' \
      -allowProvisioningUpdates SUPERCRAFTOS_BACKEND_URL="$BACKEND_URL" archive
    echo "==> exporting the development IPA"
    rm -rf "$BUILD_DIR/ipa"
    xcodebuild -exportArchive -archivePath "$ARCHIVE" \
      -exportPath "$BUILD_DIR/ipa" \
      -exportOptionsPlist "$ROOT/ios_app_dist/ci_xcode/ExportOptions-development.plist"
    echo "==> exported to $BUILD_DIR/ipa"
    echo "    install with: xcrun devicectl device install app $BUILD_DIR/ipa/*.ipa"
    ;;
  simulator)
    echo "==> building the unsigned simulator app"
    rm -rf "$BUILD_DIR/simulator"
    xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration Debug \
      -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
      -derivedDataPath "$BUILD_DIR/simulator" CODE_SIGNING_ALLOWED=NO \
      SUPERCRAFTOS_BACKEND_URL="$BACKEND_URL" build
    APP="$BUILD_DIR/simulator/Build/Products/Debug-iphonesimulator/SuperCraftOS.app"
    test -d "$APP"
    echo "==> built $APP"
    echo "    install with: xcrun simctl install booted '$APP'"
    ;;
  device)
    echo "==> archiving for a signed development build"
    rm -rf "$BUILD_DIR"
    xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration Release \
      -archivePath "$ARCHIVE" -destination 'generic/platform=iOS' \
      -allowProvisioningUpdates SUPERCRAFTOS_BACKEND_URL="$BACKEND_URL" archive
    echo "==> exporting the development IPA"
    rm -rf "$BUILD_DIR/ipa"
    xcodebuild -exportArchive -archivePath "$ARCHIVE" \
      -exportPath "$BUILD_DIR/ipa" \
      -exportOptionsPlist "$ROOT/ios_app_dist/ci_xcode/ExportOptions-development.plist"
    echo "==> exported to $BUILD_DIR/ipa"
    echo "    install with: xcrun devicectl device install app $BUILD_DIR/ipa/*.ipa"
    ;;
  testflight)
    echo "==> archiving for App Store Connect"
    rm -rf "$BUILD_DIR"
    xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration Release \
      -archivePath "$ARCHIVE" -destination 'generic/platform=iOS' \
      -allowProvisioningUpdates SUPERCRAFTOS_BACKEND_URL="$BACKEND_URL" archive
    echo "==> exporting the App Store Connect IPA"
    rm -rf "$BUILD_DIR/ipa"
    xcodebuild -exportArchive -archivePath "$ARCHIVE" \
      -exportPath "$BUILD_DIR/ipa" \
      -exportOptionsPlist "$ROOT/ios_app_dist/ci_xcode/ExportOptions-app-store-connect.plist"
    echo "==> exported to $BUILD_DIR/ipa"
    echo "    upload with: scripts/upload_to_testflight.sh $BUILD_DIR/ipa/*.ipa"
    ;;
  *)
    echo "usage: $0 {simulator|full|device|testflight}" >&2
    exit 2
    ;;
esac
