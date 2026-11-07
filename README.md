# SuperCraftOS

Latest live account checks and confirmed grant submission: [flow delivery](docs/FLOW_DELIVERY_2026-10-30.md).

SuperCraftOS is a single-operator Python control center for autonomous software tasks, local CAD generation, grant preparation, and configured service integrations.

Current recovery, live checks and outstanding requirements: [mission delivery, 2026-10-30](docs/MISSION_DELIVERY_2026-10-30.md).

## Run it

Use Linux and Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
cp .env.example .env
# Set a model credential and model in .env; keep this file private.
docker pull python:3.12-slim
.venv/bin/python main.py app
```

Open **http://127.0.0.1:8787/agents**. Submit a goal, follow the persistent activity log, and download the result and check receipts. The app starts an embedded worker by default. Commands require a running Docker daemon and the pre-pulled sandbox image. Missing model access or execution tools produce a concrete blocked status.

### iOS control app

The native SwiftUI app combines the existing Mission/Product Lab/keyboard UI with durable Tasks, Memory, Quests and account operations. It connects through the private gateway using an access key stored in the device Keychain. The public server address alone does not authorize agent commands.

Start with [free personal installation](docs/FREE_APPLE_INSTALL.md). Bitrise builds the device IPA, so an older Mac can sign and install the downloaded app without compiling it or replacing its existing Xcode. The standalone app targets iOS 17; the optional keyboard requires iOS 26. Free Personal Team provisioning expires after seven days and must be refreshed on the device. Browser downloads and server re-signing do not by themselves install or renew an app. TestFlight requires paid membership.

`ios_app_dist/ci_xcode/project.yml` is the XcodeGen source of truth. `scripts/package_ipad.py` synchronizes the native sources and the shared keyboard catalog into the Swift Playgrounds export. CI exercises deterministic fixtures; live provider tests are separate, explicit operations.

```bash
python3 scripts/package_ipad.py
swift test --package-path swift-verification
python3 -m unittest -q test_xcode_project test_package_ipa test_verify_ios_artifacts
```

Release artifacts record their Bitrise build, source commit and SHA-256 hashes. Unsigned bundle validation, personal signing and a successful physical-device launch are distinct checks; none implies the next.

For supervised deployment, separate workers, TLS, access control, backups and rollback, follow [DEPLOYMENT.md](DEPLOYMENT.md). The backend intentionally binds to loopback. The included private gateway provides a persistent access link and Secure HttpOnly session cookies for a single operator; it is not a multi-tenant identity system.

## Autonomous execution

The task runner plans, reads and writes real files, executes commands in disposable containers, inspects results, repairs failures, and can ask a specialist model for architectural, testing or review advice. Routine task steps require no approval clicks.

- SQLite stores jobs, schedules, leases, checkpoints, progress events and bounded lessons. Jobs survive application restarts. Multiple worker processes on the same Linux host atomically claim work; process locks serialize access to each workspace during cleanup and recovery.
- Every task has its own workspace. Sandbox containers have no network, credentials or Docker socket, and have CPU, memory, process, output and time limits. File tools reject traversal and symlinks. There is no fallback to executing generated commands on the host.
- Cancellation stops the active sandbox. Interrupted work reconciles the previous container before recovery; an independent container deadline also bounds a crashed worker's command.
- Completion requires actual nonempty files and a successful command against the current file manifest. An edit or failed command invalidates earlier verification. A separate model review must also accept the goal, source and check evidence. Receipts show the commands, exit codes, outputs and review. These checks do not guarantee that a model chose sufficient tests for every possible requirement.
- Successfully completed work can contribute bounded lessons to future tasks. This is persistent agent memory and instruction design, not model-weight training.
- A step budget and 30-minute task deadline bound execution. Operators can inspect blocked work and retry with the previous observations and files retained.

Model access supports `OPENROUTER_API_KEY`, an explicitly configured HTTPS OpenAI-compatible endpoint, or the existing NVIDIA/verified OpenCode routing. Set `SUPERCRAFTOS_MODEL` and `SUPERCRAFTOS_LIGHT_MODEL` for your available provider. Usage accounting combines actual returned token counts across processes, uses provider-reported cost when supplied, and explicitly counts unpriced requests. No model credential is committed.

```bash
.venv/bin/python main.py submit 'Build a CSV expense summarizer and test invalid amounts'
.venv/bin/python main.py jobs
.venv/bin/python main.py worker
```

Set `SUPERCRAFTOS_EMBEDDED_WORKER=0` when running a separate supervised worker. The `/api/jobs` API accepts idempotency keys, scheduled start timestamps and step budgets. See the implementation and [release verification](docs/RELEASE_VERIFICATION.md) for tested behaviors and outstanding external prerequisites.

## Existing modules

| Module | Implemented behavior | Required setup / boundary |
| --- | --- | --- |
| Autonomous tasks | Persistent plan/action/observation loop, file delivery, container execution, recovery, cancellation, specialist advice | Model credential; Docker for execution; this is not a remote desktop/device automation service |
| Product Lab | Fixed enclosure, plate and bracket templates; STEP/STL/DXF exports and geometry round-trip checks | Separate `.cad-venv`; early engineering screening, not manufacturing certification |
| Grant Ops | Official-source catalog, fit screening, draft packages and submission history | Availability must be checked with the programme; submission needs a supported configured official adapter; no funding guarantee |
| MCP | Schema-validated stdio tools, autonomous task submission/inspection/cancellation, product and grant tools | Launch `.venv/bin/python main.py mcp` with the repository as working directory |
| Legacy LangGraph workflow | Planner/builder text artifacts, durable checkpoints, explicit approve/deny review | Model credential; remains available through Workflows and `main.py task` |
| E2B | Remote bounded Python execution | E2B credential; separate from the local Docker task sandbox |
| Lark / Notion / cloud browsers | Existing messaging, encrypted credential storage and registration adapters | Service-specific credentials and permissions; absent credentials are not verified connections |
| Context.dev | Official-SDK source research for the 1inch Fusion resolver | Context.dev credential; research consumes provider credits; no trading engine is implemented |
| iPad/iPhone companion | Tasks, verified downloads, memory, accounts, quests, CAD and native utilities | Swift Playgrounds bundle; Apple compilation remains a separate release check |
| Apple Shortcuts | Send text/shared content, return tracking ID, check status, retrieve summary or checksum-verified file | [Connection and automation setup](docs/APPLE_SHORTCUTS.md); Notes/site/database access is supplied by the user’s Shortcuts actions |
| Accounts | Durable provider operation, existing-key verification, private credential storage, uncertain-signup recovery | Supported provider connection and actual native verification; no fabricated credentials or signup receipts |
| Quests | Official-source discovery, screening and durable adapter receipts | Live source availability and configured participation adapter; no reward/payment assertion |
| Rust worker | Optional Tokio protocol worker | Rust toolchain; Python service works without it |

Autonomous tasks can call the installed grant catalog/screening/drafting and product screening/CAD tools. External submissions and paid research remain explicit tools with their existing integration requirements.

Install the optional CAD environment:

```bash
python3.12 -m venv .cad-venv
.cad-venv/bin/pip install -r requirements-cad.lock
# Linux may also require libgl1 and libglu1-mesa.
```

The CAD implementation accepts validated numeric parameters for three fixed templates. It uses a separate worker with measured memory limits and a deadline. Browser registration is an independent adapter, not a browser available to the coding sandbox.

## Verify a release

```bash
.venv/bin/python main.py doctor
.venv/bin/python -m unittest discover -q
.venv/bin/pip check
# Requires Docker and the sandbox image; exercises actual isolation and crash cleanup:
SUPERCRAFTOS_TEST_DOCKER=1 .venv/bin/python -m unittest -q test_sandbox_integration
# Reproduce CI with no external network or provider secrets:
docker build -t supercraftos:check .
docker run --rm --init --network none --memory 2g --entrypoint python \
  supercraftos:check .github/ci/offline_checks.py
# Optional protocol worker:
cargo test --manifest-path agent-core/Cargo.toml
```

Tests use local transport fixtures and scripted model responses unless the real Docker suite is explicitly enabled. The CAD export test skips if its optional environment is absent. Live inference and external service checks are separate evidence; a passing offline suite does not prove provider credentials or a production account are working.

Private state lives under `data/` and is ignored by Git. Back up that directory, including `vault.key` and `access.key`, and keep model credentials outside version control. Historical reports mentioned in older research documents came from another development environment and are not prerequisites for a clean install.
