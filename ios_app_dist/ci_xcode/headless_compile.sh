#!/bin/bash
# Headless build client for SuperCraftOS.
#
# This runs on the 2015 MacBook Air, which is a deprecated, low resource
# machine with under 30 GB of internal disk. Three rules are absolute:
#
#   1. Never write build outputs, caches or metadata to the internal root
#      filesystem. Everything is pinned to the /Volumes/EAGET/ external APFS
#      container.
#   2. Never open the Xcode GUI. Everything is headless.
#   3. Limit compile concurrency to 2 and pin the target SDK to iphoneos, so
#      the old Intel CPU does not throttle or overheat and the toolchain
#      instance cannot mismatch.
#
# It is expected to live at /Volumes/EAGET/ios_project/headless_compile.sh
set -euo pipefail

STAGING="/Volumes/EAGET/ios_project"
DERIVED="/Volumes/EAGET/XcodeDerivedData"
BUILDS="/Volumes/EAGET/builds"
PROJECT="$STAGING/ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj"
SCHEME="SuperCraftOS"
export SDKROOT=iphoneos

say() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

say "checking the external volume is mounted"
if [ ! -d /Volumes/EAGET ]; then
  echo "error: /Volumes/EAGET is not mounted. Nothing was written to the internal disk." >&2
  exit 1
fi

say "free space on the external volume"
df -h /Volumes/EAGET | tail -1

cd "$STAGING"

say "generating the Xcode project"
if ! command -v xcodegen >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    brew install xcodegen
  else
    echo "error: xcodegen is not installed and brew is not available" >&2
    exit 1
  fi
fi
xcodegen generate --spec ios_app_dist/ci_xcode/project.yml

mkdir -p "$DERIVED" "$BUILDS" "$DERIVED/SourcePackages"

say "archiving for a signed device build"
rm -rf "$BUILDS/SuperCraftOS.xcarchive"
set +e
xcodebuild archive \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$BUILDS/SuperCraftOS.xcarchive" \
  -derivedDataPath "$DERIVED" \
  -clonedSourcePackagesDirPath "$DERIVED/SourcePackages" \
  -IDEBuildOperationMaxNumberOfConcurrentCompileTasks=2 \
  -allowProvisioningUpdates \
  CODE_SIGN_STYLE=Automatic \
  SDKROOT=iphoneos \
  2>&1 | tee "$BUILDS/archive.log"
STATUS="${PIPESTATUS[0]}"
set -e
if [ "$STATUS" != 0 ]; then
  echo "error: the archive failed, see $BUILDS/archive.log" >&2
  exit "$STATUS"
fi

say "exporting the ipa"
rm -rf "$BUILDS/ipa"
mkdir -p "$BUILDS/ipa"
set +e
xcodebuild -exportArchive \
  -archivePath "$BUILDS/SuperCraftOS.xcarchive" \
  -exportPath "$BUILDS/ipa" \
  -exportOptionsPlist ios_app_dist/ci_xcode/ExportOptions-development.plist \
  2>&1 | tee "$BUILDS/export.log"
STATUS="${PIPESTATUS[0]}"
set -e
if [ "$STATUS" != 0 ]; then
  echo "error: the export failed, see $BUILDS/export.log" >&2
  exit "$STATUS"
fi

say "built"
ls -la "$BUILDS/ipa"

say "internal disk was not used for build output"
du -sh "$DERIVED" 2>/dev/null || true
