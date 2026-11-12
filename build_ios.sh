#!/usr/bin/env bash
# SuperCraftOS core pipeline. Runs on the VPS, before anything is pushed to the
# Mac build client.
#
#   build_ios.sh            validate, test, commit and push
#   build_ios.sh --no-push  validate and test only
#   build_ios.sh --message "..."   commit with a specific message
#
# The Mac is the build client for the signed device archive. This script never
# touches it directly; scripts/mac_build.sh does that over the reverse tunnel.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PUSH=1
MESSAGE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --no-push) PUSH=0; shift ;;
    --message) MESSAGE="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

say "regenerating the iPad transfer bundle"
.venv/bin/python scripts/package_ipad.py

say "portable Swift contract tests"
export SUPERCRAFTOS_CLI_BINARY="$(swift build --package-path swift-verification --show-bin-path)/supercraftos-check"
swift test --package-path swift-verification

say "python test suite"
.venv/bin/python -m unittest -q \
  test_verify_ios_artifacts.py test_package_ipa.py test_xcode_project.py \
  test_control_center.py test_bitrise_monitor.py test_grant_registry.py test_grants.py \
  test_ios_udid_capture.py test_ios_sign_service.py test_supercraftos_installer.py test_ios_backend_contract.py

say "checking the delivery"
.venv/bin/python scripts/verify_delivery.py

say "checking the project against Apple's own documentation"
.venv/bin/python scripts/verify_apple_rules.py

say "regenerating the app icon set"
.venv/bin/python scripts/generate_app_icons.py

say "verifying the Xcode project spec"
.venv/bin/python - <<'PY'
import yaml
with open("ios_app_dist/ci_xcode/project.yml") as handle:
    spec = yaml.safe_load(handle)
targets = set(spec["targets"])
required = {"SuperCraftOS", "SuperCraftOSKeyboard", "SuperCraftOSTests"}
missing = required - targets
if missing:
    raise SystemExit(f"the Xcode project spec is missing targets: {sorted(missing)}")
print("targets:", ", ".join(sorted(targets)))
print("schemes:", ", ".join(sorted(spec["schemes"])))
PY

if [ "$PUSH" = 0 ]; then
  say "skipping the commit"
  exit 0
fi

if git diff --quiet && git diff --cached --quiet; then
  say "nothing to commit"
  exit 0
fi

say "committing"
git add -A
if [ -n "$MESSAGE" ]; then
  git commit -m "$MESSAGE"
else
  git commit -m "Update the iOS app and keyboard extension"
fi

say "pushing to master"
git push origin master

say "done"
echo "The signed device archive is built on the Mac client:"
echo "  scripts/mac_build.sh"
