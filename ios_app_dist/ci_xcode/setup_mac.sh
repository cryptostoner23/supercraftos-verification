#!/bin/bash
# One command setup for the SuperCraftOS Mac build client.
#
#   curl -fsSL https://agent.commetai.ca/ios/setup_mac.sh | bash
#
# Pass arguments through a pipe with:  bash -s -- --app-only
#
# It does everything, in this order:
#
#   1. reports the machine: macOS, Xcode, the external volume, the free disk
#   2. installs the build server's public key with the permissions sshd insists
#      on, so the build server can drive this Mac
#   3. opens the reverse SSH tunnel back to the build server on port 25177
#   4. downloads iloader onto the external volume, so no Xcode is needed
#   5. downloads the prebuilt app bundle and opens it in iloader
#
# Nothing is written to the internal disk except iloader, which is small.
# The app is built, tested and archived on the build server with the current
# Xcode. This machine only signs and installs.
set -uo pipefail

AGENT_KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICn22XGA+ONqjeWTVb0Q4E6m2abdagI7n/RY5UQ5orl3 supercraftos-agent@bitrise-mac-access'
AGENT_FINGERPRINT='SHA256:4JFjK4iGz0FmmrOnJcNmkmJb1Fl4oOQrCdmcUwAgk64'
SERVER='root@161.97.77.153'
TUNNEL_PORT=25177
SERVER_BASE='https://agent.commetai.ca/ios'
VOLUME='/Volumes/EAGET'
WORK="$VOLUME/builds"
ILoader_VERSION='v2.3.10'
ILoader_DMG="https://github.com/nab138/iloader/releases/download/$ILoader_VERSION/iloader-darwin-universal.dmg"

say() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

say "1. this machine"
echo "  hostname : $(hostname)"
echo "  macOS    : $(sw_vers -productVersion) ($(sw_vers -buildVersion))"
echo "  chip     : $(uname -m)"
if xcode-select -p >/dev/null 2>&1 && [ -d "$(xcode-select -p)/Xcode.app" ]; then
  echo "  xcode    : $(xcodebuild -version | head -1)"
else
  echo "  xcode    : not installed, only the command line tools"
  echo "             the newest Xcode that runs on this macOS is 14.2, and it"
  echo "             cannot build this project, so none is needed here"
fi
echo "  internal disk:"
df -h / | tail -1 | sed 's/^/    /'
if [ -d "$VOLUME" ]; then
  echo "  external volume:"
  df -h "$VOLUME" | tail -1 | sed 's/^/    /'
  mkdir -p "$VOLUME/builds" "$VOLUME/ios_project" "$VOLUME/XcodeDerivedData" "$VOLUME/Applications"
else
  echo "  external volume: $VOLUME is not mounted"
  WORK="$HOME/Downloads/supercraftos"
  mkdir -p "$WORK"
fi

say "2. installing the build server key"
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
grep -qxF "$AGENT_KEY" "$HOME/.ssh/authorized_keys" || echo "$AGENT_KEY" >> "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
# sshd silently ignores an authorised keys file when the home directory or the
# file is group writable, which is the usual reason a key is refused.
chmod go-w "$HOME"
if ssh-keygen -lf "$HOME/.ssh/authorized_keys" | grep -qF "$AGENT_FINGERPRINT"; then
  echo "  the key is installed and the fingerprint matches"
else
  echo "  error: the key did not install" >&2
fi
if ssh -o BatchMode=yes -o ConnectTimeout=8 "$(id -un)@localhost" true 2>/dev/null; then
  echo "  the key can already log in"
else
  echo "  the key is installed; the server will use it through the tunnel"
fi

say "2b. enabling Tailscale SSH on this machine"
# The App Store GUI build of Tailscale cannot run the Tailscale SSH server. The
# open source tailscaled can, but it is driven by its own CLI, which is not the
# one the GUI app puts on the PATH. Find a CLI that can actually advertise SSH.
TS_CLI=""
for candidate in /opt/homebrew/bin/tailscale /usr/local/bin/tailscale "$(command -v tailscale 2>/dev/null)"; do
  [ -n "$candidate" ] && [ -x "$candidate" ] || continue
  if "$candidate" set --ssh >/tmp/supercraftos-ts-ssh.log 2>&1 && ! grep -qi "sandboxed" /tmp/supercraftos-ts-ssh.log; then
    TS_CLI="$candidate"
    echo "  enabled with $candidate"
    break
  fi
done
if [ -z "$TS_CLI" ]; then
  echo "  no CLI here can advertise Tailscale SSH"
  echo "  the open source build is at /usr/local/bin/tailscale or"
  echo "  /opt/homebrew/bin/tailscale if it is installed alongside the app"
fi

say "3. opening the reverse tunnel to the build server"
# The build server reaches this Mac on 127.0.0.1:$TUNNEL_PORT. The tunnel is
# opened from here, because the build server cannot dial in.
TUNNEL_OPEN=0
if ssh -o BatchMode=yes -o ConnectTimeout=8 "$SERVER" true 2>/dev/null; then
  nohup ssh -N -R "$TUNNEL_PORT:localhost:22" -o ExitOnForwardFailure=yes \
       -o ServerAliveInterval=30 -o ServerAliveCountMax=6 "$SERVER" \
       >/tmp/supercraftos-tunnel.log 2>&1 &
  sleep 3
  if nc -z 127.0.0.1 "$TUNNEL_PORT" 2>/dev/null; then
    echo "  the tunnel is open on 127.0.0.1:$TUNNEL_PORT"
    TUNNEL_OPEN=1
  fi
elif [ -n "$TS_CLI" ] && "$TS_CLI" status >/dev/null 2>&1; then
  # The tailnet is the fallback route to the build server.
  nohup "$TS_CLI" ssh -N -R "$TUNNEL_PORT:localhost:22" root@vmi3563685 \
       >/tmp/supercraftos-tunnel.log 2>&1 &
  sleep 4
  if nc -z 127.0.0.1 "$TUNNEL_PORT" 2>/dev/null; then
    echo "  the tunnel is open on 127.0.0.1:$TUNNEL_PORT over the tailnet"
    TUNNEL_OPEN=1
  fi
fi
if [ "$TUNNEL_OPEN" = 0 ]; then
  echo "  the tunnel did not come up"
  echo "  this machine has to be able to reach $SERVER over ssh, or the tailnet"
  echo "  see /tmp/supercraftos-tunnel.log"
fi

say "3b. proving the tunnel carries an ssh session"
if ssh -p "$TUNNEL_PORT" -o BatchMode=yes -o ConnectTimeout=8 \
     -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
     "$(id -un)@127.0.0.1" true 2>/dev/null; then
  echo "  the tunnel carries a session, so the build server can drive this Mac"
else
  echo "  the tunnel is not carrying a session yet"
fi

say "4. installing iloader onto the external volume"
APP_DIR="$VOLUME/Applications"
[ -d "$VOLUME" ] || APP_DIR="$HOME/Applications"
mkdir -p "$APP_DIR"
if [ -d "$APP_DIR/iloader.app" ]; then
  echo "  iloader is already installed"
else
  DMG="/tmp/iloader.dmg"
  MOUNT="/tmp/iloader_mount"
  if curl -fL --progress-bar -o "$DMG" "$ILoader_DMG"; then
    hdiutil attach "$DMG" -nobrowse -quiet -mountpoint "$MOUNT" 2>/dev/null
    if [ -d "$MOUNT" ]; then
      cp -R "$MOUNT/iloader.app" "$APP_DIR/" 2>/dev/null || cp -R "$MOUNT"/*.app "$APP_DIR/" 2>/dev/null
      hdiutil detach "$MOUNT" -quiet 2>/dev/null
      echo "  iloader is in $APP_DIR"
    else
      echo "  could not mount the disk image, install it manually"
    fi
  else
    echo "  could not download iloader, install it manually"
  fi
  rm -f "$DMG"
fi

say "5. fetching the app bundle"
# The full build, with the custom keyboard embedded, is the default. The app
# and the keyboard extension are separate registrations, so the app only build
# is one App ID instead of two.
BUNDLE='SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa'
[ "${1:-}" = "--app-only" ] && BUNDLE='SuperCraftOS-iOS-Device-unsigned.ipa'
curl -fL --progress-bar -o "$WORK/$BUNDLE" "$SERVER_BASE/$BUNDLE"
ls -la "$WORK/$BUNDLE"

if [ -d "$APP_DIR/iloader.app" ]; then
  say "6. opening the bundle in iloader"
  open -a "$APP_DIR/iloader.app" "$WORK/$BUNDLE"
  cat <<EOF

  iloader is open with the bundle loaded.

    1. sign in with the Apple ID for this device
    2. press Install
    3. the app is on the device

  To keep it alive, choose "Install SideStore" in iloader first. SideStore
  re-signs the app in the background over Wi-Fi every 7 days.

  The build server can now reach this Mac on 127.0.0.1:$TUNNEL_PORT, so it
  can drive the build and the install itself from here on.

EOF
fi
