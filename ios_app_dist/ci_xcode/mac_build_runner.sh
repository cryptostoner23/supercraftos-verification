#!/bin/bash
# SuperCraftOS Mac build client runner.
#
# Run this ON THE MAC, as the user that will sign the app:
#
#   curl -fsSL https://agent.commetai.ca/ios/mac_build_runner.sh | bash
#
# It performs the client half of the pipeline, entirely on the Mac:
#
#   1. git sync down to /Volumes/EAGET/ios_project
#   2. clear the macOS quarantine parameters
#   3. fire /Volumes/EAGET/ios_project/headless_compile.sh
#   4. copy the finished bundle to the build server
#
# Nothing is written to the internal disk. The derived data, the source package
# cache and the archive all stay inside the external volume. The build never
# opens the Xcode GUI, compiles at most 2 tasks at a time, and targets iphoneos.
set -uo pipefail

SERVER='https://agent.commetai.ca'
STAGING='/Volumes/EAGET/ios_project'
DERIVED='/Volumes/EAGET/XcodeDerivedData'
BUILDS='/Volumes/EAGET/builds'
TUNNEL='ssh://hsk@127.0.0.1:25177/root/SuperCraftOS'

say() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

say "checking the external volume"
if [ ! -d /Volumes/EAGET ]; then
  echo "error: /Volumes/EAGET is not mounted, refusing to write to the internal disk" >&2
  exit 1
fi
df -h /Volumes/EAGET | tail -1
mkdir -p "$STAGING" "$DERIVED" "$BUILDS"

say "git sync down"
cd "$STAGING" 2>/dev/null || { mkdir -p "$STAGING"; cd "$STAGING"; }
if [ ! -d .git ]; then
  git init -q
  git remote add origin https://github.com/cryptostoner94/SuperCraftOS.git
fi
# Prefer the reverse tunnel to the build server, fall back to the public remote.
if ssh -o BatchMode=yes -o ConnectTimeout=5 -p 25177 hsk@127.0.0.1 true 2>/dev/null; then
  echo "  syncing through the reverse tunnel"
  git remote set-url origin "$TUNNEL" 2>/dev/null || git remote add origin "$TUNNEL"
else
  echo "  syncing through the public remote"
  git remote set-url origin https://github.com/cryptostoner94/SuperCraftOS.git
fi
git fetch --all --prune -q
git checkout -q master
git reset --hard origin/master
git log --oneline -1

say "clearing the macOS quarantine parameters"
xattr -dr com.apple.quarantine . 2>/dev/null || true
xattr -cr . 2>/dev/null || true
echo "  quarantine cleared"

say "firing the headless build"
if [ ! -x "$STAGING/headless_compile.sh" ]; then
  curl -fsSL "$SERVER/ios/headless_compile.sh" -o "$STAGING/headless_compile.sh"
  chmod +x "$STAGING/headless_compile.sh"
  xattr -d com.apple.quarantine "$STAGING/headless_compile.sh" 2>/dev/null || true
fi
"$STAGING/headless_compile.sh"
STATUS=$?

say "publishing the result"
if [ -d "$BUILDS/ipa" ]; then
  ls -la "$BUILDS/ipa"
  for ipa in "$BUILDS/ipa"/*.ipa; do
    [ -f "$ipa" ] || continue
    if command -v curl >/dev/null 2>&1; then
      curl -fsS -X POST --data-binary "@$ipa" "$SERVER/ios/upload" -o /tmp/supercraftos-upload.log 2>/dev/null \
        && echo "  uploaded $(basename "$ipa")" \
        || echo "  could not reach the build server to upload, the file is at $ipa"
    fi
  done
else
  echo "  no ipa was produced, the build log is in $BUILDS/archive.log"
fi

say "done, status $STATUS"
exit $STATUS
