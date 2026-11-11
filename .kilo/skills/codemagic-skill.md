---
name: codemagic-skill
description: Build, test, and deliver an iOS app end-to-end on Codemagic (single platform) — from XcodeGen spec to signed/unsigned IPA and simulator .app, with webhooks, env/secrets, CI/CD, and POV acceptance. Use when a task involves Codemagic builds, webhooks, env vars, artifacts, or iOS CI/CD delivery on Codemagic.
---

# Codemagic Skill — Single-Platform iOS Delivery

A complete, reusable playbook for delivering an iOS app on **Codemagic** (free tier: 500 macOS M2 minutes/month). This is the platform that covers the entire pipeline in one place: XcodeGen generate → Swift tests → iOS unit/UI/backend/interaction tests on a simulator → unsigned IPA + simulator `.app` → TestFlight/App Store + tester distribution.

> Official docs (ingest these before executing): https://docs.codemagic.io
> - config: https://docs.codemagic.io/yaml-basic-configuration/yaml-getting-started/
> - env vars/secrets: https://docs.codemagic.io/yaml-basic-configuration/configuring-environment-variables/
> - webhooks: https://docs.codemagic.io/yaml-running-builds/webhooks/
> - auto-build triggers: https://docs.codemagic.io/yaml-running-builds/starting-builds-automatically/
> - signing iOS: https://docs.codemagic.io/yaml-code-signing/signing-ios/
> - tests: https://docs.codemagic.io/yaml-testing/testing/
> - REST API: https://docs.codemagic.io/rest-api/codemagic-rest-api/
> - Xcode 26/27 specs: https://docs.codemagic.io/specs-macos/xcode-26-6/

---

## 0. Prerequisites (collect from the user)
- Repository URL + default branch (must contain `codemagic.yaml` at root).
- Bundle ID, Xcode scheme name, and the simulator device name to test on.
- Optional but strongly recommended:
  - **Codemagic API key** (for CLI/API automation). Scope: full account-level access.
  - **App Store Connect API key** (Issuer ID, Key ID, `.p8`) — ONLY if the user has a paid Apple Developer Program membership. For free personal teams, automatic provisioning is NOT possible; use manual `.p12` + `.mobileprovision` or ship unsigned.
  - Gateway access key / backend URL (runtime env injection).

## 1. Mandatory setup (from the UI — these CANNOT be done via API)
| Item | Where | Why |
|---|---|---|
| Add the app | Codemagic → Add application → GitHub → select repo | Connects the repo. |
| **Create webhook** | App settings → Webhooks → Create webhook | **MANDATORY** for automatic builds on push. Payload URL: `https://api.codemagic.io/hooks/<appId>`. Events: Pushes, Pull requests, Branch/tag creation. |
| Environment groups | App settings → Environment variables (or Team settings) | Secrets + config injected at build time. Mark secrets as **Secret**. |
| (Paid only) App Store Connect integration | Team settings → Integrations | For automatic signing + TestFlight/App Store. |

> The API key alone cannot create the webhook (that is a GitHub-repo action) nor create env groups in some setups — the webhook requires `admin:repo_hook` scope on the GitHub token; env groups are created in the Codemagic UI (or via the REST API `POST /apps/{id}/variables` with `{"key":..., "value":..., "group":...}` — mark secrets by storing them as-is; the API returns `secure:true`).

## 2. Environment variables / secrets (required)
Group `ios_config` (public):
| Var | Example | Purpose |
|---|---|---|
| `XCODE_SCHEME` | `SuperCraftOS` | Scheme for build/test |
| `TEST_SIMULATOR` | `iPhone 17` | Device for `xcodebuild test` (**must exist on the stack's Xcode** — iPad Xcode 26.6, `iPhone 16` does NOT exist; use `iPhone 17`/`iPhone 17 Pro`) |
| `BACKEND_URL` | `https://agent.commetai.ca` | Runtime-injected backend |
| `BUILD_NOTIFY_EMAIL` | `you@example.com` | Notifications |

Group `backend_credentials` (Secret): `ACCESS_KEY`, optional `REVYL_API_KEY`, `GCLOUD_KEY_FILE`, `FIREBASE_PROJECT`.

## 3. `codemagic.yaml` skeleton (validated & working)
```yaml
workflows:
  ios-verify-and-sim-app:
    name: iOS Verify + Simulator .app
    max_build_duration: 120
    instance_type: mac_mini_m2
    triggering:
      events: [push]
      branch_patterns:
        - pattern: 'main'
          include: true
          source: true
    environment:
      xcode: latest
      groups: [ios_config, backend_credentials]
    scripts:
      - name: Install XcodeGen and generate the Xcode project
        script: |
          command -v xcodegen >/dev/null 2>&1 || brew install xcodegen
          cd "$CM_BUILD_DIR"
          xcodegen generate --spec ios_app_dist/ci_xcode/project.yml
      - name: Swift contract tests (SPM)
        script: |
          cd "$CM_BUILD_DIR"; set -e; mkdir -p build
          export SUPERCRAFTOS_CLI_BINARY="$(swift build --package-path swift-verification --show-bin-path)/supercraftos-check"
          swift test --package-path swift-verification 2>&1 | tee build/contract-tests.log
        test_report: build/contract-tests.log
      - name: iOS unit / UI / backend / interaction tests on simulator
        script: |
          cd "$CM_BUILD_DIR"; set -e; mkdir -p build/ios
          PROJECT=ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj
          for SCHEME in SuperCraftOSTests SuperCraftOSBackendTests SuperCraftOSInteractionTests SuperCraftOSUITests; do
            xcodebuild test -project "$PROJECT" -scheme "$SCHEME" \
              -sdk iphonesimulator -destination "platform=iOS Simulator,name=$TEST_SIMULATOR" \
              CODE_SIGNING_ALLOWED=NO 2>&1 | tee build/ios/$SCHEME.log
          done
        test_report: build/ios/*.log
      - name: Build unsigned simulator .app slice (for cloud-device testing)
        script: |
          cd "$CM_BUILD_DIR"; set -e; mkdir -p build/simulator
          xcodebuild build -project ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj \
            -scheme SuperCraftOS -sdk iphonesimulator -configuration Debug \
            -destination 'generic/platform=iOS Simulator' -derivedDataPath build/derived \
            CODE_SIGNING_ALLOWED=NO
          APP=$(find build/derived/Build/Products -name "SuperCraftOS.app" -maxdepth 2 | head -1)
          ditto -c -k --keepParent "$APP" build/simulator/SuperCraftOS-simulator.app.zip
    artifacts:
      - build/simulator/*.zip
      - build/ios/*.log
      - build/contract-tests.log
      - $HOME/Library/Developer/Xcode/DerivedData/**/Build/**/*.app
      - $HOME/Library/Developer/Xcode/DerivedData/**/Build/**/*.dSYM
    publishing: {}

  ios-release:
    name: iOS Release (unsigned IPA + optional manual signing)
    max_build_duration: 120
    instance_type: mac_mini_m2
    triggering:
      events: [push]
      branch_patterns:
        - pattern: 'main'
          include: true
          source: true
    environment:
      xcode: latest
      groups: [ios_config, backend_credentials]
    scripts:
      - name: Install XcodeGen, generate project, apply backend runtime env
        script: |
          command -v xcodegen >/dev/null 2>&1 || brew install xcodegen
          cd "$CM_BUILD_DIR"
          xcodegen generate --spec ios_app_dist/ci_xcode/project.yml
      - name: Build and export IPA (unsigned unless signing secrets present)
        script: |
          cd "$CM_BUILD_DIR"; set -e; mkdir -p build/ios/ipa
          xcodebuild build -project ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj \
            -scheme SuperCraftOS -configuration Release \
            -sdk iphoneos -destination 'generic/platform=iOS' \
            -derivedDataPath build/device \
            CODE_SIGNING_ALLOWED=NO
          APP=$(find build/device/Build/Products -name "SuperCraftOS.app" -maxdepth 2 | head -1)
          mkdir -p build/ipa-staging/Payload; cp -R "$APP" build/ipa-staging/Payload/
          (cd build/ipa-staging && zip -r ../ios/ipa/SuperCraftOS-unsigned.ipa Payload)
    artifacts:
      - build/ios/ipa/*.ipa
      - $HOME/Library/Developer/Xcode/DerivedData/**/Build/**/*.dSYM
    publishing:
      email:
        recipients: [$BUILD_NOTIFY_EMAIL]
        notify: {success: true, failure: true}
```

### Known pitfalls (do not repeat)
- `tee` fails if the `build/` or `build/ios/` directory does not exist → always `mkdir -p` first.
- `Swift test` CLI contract tests fail without `SUPERCRAFTOS_CLI_BINARY` (the binary the tests spawn) → set it to `$(swift build --package-path ... --show-bin-path)/supercraftos-check`.
- Destination simulator must exist on the chosen Xcode stack. Xcode 26.6 has iPhone 17/17 Pro/Air, **not** iPhone 16.
- Free personal team ⇒ NO automatic provisioning ⇒ ship unsigned IPA + simulator `.app`; sign locally (see `free_team_refresh.sh`).

## 4. REST API automation (no UI needed for builds)
```bash
KEY="$CODEMAGIC_API_KEY"; APP_ID="<appId>"
# Trigger a build:
curl -s -X POST https://api.codemagic.io/builds \
  -H "x-auth-token: $KEY" -H "Content-Type: application/json" \
  -d "{\"appId\":\"$APP_ID\",\"branch\":\"main\",\"workflowId\":\"ios-verify-and-sim-app\"}"
# List builds:
curl -s "https://api.codemagic.io/builds?limit=10" -H "x-auth-token: $KEY"
# Create an env variable (group enum):
curl -s -X POST "https://api.codemagic.io/apps/$APP_ID/variables" \
  -H "x-auth-token: $KEY" -H "Content-Type: application/json" \
  -d '{"key":"BACKEND_URL","value":"https://agent.commetai.ca","group":"ios_config"}'
# Artifacts appear in the build record's `artefacts` array (`.url`).
```

## 5. Confirm green / artifact verification
- Build `status: finished` and every `buildActions[].status == success`.
- Artifacts: `SuperCraftOS-unsigned.ipa`, `SuperCraftOS-simulator.app.zip`, `.app`, `.dSYM`.
- Download via the `artefacts[].url` with `x-auth-token` header.

## 6. POV (human) acceptance benchmarks — apply to every delivered build
Cover every module/screen through the real UI (no mock-only rendering). Verify:
1. App builds, installs, launches; every screen opens and is interactive.
2. Backend sync: UI shows real/live data (workers online, tasks, digital-me memory) — not placeholders.
3. Sign-in/connection flows, error + offline states, retry/recovery.
4. iOS-specific: launch screen, icons, privacy manifest, accessibility (VoiceOver identifiers, Dynamic Type, contrast), rotations, background/foreground.
5. Real device/cloud-device: install the `.app` (simulator) or signed IPA on a device; exercise a complete user journey (login → task → result → artifact).
6. Performance: no perceptible delay on a typical device; graceful degradation when backend/providers are unavailable.
Pass = every journey completes end-to-end with real data; failures are fixed and re-verified before delivery.
