---
name: bitrise-skill
description: Build, sign, test, and export an iOS IPA on Bitrise CI/CD — from XcodeGen spec to signed/unsigned IPA, with code signing, secrets, workflows, and POV acceptance. Use when a task involves Bitrise builds, iOS code signing, bitrise.yml workflows, or CI/CD delivery on Bitrise.
---

# Bitrise Skill — iOS CI/CD

A complete, reusable playbook for delivering an iOS app on **Bitrise** (macOS Xcode stacks). Use this when you need a mature CI/CD pipeline for build, signing, test, and IPA export.

> Official docs (ingest these before executing): https://docs.bitrise.io
> - Configuration YAML: https://docs.bitrise.io/en/bitrise-ci/references/configuration-yaml-reference
> - iOS quickstart (IPA export): https://docs.bitrise.io/en/bitrise-ci/getting-started/quick-start-guides/getting-started-with-ios-projects
> - iOS code signing: https://docs.bitrise.io/en/bitrise-ci/code-signing/ios-code-signing/ios-code-signing
> - Automatic provisioning: https://docs.bitrise.io/en/bitrise-ci/code-signing/ios-code-signing/managing-ios-code-signing-files---automatic-provisioning
> - Env vars/secrets: https://docs.bitrise.io/en/bitrise-ci/configure-builds/environment-variables
> - CLI: https://docs.bitrise.io/en/bitrise-ci/bitrise-cli/bitrise-cli-overview
> - Xcode Archive step: https://github.com/bitrise-steplib/steps-xcode-archive
> - XcodeGen step: https://bitrise.io/integrations/steps/xcodegen
> - Build Cache for Xcode: https://docs.bitrise.io/en/bitrise-build-cache/build-cache-for-xcode/configuring-the-build-cache-for-xcode-in-the-bitrise-ci-environment

---

## 0. Prerequisites (collect from the user)
- Repository URL + default branch.
- Bundle ID, scheme, and whether the user has a **paid Apple Developer Program membership**.
  - Paid ⇒ automatic provisioning via App Store Connect API key or Apple ID connection.
  - Free personal team ⇒ manual `.p12` + `.mobileprovision` ONLY (no API keys, no TestFlight/App Store distribution).

## 1. Mandatory setup (UI — cannot be fully scripted)
| Item | Where | Why |
|---|---|---|
| Add the app | Bitrise → Add new app → connect repo | Connects repo. |
| Code Signing | Project settings → Code signing | Upload `.p12` certs (dev + dist) + connect Apple service. |
| Secrets | Workflow/App env vars tab | `BITRISE_TOKEN`, keychain/passphrase, etc. |
| (Optional) Webhook | Auto-added by Bitrise on app creation | Triggers builds on push. |

## 2. Key secrets / env vars
| Var | Purpose |
|---|---|
| `BITRISE_TOKEN` | Bitrise API/CLI access (secret) |
| `BITRISE_CERTIFICATE_PASSPHRASE` | `.p12` passphrase |
| `BITRISE_KEYCHAIN_PASSWORD` | Keychain password for signing |
| `DEVELOPER_TEAM_ID` | Apple team ID (apple-id method) |
| Apple .p12 + profiles | Uploaded in Code Signing tab (manual method) |

## 3. `bitrise.yml` skeleton (validated pattern)
```yaml
format_version: '26'
default_step_lib_source: https://github.com/bitrise-io/bitrise-steplib.git
project_type: ios
meta:
  bitrise.io:
    stack: osx-xcode-latest-stable
workflows:
  primary:
    steps:
      - git-clone@8: {}
      - script@1:
          title: Install XcodeGen and generate project
          inputs:
            - content: |
                #!/bin/bash
                set -euo pipefail
                if ! command -v xcodegen >/dev/null 2>&1; then brew install xcodegen; fi
                xcodegen generate --spec ios_app_dist/ci_xcode/project.yml
      - xcode-archive@4:
          inputs:
            - project_path: $BITRISE_PROJECT_PATH
            - scheme: $BITRISE_SCHEME
            - distribution_method: ad-hoc   # or app-store / development
            - automatic_code_signing: api-key  # api-key | apple-id | off
            - export_options_plist_content: |
                <?xml version="1.0" encoding="UTF-8"?>
                <plist version="1.0"><dict>
                  <key>method</key><string>ad-hoc</string>
                  <key>signingStyle</key><string>automatic</string>
                </dict></plist>
      - deploy-to-bitrise-io@2: {}
```

### Known pitfalls
- Choose ONE signing path: `xcode-archive` automatic signing OR `manage-ios-code-signing` + your own build script — never both.
- Free personal team: no App Store Connect API keys → use `automatic_code_signing: apple-id` (with `DEVELOPER_TEAM_ID`) or manual `.p12`/profile; distribution limited to development.
- Every build is a clean VM — must upload certs + connect Apple services.
- Install XcodeGen in a script step (not preinstalled).

## 4. API/CLI automation
```bash
# Validate config
bitrise yml validate --config bitrise.yml
# Run a workflow locally
bitrise run primary --config bitrise.yml --inventory .bitrise.secrets.yml
```

## 5. Confirm green / artifact verification
- Build success; `$BITRISE_IPA_PATH` populated.
- Download IPA from the build artifacts page.
- Verify IPA with `scripts/verify_ios_artifacts.py`.

## 6. POV (human) acceptance benchmarks
Same as the Codemagic skill §6 — exercise every screen/module through the real UI with live backend data; verify install, signing, launch, full user journey, offline/error states, accessibility, and performance before delivery. Never claim a signed/validated install without verifying it on a device.
