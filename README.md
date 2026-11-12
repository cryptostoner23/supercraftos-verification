# OpenCode SuperCraftOS — Digital Me × SuperCraftOS

A unified, production-grade **personal AI operating system**: SuperCraftOS's AI workspace (agents, tasks, workflows, grants, product lab, integrations) fused with **Digital Me**'s persistent identity, memory, reasoning, and planning. Ships with a native iOS app (SwiftUI), a FastAPI backend, a private gateway, and full CI/CD + device-testing automation.

Delivered and verified on a 2015 MacBook Air (Xcode 15.4, iOS 17.5 simulator) **and** on the Codemagic cloud (Xcode 26.6, iOS 26.x) — with a **520-test green suite** (see [Verification](#verification)).

---

## Repository Contents

| Area | Location | Description |
|---|---|---|
| Backend | `main.py`, `supercraftos_cli.py`, `digital_me.py`, `private_gateway.py` | FastAPI-style unified API (Digital Me + SuperCraftOS routes), private HTTPS gateway |
| Agents | `agent_runtime.py`, `langgraph_orchestrator.py`, `agent_tools.py`, `agent-core/` | Autonomous agent execution, orchestration, tools |
| iOS app | `ios_app_dist/YourApp.swiftpm/` | SwiftUI host app + keyboard/share extensions (XcodeGen spec) |
| iOS project spec | `ios_app_dist/ci_xcode/project.yml` | **Single source of truth** — XcodeGen generates the `.xcodeproj` (never commit the generated project) |
| Swift verification | `swift-verification/` | Portable Swift package with contract tests (46) |
| Python tests | `test_*.py` | 435-test unittest suite |
| Security audit | `scripts/audit_repository.py` | Static secret + syntax scan (0 issues) |
| CI/CD | `.github/workflows/ci.yml`, `bitrise.yml`, `codemagic.yaml` | GitHub Actions, Bitrise, and Codemagic pipelines |
| Skills | `.kilo/skills/{codemagic,bitrise,revyl}-skill.md` | Platform-specific, reusable delivery playbooks |
| Free signing tooling | `scripts/free_team_refresh.sh`, `scripts/auto_install_from_codemagic.sh` | Free Apple "Personal Team" signing + auto-install |
| Docs | `DEPLOYMENT.md`, `docs/` | Deployment, Apple install, testing details |

---

## Quick Start (backend)

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock   # or -r requirements.txt
cp .env.example .env && chmod 600 .env        # fill in your provider keys
.venv/bin/python main.py doctor                # health check
.venv/bin/python main.py app                   # serve http://127.0.0.1:8787
```

**Digital Me routes** (live-verified): `/api/digital_me/profile`, `/api/digital_me/memory`, `/api/digital_me/reasoning`, `/api/digital_me/planning`.

---

## iOS app

- Bundle ID: `com.supercraftos.control`
- Backend baked in: `https://agent.commetai.ca` (override via `SUPERCRAFTOS_BACKEND_URL`)
- Access key: provisioned at build time via `SUPERCRAFTOS_ACCESS_KEY` (never committed) or entered manually at connect; stored in Keychain.
- Extensions: keyboard (`com.supercraftos.control.keyboard`) and share (`...share`) — built and CI-verified, deliberately not embedded by default.

### Build from the XcodeGen spec
```bash
# macOS (Xcode required)
brew install xcodegen          # or use the pinned 2.43 binary (format-compatible with Xcode 15)
xcodegen generate --spec ios_app_dist/ci_xcode/project.yml
xcodebuild -project ios_app_dist/ci_xcode/SuperCraftOS.xcodeproj \
  -scheme SuperCraftOS -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 17' CODE_SIGNING_ALLOWED=NO build
```

### Free personal-team signing + auto-install (no paid Apple Developer Program)
Credentials file (gitignored, mode 0600): `.signing/creds.env` → `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `DEVICE_UDID`.
```bash
# Sign the current source and install to your iPhone (USB / same Wi-Fi):
bash scripts/free_team_refresh.sh
# Auto-fetch the latest green Codemagic build, re-sign, and install:
bash scripts/auto_install_from_codemagic.sh
```
A launchd job (`scripts/ai.supercraftos.free-team-refresh.plist`) runs this daily to stay inside the 7-day free-profile window.

---

## CI/CD

### GitHub Actions (`.github/workflows/ci.yml`)
`python-tests` (435), `repository-audit` (0 issues), `swift-package-tests` (46). Runs on every push/PR. (Account billing-lock currently blocks runners; the Mac + Codemagic provide the proof.)

### Codemagic (`codemagic.yaml`) — the single delivery platform
Two workflows, both auto-triggered by a webhook on push to `main`:
| Workflow | What it does | Artifacts |
|---|---|---|
| `ios-verify-and-sim-app` | XcodeGen generate → Swift contract tests → iOS unit/UI/backend/interaction suites on a simulator → unsigned simulator `.app` | `SuperCraftOS-simulator.app.zip`, `.app`, test logs |
| `ios-release` | Build unsigned IPA (+ optional manual free-team signing) | `SuperCraftOS-unsigned.ipa` |

**Mandatory Codemagic setup (UI):** webhook (events: Pushes/PRs/Branch-tag) + env groups `ios_config` and `backend_credentials` (secrets). See `.kilo/skills/codemagic-skill.md` for the full playbook and pitfalls.

### Bitrise (`bitrise.yml`)
macOS Xcode stack; builds signed/unsigned IPA via CodexCode-archive` step. See `.kilo/skills/bitrise-skill.md`.

### Revyl (`.revyl/config.yaml`)
Cloud-device (simulator/emulator) testing of the simulator `.app`. See `.kilo/skills/revyl-skill.md`.

---

## Verification

| Suite | Result |
|---|---|
| Python backend unittest | 435 OK (23 designed skips) |
| Repository audit (secrets + syntax) | 0 issues (Python 3.9 & 3.12) |
| Swift contract tests | 46/46 |
| iOS UI E2E (real app on simulator) | 10/10 |
| iOS unit / backend / interaction | 5/5 · 18/18 · 6/6 |
| **Total** | **520 green** |
| Codemagic cloud (`ios-verify-and-sim-app`) | All steps green, artifacts produced |
| Codemagic cloud (`ios-release`) | All steps green, unsigned IPA produced |
| Webhook auto-trigger | Verified (push → automatic builds) |

---

## Security

- No secrets in the tree or history. `.env`, `.signing/` are gitignored and mode 0600.
- The audit (`scripts/audit_repository.py`) statically blocks committed credentials (including the previously leaked gateway key pattern).
- Access key rotated via `data/access.key`; the gateway validates Host/Origin and requires bearer/session auth.

---

## Architecture notes

- **No e-commerce / payment components.**
- **Repository sync model:** `origin` = public mirror (`cryptostoner23/supercraftos-verification` fresh single-root history); private canonical = `cryptostoner94/opencode-supercraftos`. Never push legacy history or the `sync` branch to any public repo.
- The Xcode project is generated from the spec; never commit a `.xcodeproj`.
