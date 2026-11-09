#!/bin/bash
# Explicit read-only gateway smoke test. CI must supply the access key as a secret.
set -euo pipefail
: "${SUPERCRAFTOS_TEST_BACKEND:?Set the HTTPS gateway origin}"
: "${SUPERCRAFTOS_TEST_ACCESS_KEY:?Set the gateway key as a CI secret}"
if ! command -v xcodegen >/dev/null 2>&1; then brew install xcodegen; fi
python3 scripts/package_ipad.py
xcodegen generate --spec ios_app_dist/ci_xcode/project.yml
PROJECT="ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj"
# Values are environment variables in an untracked scheme, never build arguments.
# Delete that scheme even if xcodebuild fails. Do not publish its result bundle.
trap 'rm -rf "$PROJECT"' EXIT
python3 - <<'PY'
import os
import xml.etree.ElementTree as ET
from pathlib import Path
path = Path('ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj/xcshareddata/xcschemes/SuperCraftOSBackendTests.xcscheme')
tree = ET.parse(path)
action = tree.getroot().find('TestAction')
action.set('shouldUseLaunchSchemeArgsEnv', 'NO')
variables = action.find('EnvironmentVariables')
if variables is None:
    variables = ET.SubElement(action, 'EnvironmentVariables')
for name, value in {'SUPERCRAFTOS_LIVE_TESTS': '1',
                    'SUPERCRAFTOS_TEST_BACKEND': os.environ['SUPERCRAFTOS_TEST_BACKEND'],
                    'SUPERCRAFTOS_TEST_ACCESS_KEY': os.environ['SUPERCRAFTOS_TEST_ACCESS_KEY']}.items():
    ET.SubElement(variables, 'EnvironmentVariable', key=name, value=value, isEnabled='YES')
path.chmod(0o600)
tree.write(path, encoding='utf-8', xml_declaration=True)
PY
UDID="$(xcrun simctl list devices available -j | python3 -c 'import json,sys; print(next(d["udid"] for ds in json.load(sys.stdin)["devices"].values() for d in ds if "iPhone" in d["name"]))')"
# Keep the explicit live workflow read-only. Mutation coverage always uses fixtures.
xcodebuild test -quiet -project "$PROJECT" -scheme SuperCraftOSBackendTests \
  -configuration Debug -destination "id=$UDID" \
  -only-testing:SuperCraftOSBackendTests/LiveBackendContractTests/testRuntimeStatusDecodes \
  -only-testing:SuperCraftOSBackendTests/LiveBackendContractTests/testToolsDecode \
  -only-testing:SuperCraftOSBackendTests/LiveBackendContractTests/testWorkflowsDecode \
  -only-testing:SuperCraftOSBackendTests/LiveBackendContractTests/testIntegrationsDecode \
  -only-testing:SuperCraftOSBackendTests/LiveBackendContractTests/testRegistrationsDecode \
  -only-testing:SuperCraftOSBackendTests/LiveBackendContractTests/testCapabilitiesDecode \
  -only-testing:SuperCraftOSBackendTests/LiveBackendContractTests/testGrantCatalogDecodes \
  -only-testing:SuperCraftOSBackendTests/LiveBackendContractTests/testQuestSourcesDecode
