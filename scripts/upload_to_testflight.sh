#!/bin/bash
# Upload a SuperCraftOS IPA to App Store Connect, where it becomes available in
# TestFlight.
#
#   scripts/upload_to_testflight.sh path/to/SuperCraftOS.ipa
#
# Credentials come from the environment:
#   ASC_API_KEY_PATH   path to the App Store Connect API key (.p8)
#   ASC_API_KEY_ID     the key identifier
#   ASC_API_ISSUER_ID  the issuer identifier
#
# Or from a Bitrise secret of the same name. Never put the key in the
# repository, in a log, or in a Lark message.
set -euo pipefail

IPA="${1:-}"
if [ -z "$IPA" ] || [ ! -f "$IPA" ]; then
  echo "usage: $0 path/to/SuperCraftOS.ipa" >&2
  exit 2
fi

: "${ASC_API_KEY_ID:?ASC_API_KEY_ID is required}"
: "${ASC_API_ISSUER_ID:?ASC_API_ISSUER_ID is required}"
if [ -z "${ASC_API_KEY_PATH:-}" ] || [ ! -f "${ASC_API_KEY_PATH:-}" ]; then
  echo "error: ASC_API_KEY_PATH must point at the App Store Connect .p8 key" >&2
  exit 2
fi

echo "==> uploading $(basename "$IPA") to App Store Connect"

if xcrun altool --help >/dev/null 2>&1; then
  xcrun altool --upload-app -f "$IPA" -t ios \
    --apiKey "$ASC_API_KEY_ID" --apiIssuer "$ASC_API_ISSUER_ID"
  echo "==> uploaded; the build appears in TestFlight once Apple processes it"
  exit 0
fi

echo "==> altool unavailable, falling back to iTMSTransporter"
xcrun iTMSTransporter -m upload \
  -assetFile "$IPA" \
  -apiKey "$ASC_API_KEY_ID" \
  -apiIssuer "$ASC_API_ISSUER_ID"
echo "==> uploaded; the build appears in TestFlight once Apple processes it"
