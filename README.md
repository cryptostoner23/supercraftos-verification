# OpenCode SuperCraftOS

**Digital Me × SuperCraftOS** — full inventory of every action taken, IPA artifacts, and device testing results.

## Repository Contents

This is the complete working codebase as of 2026-11-07, including:

- **Backend**: FastAPI unified API (Digital Me v2 + SuperCraftOS routes), private gateway, systemd services
- **iOS App**: SwiftUI host app + keyboard extension, XcodeGen spec, Info.plist with provisioned access key
- **Revyl Cloud Device Testing**: Full E2E test sessions, screenshots, and build artifacts
- **CI/CD**: Bitrise pipeline (`bitrise.yml`), Revyl build config (`.revyl/config.yaml`)
- **Swift Verification**: `swift-verification/` package with contract tests
- **Python Tests**: 50+ test files covering all subsystems
- **Documentation**: DEPLOYMENT.md, docs/, REVYL_TESTING.md

## Quick Start

```bash
cd /root/SuperCraftOS
python3.14 -m venv .venv
.venv/bin/pip install -r requirements.lock
cp .env.example .env
chmod 600 .env
.venv/bin/python main.py doctor
```

## Backend Status

| Component | Port | Status |
|-----------|------|--------|
| Python backend (`main.py app`) | 8787 | Running |
| Private gateway (`private_gateway.py`) | 8790 | Running |
| HTTPS (nginx + TLS) | 443 | `https://agent.commetai.ca` |

**Access key**: `BCQMChP-tCaOWU_aeLlY32rn618HAX3F8Oi4dIf0wjg`

## iOS App

- Bundle ID: `com.supercraftos.control`
- Build profile: `ipa_release` (simulator, unsigned)
- Backend URL baked in: `https://agent.commetai.ca`
- Access key provisioned in Info.plist for simulator Keychain bypass

## Revyl Device Testing

- App ID: `017e6103-7dbe-4ba3-a910-88575e966048`
- Latest session: `044203be-2bd6-4ad9-852c-b306bb387ba1`
- Device: iPhone 15, iOS 26.2
- Screenshots: `app.png` through `app_conn3.png`, `app_focus.png`, `app_result.png`, `app_check.png`

## Test Plan

See `/root/REVYL_TESTING.md` for the 25-journey E2E test plan.

## Key Files

| File | Purpose |
|------|---------|
| `ios_app_dist/ci_xcode/project.yml` | XcodeGen spec (single source of truth) |
| `ios_app_dist/ci_xcode/Info.plist` | App config with provisioned access key |
| `ios_app_dist/YourApp.swiftpm/BackendClient.swift` | API client |
| `ios_app_dist/YourApp.swiftpm/CredentialStore.swift` | Keychain credential storage |
| `ios_app_dist/YourApp.swiftpm/AppConfig.swift` | App config + BackendStore |
| `private_gateway.py` | HTTPS gateway with access key auth |
| `.revyl/config.yaml` | Revyl build configuration |
| `bitrise.yml` | CI/CD pipeline |

## iOS Build via Bitrise CLI

All iOS automation runs through the official Bitrise CLI (`bitrise run --config bitrise.yml --workflow <workflow>`). **These steps require macOS** (Xcode toolchain, `xcodebuild`, `xcodegen`, `bitrise`) and cannot run on Linux.

Available workflows:

| Workflow | Purpose |
|----------|---------|
| `primary` | Generate Xcode project from XcodeGen spec, build unsigned iOS device app, export production `.ipa` |
| `personal_device` | Build standalone unsigned iOS device app for local private provisioning / Sideloadly |
| `run_tests` | Build for simulator + device, run Swift package and UI tests |
| `mission_acceptance` | Compile mission workspace, drive app screens on iPad/iPhone with offline fixtures |
| `ipa_release` | Build and export unsigned iOS `.ipa` |
| `live_backend_contract` | Read-only backend gateway smoke tests |

Example (macOS only):
```bash
bitrise run --config bitrise.yml --workflow primary
```

Continuous polling until the signed/unsigned `.ipa` is produced (macOS, 110s max sleep interval):
```bash
while true; do
    if bitrise run --config bitrise.yml --workflow primary 2>&1 | grep -qE "SUCCESS|The export completed"; then
        break
    fi
    sleep 110
done
```

Verify a delivered `.ipa` / `.app.zip` bundle:
```bash
.venv/bin/python scripts/verify_ios_artifacts.py <app.zip>
```

## Architecture Boundaries

- **No e-commerce**: The application structure contains no shops, carts, checkouts, or payment components.
- **CrossX Campaigns**: Video/quest workflows are nested under CrossX Campaigns (`QuestOperationsView.swift`); `FAY` is not a main module.
- **Keyboard extension**: Deliberately not embedded by default. Activate with `python3 scripts/xcode_project.py --embed-keyboard`.

## Commit History

1. `bedb81d` — Add provisioned access key in Info.plist for simulator Keychain bypass
2. `233c882` — feat: complete Bitrise build trigger and Revyl setup for iOS IPA deployment
3. `72d86ad` — Repair source generation, automatic verification, acceptance and provider recovery
4. `b4c8a16` — Honor provider cooldowns without retrying early
5. `5968534` — Preserve tasks across provider outages and record build 190 delivery evidence