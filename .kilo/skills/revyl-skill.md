---
name: revyl-skill
description: Run iOS/Android app tests on cloud devices via Revyl — publish a simulator .app or emulator APK, launch sessions, drive YAML tests/workflows, capture evidence. Use when a task involves Revyl device testing, cloud simulator/emulator testing, YAML test plans, or physical-ish device verification.
---

# Revyl Skill — Cloud-Device (Simulator/Emulator) Testing

A complete, reusable playbook for testing an app on **Revyl** cloud devices.

> ⚠️ **Official correction:** Revyl runs tests on **cloud simulators (iOS) and emulators (Android)** — it does **NOT** run physical devices. A physical-device `.ipa` is rejected; you must provide a **simulator `.app`** (built for `iphonesimulator`, containing `arm64`) or an emulator APK. Plan accordingly (this complements Codemagic/Bitrise which build the `.app`).

> Official docs (ingest these before executing): https://docs.revyl.com
> - Auth: https://docs.revyl.com/authentication
> - Mobile quickstart: https://docs.revyl.com/devices/quickstart
> - Infrastructure (simulators/emulators): https://docs.revyl.com/infrastructure
> - Artifact requirements (simulator `.app`): https://docs.revyl.com/builds/artifact-requirements
> - YAML tests: https://docs.revyl.com/tests/yaml
> - Test format reference: https://docs.revyl.com/reference/yaml-test-format
> - Workflows + CI: https://docs.revyl.com/tests/workflows , https://docs.revyl.com/tests/ci

---

## 0. Prerequisites
- `REVYL_API_KEY` (secret) — used non-interactively in CI.
- A built **simulator `.app`** (iOS) or **debuggable `.apk`** (Android). For iOS this comes from Codemagic/Bitrise `ios-verify-and-sim-app` workflow (`SuperCraftOS-simulator.app.zip`).
- Revyl CLI: `curl -fsSL https://revyl.com/install.sh | sh && export PATH="$HOME/.revyl/bin:$PATH"`.

## 1. Authenticate
```bash
revyl auth status
# CI:
export REVYL_API_KEY="..."   # takes precedence over stored creds
```

## 2. Create app + register build
```bash
revyl init -y
revyl app create --name "MyApp" --platform ios --json   # → app_id
# set build.profiles.<profile>.ios.app_id in .revyl/config.yaml
revyl config validate
# Upload simulator .app (zip) or build in-cloud:
revyl build upload --file ./MyApp-simulator.app.zip --app YOUR_APP_ID --platform ios --json
# → build_version_id
```

## 3. Launch a device session
```bash
revyl device start --platform ios --build-version-id YOUR_BUILD_ID --json
# device selection: model/os pinned per test or via --device-model (see `revyl device targets`)
```

## 4. Capture evidence
```bash
revyl device screenshot --session-id "$SESSION_ID" --out after.png
revyl device validation --session-id "$SESSION_ID" "The home screen is visible." --json
revyl device report --session-id "$SESSION_ID" --json
revyl device stop --session-id "$SESSION_ID"
```

## 5. YAML tests + workflows (the "journey" pattern)
```yaml
test:
  metadata:
    name: smoke-login-ios
    platform: ios
    variables:
      email: test@example.com
  build:
    name: my-ios-app
  device:
    model: "iPhone 17"
    os_version: "iOS 26.5"
  blocks:
    - type: instructions
      step_description: Tap the Sign In button
    - type: validation
      step_description: The inbox is visible
```
```bash
revyl test create smoke-login-ios --from-file ./smoke-login-ios.yaml
revyl test push smoke-login-ios --force
revyl test run smoke-login-ios
# Group into a workflow (run many tests, parallel):
revyl workflow create regression
revyl workflow add-tests regression login-flow checkout-flow
revyl workflow config regression --parallelism 3 --retries 2
revyl workflow run regression --build
```

## 6. POV (human) acceptance benchmarks
Run a full user journey on the device via YAML/validation:
1. Install + launch the app; assert the first screen renders.
2. Login/connect with real backend; assert live data appears (not placeholders).
3. Exercise navigation to every module/screen; assert each is interactive.
4. Error/offline states render and allow recovery.
5. Capture screenshots + report as evidence.
Pass = every journey completes with real data; fix and re-run on failure.

## 7. CI note
Set `REVYL_API_KEY` in CI; invoke `revyl workflow run smoke-tests`. Never commit the key.
