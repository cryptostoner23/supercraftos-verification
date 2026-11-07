#!/usr/bin/env bash
# Drive the Mac build client from the VPS.
#
#   scripts/mac_build.sh                 sync, quarantine clear, headless build
#   scripts/mac_build.sh --install       also install on the connected device
#   scripts/mac_build.sh --pull-only     just sync the code
#   scripts/mac_build.sh --check         report the connection and exit
#
# Two routes are tried, in order:
#   1. the Tailscale tailnet, if the Mac is online there
#   2. the reverse SSH tunnel the Mac opens back to this server on port 25177
#
# The Mac is reached as user hsk with the dedicated key, so no credential other
# than the key is ever exchanged.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TUNNEL_PORT="${MAC_TUNNEL_PORT:-25177}"
MAC_USER="${MAC_USER:-hsk}"
IDENTITY="${MAC_IDENTITY:-$HOME/.ssh/id_ed25519_mac}"
STAGING="/Volumes/EAGET/ios_project"
DERIVED="/Volumes/EAGET/XcodeDerivedData"
BUILDS="/Volumes/EAGET/builds"
TAILNET_HOSTS="${MAC_TAILNET_HOSTS:-100.75.232.99 100.113.224.99 100.95.189.57}"

PULL_ONLY=0
INSTALL=0
CHECK_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --pull-only) PULL_ONLY=1; shift ;;
    --install) INSTALL=1; shift ;;
    --check) CHECK_ONLY=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

# The tunnel is tried first because it is always available when it is running.
HOST=""
ROUTE=""
if timeout 5 bash -c "cat < /dev/null > /dev/tcp/127.0.0.1/$TUNNEL_PORT" 2>/dev/null; then
  HOST="127.0.0.1"; PORT="$TUNNEL_PORT"; ROUTE="reverse tunnel on $TUNNEL_PORT"
fi
if [ -z "$HOST" ]; then
  for candidate in $TAILNET_HOSTS; do
    if timeout 5 bash -c "cat < /dev/null > /dev/tcp/$candidate/22" 2>/dev/null; then
      HOST="$candidate"; PORT=22; ROUTE="tailscale $candidate"
      break
    fi
  done
fi

if [ -z "$HOST" ]; then
  cat >&2 <<EOF
error: the Mac build client is not reachable.

Either turn Tailscale on for the Mac, or open the reverse tunnel from the Mac:

  ssh -N -R $TUNNEL_PORT:localhost:22 root@161.97.77.153

then run this again.
EOF
  exit 1
fi

# Every way in, tried in order. The first that works wins.
attempt() {
  if [ "$1" = "tailscale" ]; then
    command -v tailscale >/dev/null 2>&1 || return 1
    tailscale ssh "$MAC_USER@$HOST" 'echo connected' >/dev/null 2>&1 || return 1
    SSH=(tailscale ssh "$MAC_USER@$HOST")
  else
    local key="$2"
    [ -f "$key" ] || return 1
    ssh -p "$PORT" -i "$key" -o IdentitiesOnly=yes \
        -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$HOME/.ssh/known_hosts" \
        -o ConnectTimeout=10 -o BatchMode=yes \
        "$MAC_USER@$HOST" 'echo connected' >/dev/null 2>&1 || return 1
    SSH=(ssh -p "$PORT" -i "$key" -o IdentitiesOnly=yes
         -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$HOME/.ssh/known_hosts"
         -o ConnectTimeout=10 -o BatchMode=yes
         "$MAC_USER@$HOST")
  fi
  return 0
}

say "route: $ROUTE"
if ! attempt tailscale "" && ! attempt key "$IDENTITY" && ! attempt key "$HOME/.ssh/id_ed25519"; then
  cat >&2 <<EOF
error: the route is open but the login was refused for $MAC_USER.

The simplest fix is to let Tailscale handle the authentication, which needs no
key and no permissions. On the Mac, run:

  sudo tailscale set --ssh=true

If the tailnet policy blocks it, add an SSH rule at
https://login.tailscale.com/admin/acls:

  {"action": "accept", "src": ["autogroup:member"], "dst": ["autogroup:member"], "ssh": ["*"]}

If you would rather use a key, run this on the Mac instead. It installs the
key with the permissions sshd insists on and verifies the fingerprint:

  curl -fsSL https://raw.githubusercontent.com/cryptostoner94/SuperCraftOS/master/scripts/mac_bootstrap.sh | bash

The key fingerprint is SHA256:4JFjK4iGz0FmmrOnJcNmkmJb1Fl4oOQrCdmcUwAgk64
EOF
  exit 1
fi

say "verifying the client and the external volume"
"${SSH[@]}" 'set -e
  echo "  connected as $(whoami) on $(hostname)"
  echo "  macOS $(sw_vers -productVersion) on $(uname -m)"
  if [ ! -d /Volumes/EAGET ]; then
    echo "  error: /Volumes/EAGET is not mounted" >&2
    exit 1
  fi
  df -h /Volumes/EAGET | tail -1
  xcodebuild -version | head -1
'

if [ "$CHECK_ONLY" = 1 ]; then
  say "check complete"
  exit 0
fi

say "syncing the code down"
"${SSH[@]}" "set -e
  cd '$STAGING'
  git pull --ff-only origin master
  git log --oneline -1
"

say "clearing the macOS quarantine flags"
"${SSH[@]}" "set -e
  cd '$STAGING'
  xattr -dr com.apple.quarantine . 2>/dev/null || true
  xattr -cr . 2>/dev/null || true
  echo '  quarantine cleared'
"

if [ "$PULL_ONLY" = 1 ]; then
  say "synced"
  exit 0
fi

say "installing the headless build wrapper on the external volume"
"${SSH[@]}" "set -e
  cd '$STAGING'
  cp ios_app_dist/ci_xcode/headless_compile.sh '$STAGING/headless_compile.sh'
  chmod +x '$STAGING/headless_compile.sh'
  xattr -d com.apple.quarantine '$STAGING/headless_compile.sh' 2>/dev/null || true
  echo '  wrapper in place'
"

say "firing the headless build on the Mac"
"${SSH[@]}" "set -e
  cd '$STAGING'
  ./headless_compile.sh
"

if [ "$INSTALL" = 1 ]; then
  say "installing on the connected device"
  "${SSH[@]}" "set -e
    IPA=\$(ls -1 '$BUILDS/ipa'/*.ipa 2>/dev/null | head -1)
    if [ -z \"\$IPA\" ]; then echo '  no ipa was produced' >&2; exit 1; fi
    xcrun devicectl list devices
    xcrun devicectl device install app \"\$IPA\"
  "
  say "fetching the signed ipa back to this server"
  mkdir -p "$ROOT/release/ios"
  scp -P "$PORT" -i "$IDENTITY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
      "$MAC_USER@$HOST:/Volumes/EAGET/builds/ipa/*.ipa" "$ROOT/release/ios/" 2>/dev/null || true
  ls -la "$ROOT/release/ios" || true
fi

say "done"
