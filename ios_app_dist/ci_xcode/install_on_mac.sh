#!/bin/bash
# Sign SuperCraftOS with your Apple ID and install it on the connected iPhone
# or iPad. This runs ON THE MAC.
#
#   curl -fsSL https://agent.commetai.ca/ios/install_on_mac.sh | bash
#
# The app itself is built, tested and archived on the build server with the
# current Xcode. This script only fetches that finished bundle, signs it with
# your Apple ID, and installs it.
#
# Nothing is compiled here, so no Xcode is required, and nothing is written to
# the internal disk.
set -euo pipefail

SERVER='https://agent.commetai.ca/ios'
WORK="${SUPERCRAFTOS_WORK:-/Volumes/EAGET/builds}"
BUNDLE='SuperCraftOS-iOS-Device-unsigned.ipa'
KEYBOARD_BUNDLE='SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa'
WITH_KEYBOARD=0
[ "${1:-}" = "--with-keyboard" ] && WITH_KEYBOARD=1

say() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

say "working out where to put things"
if [ -d /Volumes/EAGET ]; then
  mkdir -p "$WORK"
  echo "  $WORK (on the external volume)"
else
  WORK="$HOME/Downloads/supercraftos"
  mkdir -p "$WORK"
  echo "  $WORK (the external volume is not mounted)"
fi

say "finding the connected device"
UDID=""
if command -v idevice_id >/dev/null 2>&1; then
  UDID="$(idevice_id -l 2>/dev/null | head -1)"
fi
if [ -z "$UDID" ] && command -v xcrun >/dev/null 2>&1; then
  UDID="$(xcrun devicectl list devices 2>/dev/null | grep -oE '[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}' | head -1)"
fi
if [ -n "$UDID" ]; then
  echo "  device $UDID"
else
  echo "  no device detected, continuing anyway"
fi

say "fetching the bundle"
if [ "$WITH_KEYBOARD" = 1 ]; then
  TARGET="$KEYBOARD_BUNDLE"
  echo "  the app and the custom keyboard"
else
  TARGET="$BUNDLE"
  echo "  the app on its own"
fi
curl -fL --progress-bar -o "$WORK/$TARGET" "$SERVER/$TARGET"
ls -la "$WORK/$TARGET"

say "deciding how to sign it"
# 1. A certificate the user already has. This is the fully scriptable path.
if [ -n "${SUPERCRAFTOS_P12:-}" ] && [ -n "${SUPERCRAFTOS_PROFILE:-}" ] && command -v zsign >/dev/null 2>&1; then
  echo "  signing with your certificate"
  zsign -k "$SUPERCRAFTOS_P12" -m "$SUPERCRAFTOS_PROFILE" -o "$WORK/signed.ipa" "$WORK/$TARGET"
  if command -v ideviceinstaller >/dev/null 2>&1; then
    ideviceinstaller -i "$WORK/signed.ipa"
    echo "  installed"
    exit 0
  fi
fi

# 2. iloader. It signs with a free Apple ID and installs, with no Xcode.
for candidate in \
  "/Applications/iloader.app" \
  "$HOME/Applications/iloader.app" \
  "/Volumes/EAGET/Applications/iloader.app"; do
  if [ -d "$candidate" ]; then
    echo "  handing the bundle to iloader"
    open -a "$candidate" "$WORK/$TARGET"
    cat <<EOF

  iloader is open with the bundle loaded.

    1. sign in with the Apple ID for THIS device
    2. press Install
    3. when it is done, the app is on the device

  If you want SideStore as well, choose "Install SideStore" in iloader first.
  SideStore re-signs the app in the background over Wi-Fi every 7 days, so you
  never have to do this again.

EOF
    exit 0
  fi
done

cat <<EOF
  No signing tool was found on this Mac.

  The simplest option, and it needs no Xcode and almost no disk:

    1. download iloader for macOS
         https://github.com/nab138/iloader/releases/latest
    2. drag it into Applications, or into /Volumes/EAGET/Applications
    3. run this script again

  Sideloadly works too and is a single app:
    https://sideloadly.io
  Drop the bundle onto it, enter your Apple ID, press Start.

  The bundle is already here:
    $WORK/$TARGET

  If you have a .p12 certificate and a .mobileprovision profile, set
  SUPERCRAFTOS_P12 and SUPERCRAFTOS_PROFILE and this script will sign and
  install with no interaction at all.
EOF
