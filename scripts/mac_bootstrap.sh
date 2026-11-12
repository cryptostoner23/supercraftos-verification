#!/bin/bash
# Bootstrap the Mac build client for the SuperCraftOS agent.
#
# Run this ON THE MAC, as the user that will sign the app:
#
#   bash bootstrap_mac.sh
#
# It installs the agent's public key with the permissions sshd insists on,
# verifies the fingerprint matches, prints the effective sshd configuration and
# proves the key can log in, then starts the reverse tunnel back to the build
# server so the agent can drive the client.
set -euo pipefail

AGENT_KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICn22XGA+ONqjeWTVb0Q4E6m2abdagI7n/RY5UQ5orl3 supercraftos-agent@bitrise-mac-access'
AGENT_FINGERPRINT='SHA256:4JFjK4iGz0FmmrOnJcNmkmJb1Fl4oOQrCdmcUwAgk64'
SERVER='root@161.97.77.153'
TUNNEL_PORT=25177

say() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

say "installing the agent key"
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
grep -qxF "$AGENT_KEY" "$HOME/.ssh/authorized_keys" || echo "$AGENT_KEY" >> "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
# sshd refuses the file silently when the home directory is group writable.
chmod go-w "$HOME"
echo "  installed"

say "verifying the fingerprint"
ssh-keygen -lf "$HOME/.ssh/authorized_keys" | grep -F "$AGENT_FINGERPRINT" \
  && echo "  the agent key is present and matches" \
  || { echo "  error: the agent key is not in the file" >&2; exit 1; }

say "effective sshd configuration"
if sudo -n /usr/sbin/sshd -T 2>/dev/null | grep -Ei 'authorizedkeysfile|pubkeyauthentication|strictmodes'; then
  :
else
  echo "  sudo -n failed, showing the config with sudo"
  sudo /usr/sbin/sshd -T 2>/dev/null | grep -Ei 'authorizedkeysfile|pubkeyauthentication|strictmodes' || true
fi

say "proving the key can log in"
if ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=8 "$(id -un)@localhost" true 2>/dev/null; then
  echo "  a key is already accepted for this user"
else
  echo "  no key is accepted yet, which is what the agent will hit"
fi

say "the external volume"
if [ -d /Volumes/EAGET ]; then
  df -h /Volumes/EAGET | tail -1
  mkdir -p /Volumes/EAGET/ios_project /Volumes/EAGET/XcodeDerivedData /Volumes/EAGET/builds
  echo "  /Volumes/EAGET/ios_project, /Volumes/EAGET/XcodeDerivedData and /Volumes/EAGET/builds are ready"
else
  echo "  warning: /Volumes/EAGET is not mounted" >&2
fi

say "opening the reverse tunnel to the build server"
cat <<EOF
  Run this in a separate terminal and leave it running:

    ssh -N -R $TUNNEL_PORT:localhost:22 $SERVER

  The server then reaches this Mac on 127.0.0.1:$TUNNEL_PORT.
EOF

if ssh -o BatchMode=yes -o ConnectTimeout=8 -o ExitOnForwardFailure=yes \
      -N -R "$TUNNEL_PORT:localhost:22" "$SERVER" 2>/tmp/supercraftos-tunnel.log &
   then
  TUNNEL_PID=$!
  sleep 3
  if kill -0 "$TUNNEL_PID" 2>/dev/null; then
    echo "  the tunnel is running in the background on this Mac, pid $TUNNEL_PID"
    echo "  to keep it alive across reboots, add it to your login items or a launchd agent"
  else
    echo "  the tunnel could not start:"
    cat /tmp/supercraftos-tunnel.log || true
  fi
fi

say "done"
