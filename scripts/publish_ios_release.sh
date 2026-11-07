#!/usr/bin/env bash
# Publish only verified cloud build artifacts; preserve all existing signed apps.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ "${1:-}" != "--publish-only" ]; then
  python3 scripts/build_release_assets.py --out release/ios
fi
python3 scripts/publish_ios_release.py
