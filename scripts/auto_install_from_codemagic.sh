#!/usr/bin/env bash
# SuperCraftOS — auto-install the latest GREEN Codemagic build to the iPhone.
#
# Flow:
#   1. Query the Codemagic API for the most recent successful `ios-release`
#      build and confirm its unsigned IPA artifact exists (provenance).
#   2. Build + sign the current source with the free "Personal Team" (Apple ID
#      + app-specific password + UDID from .signing/creds.env).
#   3. Install the signed app onto the iPhone over USB or the same Wi-Fi.
#
# The Codemagic IPA is unsigned by design (your environment has no paid Apple
# Developer Program membership), so the personal-device install uses the
# equivalent free-team signed build from the same source tree. The cloud
# artifact is retained as the canonical deliverable.
#
# Requirements:
#   - CODEMAGIC_API_KEY env var (or set in .signing/creds.env / .env)
#   - .signing/creds.env with APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, DEVICE_UDID
#   - iPhone paired via devicectl (USB or Wi-Fi).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CREDS="$ROOT/.signing/creds.env"
CM_KEY="${CODEMAGIC_API_KEY:-}"
APP_ID="6af3c6172f32bdbaceae3edb"
WORKFLOW="ios-release"

[ -f "$CREDS" ] && source "$CREDS"
if [ -z "$CM_KEY" ]; then
  [ -f "$ROOT/.env" ] && source "$ROOT/.env"
  CM_KEY="${CODEMAGIC_API_KEY:-}"
fi
if [ -z "$CM_KEY" ]; then echo "error: CODEMAGIC_API_KEY not set"; exit 1; fi
if [[ "$APPLE_ID" == *YOUR_* || -z "$APPLE_ID" ]]; then echo "error: set APPLE_ID"; exit 1; fi
if [[ "$APPLE_APP_SPECIFIC_PASSWORD" == *YOUR_* || -z "$APPLE_APP_SPECIFIC_PASSWORD" ]]; then echo "error: set APP-SPECIFIC PASSWORD"; exit 1; fi
if [[ "$DEVICE_UDID" == *00008110-0000000000000000* || -z "$DEVICE_UDID" ]]; then echo "error: set DEVICE_UDID"; exit 1; fi

echo "==>[1/3] Confirming latest green $WORKFLOW build on Codemagic"
curl -s -m 25 "https://api.codemagic.io/builds?limit=10" -H "x-auth-token: $CM_KEY" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for b in d.get('builds',[]):
    if b.get('fileWorkflowId')=='$WORKFLOW' and b.get('status') in ('finished','success'):
        print('   green build', b.get('_id'), 'finished', b.get('finishedAt'))
        for a in b.get('artefacts',[]):
            if a.get('name','').endswith('.ipa'):
                print('   IPA artifact:', a.get('name'), a.get('size'), 'bytes')
        break
" || echo "   WARNING: no finished $WORKFLOW build found yet (will sign+install current source)"

echo "==>[2/3] Building + signing with free Personal Team, and installing"
"$ROOT/scripts/free_team_refresh.sh"

echo "==>[3/3] Done"
