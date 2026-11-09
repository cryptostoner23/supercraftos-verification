# Bitrise Skill — iOS CI/CD Platform

## What Bitrise Provides

Bitrise is a mobile CI/CD platform for iOS and Android apps. It enables:

- **Cloud macOS runners**: On-demand macOS machines with Xcode for iOS app compilation
- **Local CLI**: `bitrise` command-line tool for triggering and managing builds
- **Workflow configuration**: `bitrise.yml` for defining CI/CD pipelines
- **Artifact management**: Deploy and store build artifacts (`.ipa`, `.app.zip`, test reports)
- **Remote Dev Environments (RDE)**: On-demand macOS cloud machines accessible via CLI
- **Stack management**: Multiple Xcode versions available (osx-xcode-latest-stable, osx-xcode-27.x, etc.)

## Environment Constraints (CRITICAL)

**Xcode and `xcodebuild` only run on macOS.** They cannot be installed or executed on Linux.

| Operation | Linux | macOS | Bitrise Cloud |
|-----------|-------|-------|---------------|
| `bitrise` CLI | ✅ | ✅ | ✅ |
| `xcodebuild` | ❌ | ✅ | ✅ (via cloud runners) |
| `xcodegen` | ❌ | ✅ | ✅ (via cloud runners) |
| `ditto` | ❌ | ✅ | ✅ (via cloud runners) |
| `brew` | ❌ | ✅ | ✅ (via cloud runners) |
| iOS `.ipa` build | ❌ | ✅ | ✅ (via cloud runners) |

**On Linux, you can only:**
- Install and authenticate the `bitrise` CLI
- Validate `bitrise.yml` YAML syntax
- Trigger cloud builds on Bitrise macOS runners
- Monitor build status via API/CLI

**You cannot:**
- Run `xcodebuild`, `xcodegen`, `ditto`, or `brew` locally
- Produce an `.ipa` without Bitrise cloud credits or RDE access

## Official Documentation Sources

- Bitrise CLI overview: https://docs.bitrise.io/en/bitrise-ci/bitrise-cli/bitrise-cli-overview
- Bitrise YAML configuration: https://docs.bitrise.io/en/bitrise-ci/configure-builds/configuration-yaml/configuration-yaml-overview
- Bitrise local builds: https://docs.bitrise.io/en/bitrise-ci/bitrise-cli/running-your-first-local-build-with-the-cli
- Bitrise RDE overview: https://docs.bitrise.io/en/bitrise-rde/getting-started/remote-dev-environments-overview
- Bitrise RDE CLI: https://docs.bitrise.io/en/bitrise-rde/rde-options/bitrise-rde-cli
- Bitrise app management: https://docs.bitrise.io/en/bitrise-ci/bitrise-cli/managing-builds-with-the-bitrise-cli
- Bitrise stack reference: https://docs.bitrise.io/en/bitrise-ci/getting-started/stack-reference

## Bitrise CLI Installation (Linux)

```bash
# Download Bitrise CLI v3.4.1 for Linux x86_64
curl -sL --max-time 120 -o /tmp/kilo/bitrise \
  "https://github.com/bitrise-io/bitrise/releases/download/v3.4.1/bitrise-Linux-x86_64"
chmod +x /tmp/kilo/bitrise

# Verify installation
/tmp/kilo/bitrise --version
```

## Bitrise CLI Commands

### Authentication

```bash
# Authenticate with API token
export BITRISE_TOKEN='bitpat_...'
/tmp/kilo/bitrise auth status

# List workspaces
/tmp/kilo/bitrise workspace list
```

### App Management

```bash
# List apps in a workspace
/tmp/kilo/bitrise app list --workspace <workspace-id>

# Create a new app
/tmp/kilo/bitrise app create \
  --repo-url <git-repo-url> \
  --workspace <workspace-id> \
  --stack osx-xcode-latest-stable \
  --project-type ios \
  --title <app-title> \
  --bitrise-yml ./bitrise.yml

# Upload bitrise.yml to existing app
/tmp/kilo/bitrise yml update --app <app-id> --file ./bitrise.yml

# Get current bitrise.yml from app
/tmp/kilo/bitrise yml get --app <app-id>
```

### Build Management

```bash
# Trigger a build (cloud macOS runner)
/tmp/kilo/bitrise build trigger \
  --app <app-id> \
  --workflow primary \
  --stack osx-xcode-latest-stable \
  --watch \
  --format json

# Get build logs
/tmp/kilo/bitrise build log <build-id> --app <app-id>

# List builds
/tmp/kilo/bitrise build list --app <app-id>

# Get build artifacts
/tmp/kilo/bitrise build artifacts <build-id> --app <app-id>
```

### Remote Dev Environments (RDE)

```bash
# List available RDE stacks (requires RDE User role on workspace)
/tmp/kilo/bitrise rde stack list

# Create an RDE session (macOS cloud machine)
/tmp/kilo/bitrise rde session create <session-name> \
  --stack <macos-stack-id> \
  --wait

# Execute commands in RDE session
/tmp/kilo/bitrise rde session exec <session-id> --shell -- '<command>'

# Download artifacts from RDE session
/tmp/kilo/bitrise rde session download <session-id> <remote-path> <local-path>
```

## bitrise.yml Configuration Schema

```yaml
format_version: '26'
default_step_lib_source: https://github.com/bitrise-io/bitrise-steplib.git
project_type: ios
meta:
  bitrise.io:
    stack: osx-xcode-latest-stable

workflows:
  primary:
    description: Primary workflow for iOS build and IPA export
    steps:
      - git-clone@8:
          repository: <git-repo-url>
          clone_dir: /home/bitrise/project
          reset_repository: true
      - script@1:
          title: Package Swift app bundle
          inputs:
            - content: |
                #!/bin/bash
                set -euo pipefail
                python3 scripts/package_ipad.py
      - script@1:
          title: Install XcodeGen and generate Xcode project
          inputs:
            - content: |
                #!/bin/bash
                set -euo pipefail
                if ! command -v xcodegen >/dev/null 2>&1; then brew install xcodegen; fi
                python3 scripts/xcode_project.py
      - script@1:
          title: Build unsigned iOS device app
          inputs:
            - content: |
                #!/bin/bash
                set -euo pipefail
                DERIVED="$BITRISE_SOURCE_DIR/build/PersonalDevice"
                xcodebuild -project ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj \
                  -scheme SuperCraftOS -configuration Release -sdk iphoneos \
                  -destination 'generic/platform=iOS' -derivedDataPath "$DERIVED" \
                  CODE_SIGNING_ALLOWED=NO build
                APP="$DERIVED/Build/Products/Release-iphoneos/SuperCraftOS.app"
                test -d "$APP"
                mkdir -p "$BITRISE_SOURCE_DIR/build/Artifacts"
                ditto "$APP" "$BITRISE_SOURCE_DIR/build/Artifacts/SuperCraftOS-iOS-Device-unsigned.app.zip"
      - script@1:
          title: Create unsigned production IPA
          inputs:
            - content: |
                #!/bin/bash
                set -euo pipefail
                DERIVED="$BITRISE_SOURCE_DIR/build/PersonalDevice"
                APP="$DERIVED/Build/Products/Release-iphoneos/SuperCraftOS.app"
                test -d "$APP"
                IPA_DIR="$BITRISE_SOURCE_DIR/build/IPA-Staging"
                rm -rf "$IPA_DIR"
                mkdir -p "$IPA_DIR/Payload"
                cp -R "$APP" "$IPA_DIR/Payload/"
                cd "$IPA_DIR"
                zip -r "$BITRISE_SOURCE_DIR/build/Artifacts/SuperCraftOS.ipa" Payload
                test -f "$BITRISE_SOURCE_DIR/build/Artifacts/SuperCraftOS.ipa"
      - deploy-to-bitrise-io@2:
          inputs:
            - app: "$BITRISE_SOURCE_DIR/build/Artifacts/SuperCraftOS.ipa"
```

## SuperCraftOS Bitrise Configuration

- **Workspace**: `ALoop Agent's Workspace` (`5783385ed314a160`)
- **App ID**: `a49eb347-6a2a-4198-b77d-78ecfeedbb71`
- **Stack**: `osx-xcode-latest-stable` (Xcode 27.2)
- **Project type**: iOS
- **Git repo**: `https://github.com/cryptostoner94/opencode-supercraftos.git`
- **Workflow**: `primary`
- **Build URL**: https://app.bitrise.io/app/a49eb347-6a2a-4198-b77d-78ecfeedbb71/build/292f5a9a-5c09-4876-ae4b-4554e9811efb

## Authentication

```bash
# Set Bitrise API token
export BITRISE_TOKEN='bitpat_...'

# Verify auth
/tmp/kilo/bitrise auth status
```

**Never commit API tokens to the repository.** Store them in environment variables.

## Credits & Limits

- Bitrise cloud builds consume **build credits**
- Zero credits → `400: you don't have enough credits` on every build trigger
- Add credits via Bitrise web UI → Billing/Plan page
- RDE requires workspace-level **RDE User role** permission (403 if not granted)

## Build Failure Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `400: not enough credits` | No build credits | Add credits via Bitrise web UI |
| `403: Permission denied` | No RDE access | Grant RDE User role on workspace |
| `xcodegen: command not found` | No Homebrew on Linux | Run on macOS or Bitrise cloud |
| `xcodebuild: command not found` | No Xcode on Linux | Run on macOS or Bitrise cloud |
| `401 Unauthorized` | Invalid token | Verify BITRISE_TOKEN |
| `Step missing required field` | Invalid bitrise.yml | Validate YAML syntax |

## YAML Validation

```bash
# Validate bitrise.yml syntax
python3 -c "import yaml; yaml.safe_load(open('bitrise.yml')); print('valid')"

# Or use bitrise CLI (if available)
/tmp/kilo/bitrise yml validate --file ./bitrise.yml
```

## Zero GitHub Actions Policy

**All iOS automation must run via Bitrise CLI, not GitHub Actions.**
- Strip all `.github/workflows/*` files
- Do not create new GitHub Actions workflows for iOS builds
- Use `bitrise run --config bitrise.yml --workflow <workflow>` for local execution
- Use `bitrise build trigger` for cloud execution
