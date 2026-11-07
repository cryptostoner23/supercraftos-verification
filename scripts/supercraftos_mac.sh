#!/usr/bin/env bash
# SuperCraftOS for the Mac: find the iPad, sign for it, install it.
#
#   curl -fsSL https://agent.commetai.ca/ios/supercraftos-mac.sh | bash
#
# Everything happens on this Mac. The iPad or iPhone has to be connected, by
# cable or by Wi-Fi if it has already been paired. The script finds it, asks
# the server to sign for it, and installs the signed app.
#
# If this Mac has signed before, the Apple session is cached in
# ~/.supercraftos/session and neither a password nor a code is asked for.
# The session can also be copied to the build server, which then signs on its
# own from then on.
#
# The password is typed here, with the echo off, and goes straight to Apple.
set -uo pipefail

BASE="${SUPERCRAFTOS_BASE:-https://agent.commetai.ca}"
WORK="${SUPERCRAFTOS_WORK:-$HOME/.supercraftos}"
SESSION_DIR="$WORK/session"
ACCOUNTS=(
  "harjeev_kohli@hotmail.com"
  "cryptostoner94@icloud.com"
  "cryptostoner@iloud.com"
  "ngboy69@hotmail.com"
)
KEEP=0

say()  { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
die()  { printf '\n\033[31merror: %s\033[0m\n\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

# Reads a line for the user. The terminal when there is one, because the
# script is normally piped in and stdin is the script itself.
ask() {
  local prompt="$1" name="$2" answer=""
  if [ -r /dev/tty ] && [ -z "${SUPERCRAFTOS_READ_STDIN:-}" ]; then
    IFS= read -r -p "$prompt" answer < /dev/tty
  else
    IFS= read -r -p "$prompt" answer
  fi
  printf -v "$name" '%s' "$answer"
}

# Reads a secret: no echo, ever.
ask_secret() {
  local prompt="$1" name="$2" answer=""
  if [ -r /dev/tty ] && [ -z "${SUPERCRAFTOS_READ_STDIN:-}" ]; then
    IFS= read -rs -p "$prompt" answer < /dev/tty
    echo
  else
    IFS= read -rs -p "$prompt" answer
    echo
  fi
  printf -v "$name" '%s' "$answer"
}


mkdir -p "$SESSION_DIR" && chmod 700 "$WORK" "$SESSION_DIR"

# ------------------------------------------------------------- the devices

# Every iOS device this Mac can reach, connected or over Wi-Fi.
list_devices() {
  have idevice_id || return 1
  idevice_id -l 2>/dev/null
}

# The connection type of a device: "USB" or "WiFi".
connection_type() {
  have ideviceinfo || { printf 'USB'; return; }
  ideviceinfo -u "$1" -k ConnectionType 2>/dev/null | head -1
}

device_name() {
  have idevicename || { printf 'device'; return; }
  idevicename -u "$1" 2>/dev/null | head -1
}

# The iOS version of a device, which decides whether the keyboard fits.
ios_version() {
  have ideviceinfo || return 1
  ideviceinfo -u "$1" -k ProductVersion 2>/dev/null | head -1
}

# ------------------------------------------------------------------ the run

say "SuperCraftOS on this Mac"
info "server $BASE"

if ! have idevice_id; then
  info "libimobiledevice is not installed, so the device cannot be found"
  info "install it with:  brew install libimobiledevice"
  die "no device tooling on this Mac"
fi

say "looking for a device"
DEVICES="$(list_devices)"
if [ -z "$DEVICES" ]; then
  die "no iPhone or iPad found. Connect one by cable, or turn on Wireless Access for one that is already paired, then run this again."
fi

# Prefer a device that is already over Wi-Fi: that is the wireless install.
UDID=""
PICK=""
for candidate in $DEVICES; do
  kind="$(connection_type "$candidate")"
  info "found $candidate  ${kind:-unknown}  $(device_name "$candidate")"
  if [ "$kind" = "WiFi" ]; then PICK="$candidate"; break; fi
  [ -z "$PICK" ] && PICK="$candidate"
done
UDID="$PICK"
[ -n "$UDID" ] || die "the devices could not be read"

VERSION="$(ios_version "$UDID" || true)"
if [ -n "$VERSION" ]; then
  MAJOR="${VERSION%%.*}"
  info "this device runs iOS $VERSION"
fi

# Which build this device can install.
BUILD="${SUPERCRAFTOS_BUILD:-}"
if [ -z "$BUILD" ]; then
  BUILD="app"
  if [ -n "$MAJOR" ] && [ "$MAJOR" -ge 26 ] 2>/dev/null; then BUILD="keyboard"; fi
fi
if [ "$BUILD" = "keyboard" ]; then
  say "the app with the keyboard, which needs iOS 26 or later"
else
  say "the app on its own, which runs on iOS 17 and later"
  info "the keyboard needs iOS 26, so it is left out unless this device can run it"
fi

# ------------------------------------------------------------- the signer

# The signer that runs here. It caches the Apple session, so after the first
# time there is no password and no code.
SIGNER="${SUPERCRAFTOS_SIGNER:-$HOME/.supercraftos/sign-for-devices}"
if [ ! -x "$SIGNER" ]; then
  say "fetching the signing tool"
  if ! curl -fSL --max-time 180 -o "$SIGNER" "$BASE/ios/sign-for-devices" ; then
    die "the signing tool could not be fetched"
  fi
  chmod +x "$SIGNER"
fi
info "signer $SIGNER"

ACCOUNT="${SUPERCRAFTOS_APPLE_ID:-}"
if [ -z "$ACCOUNT" ]; then
  say "which Apple ID"
  for index in "${!ACCOUNTS[@]}"; do
    printf '    %d) %s\n' "$((index + 1))" "${ACCOUNTS[$index]}"
  done
  printf '    5) a different one\n'
  ask "    choice: " choice
  case "$choice" in
    1) ACCOUNT="${ACCOUNTS[0]}" ;;
    2) ACCOUNT="${ACCOUNTS[1]}" ;;
    3) ACCOUNT="${ACCOUNTS[2]}" ;;
    4) ACCOUNT="${ACCOUNTS[3]}" ;;
    5) ask "    Apple ID: " ACCOUNT ;;
    *) die "that is not one of the choices" ;;
  esac
fi
info "signing as $ACCOUNT"

# The session may already be cached, in which case nothing is asked for.
CACHED=0
if [ -n "$(ls -A "$SESSION_DIR" 2>/dev/null)" ]; then
  CACHED=1
  info "a cached Apple session is present, so no password and no code are needed"
fi

PASSWORD=""
if [ "$CACHED" = "0" ]; then
  printf '    App specific password for %s: ' "$ACCOUNT"
  if [ -r /dev/tty ] && [ -z "${SUPERCRAFTOS_READ_STDIN:-}" ]; then
    IFS= read -rs PASSWORD < /dev/tty
    echo
  else
    IFS= read -rs PASSWORD
    echo
  fi
  [ -n "$PASSWORD" ] || die "the password was empty"
fi

say "signing"
set +e
OUTPUT="$(SUPERCRAFTOS_APPLE_PASSWORD="$PASSWORD" "$SIGNER" \
  --apple-id "$ACCOUNT" \
  --udid "$UDID:$(device_name "$UDID")" \
  --storage "$SESSION_DIR" \
  --app "$BASE/ios/SuperCraftOS-iOS-Device-$([ "$BUILD" = keyboard ] && echo WithKeyboard- || echo "")unsigned.ipa" \
  --out "$WORK/signed-$BUILD.ipa" 2>&1 <<< "${SUPERCRAFTOS_2FA:-}")"
STATUS=$?
set -e
unset PASSWORD
PASSWORD=""

if [ "$STATUS" != "0" ] || [ ! -f "$WORK/signed-$BUILD.ipa" ]; then
  printf '%s\n' "$OUTPUT" | tail -12 | sed 's/^/    /'
  die "the signing did not finish"
fi
info "signed $(ls -l "$WORK/signed-$BUILD.ipa" | awk '{print $5}') bytes"

# ------------------------------------------------------------ the handover

# The cached session can be handed to the build server, which then signs for
# this account on its own, with no password and no code, for as long as the
# session is valid. It is the user's own account, on the user's own server.
offer_session() {
  [ -d "$SESSION_DIR" ] || return 0
  local files
  files="$(ls -1 "$SESSION_DIR" 2>/dev/null)"
  [ -n "$files" ] || return 0
  printf '    Hand the cached session to the build server so it can sign on its own? [y/N] '
  local answer=""
  if [ -r /dev/tty ] && [ -z "${SUPERCRAFTOS_READ_STDIN:-}" ]; then
    IFS= read -r answer < /dev/tty
  else
    IFS= read -r answer
  fi
  case "$answer" in
    y|Y|yes|YES) ;;
    *) return 0 ;;
  esac
  for file in $files; do
    local payload
    payload="$(base64 < "$SESSION_DIR/$file" 2>/dev/null | tr -d '\n')"
    [ -n "$payload" ] || continue
    if curl -fsS --max-time 60 -X POST \
         --data-urlencode "name=$file" --data-urlencode "data=$payload" \
         "$BASE/ios/sign/session" >/dev/null; then
      info "the session for $file was handed over"
    else
      info "the session for $file could not be handed over"
    fi
  done
}

# ----------------------------------------------------------------- install

say "installing on the device"
if ! have ideviceinstaller; then
  info "ideviceinstaller is not installed, so the file is left for you"
  info "install it with:  brew install libimobiledevice"
  printf '\n    The signed app is at %s\n' "$WORK/signed-$BUILD.ipa"
  printf '    Send it to the device and open it with SideStore.\n\n'
  exit 0
fi

if ideviceinstaller -u "$UDID" -i "$WORK/signed-$BUILD.ipa" 2>&1 | sed 's/^/    /'; then
  printf '\n\033[1;32mInstalled.\033[0m\n'
  printf '    Settings, General, Keyboard, Keyboards, Add New Keyboard, SuperCraftOS,\n'
  printf '    and turn on Allow Full Access, which Apple requires for any keyboard that\n'
  printf '    reaches the network.\n\n'
  printf '    The session is cached in %s, so the next time nothing is asked for.\n\n' "$SESSION_DIR"
  offer_session
  exit 0
fi

printf '\n\033[33mThe install did not go through.\033[0m\n'
printf '    The signed app is at %s\n' "$WORK/signed-$BUILD.ipa"
printf '    Send it to the device and open it with SideStore, or check that the\n'
printf '    device is unlocked and that this Mac is trusted by it.\n\n'
KEEP=1
exit 0
