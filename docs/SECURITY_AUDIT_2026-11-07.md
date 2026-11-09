# Security & Completion Audit — 2026-11-07

Principal audit of the repository against the "Advanced Product Upgrade & Completion"
directive. This record lists what was actually inspected and changed, the evidence
for each fix, and the work that remains blocked on tooling this environment does not
have (macOS/Xcode toolchain, live backend, physical devices). Nothing here is
fabricated: every "verified" item was checked with repository reads and static
searches during this session; every "blocked" item says exactly why.

## Critical finding and remediation (fixed in source, rotation still required)

**Finding C-1 — Live production gateway access key committed in plaintext.**
The gateway bearer key for `https://agent.commetai.ca` was hardcoded in four
tracked files and pushed to `origin` (public GitHub):
`ios_app_dist/ci_xcode/Info.plist`, `README.md`, `DEVICE_E2E.md`, `test_e2e.py`.
Anyone with repository access could authenticate to the private gateway as the app.

**Remediation applied this session:**
- `ios_app_dist/ci_xcode/Info.plist`: key replaced with the `$(SUPERCRAFTOS_ACCESS_KEY)` build variable.
- `ios_app_dist/ci_xcode/project.yml`: `SUPERCRAFTOS_ACCESS_KEY: ""` added with provisioning instructions (`xcodebuild SUPERCRAFTOS_ACCESS_KEY="$(cat data/access.key)"`). Empty value keeps the manual connect path working.
- `test_e2e.py`: reads `SUPERCRAFTOS_E2E_KEY` only; the suite now skips with an explicit message instead of shipping a default credential.
- `README.md` / `DEVICE_E2E.md`: literal key replaced with provisioning/rotation guidance.
- `scripts/audit_repository.py`: added static secret scanning (40+ character opaque tokens, known leaked literals, hardcoded provider-key assignments) across all maintained text formats, so a recurrence fails the audit.

**Verified evidence:** repository-wide search for the leaked key and its suffix
returns zero matches after the edits (4 matches before). No other hardcoded
provider credentials were found in tracked files; `.env.example` ships only
empty values.

**Required operator action (cannot be done from this device):**
1. Rotate the gateway key now: on the server, delete `data/access.key` and restart
   `private_gateway.py` (it generates a fresh key, chmod 600). The published key
   must be considered revoked until this is done.
2. Optionally rewrite/purge the leaked blob from GitHub history; rotation makes
   the old value worthless either way.
3. Push the remediation commit once reviewed.

## Verified working as designed (inspected, not executed)

- `private_gateway.py`: HMAC-signed session cookies, `__Host-` cookie scope, exact
  Origin enforcement, bearer compare_digest, request-size and slot limits, 502
  degradation when the backend is down. Sound single-operator design.
- `CredentialStore.swift` + `AppConfig.swift`: Keychain storage
  (`kSecAttrAccessibleWhenUnlockedThisDeviceOnly`), owner-scoped approvals,
  no anonymous session requests (covered by `BackendClientTests.swift`).
- `project.yml`: app, keyboard, share extension, unit/UI/interaction test targets
  all declared; keyboard deliberately not embedded (documented rationale).
- `main.py`: memory-budget supervision, durable workflow-owner binding, atomic
  writes (tmp+replace, 0600), credential-free error output.

## Blocked in this environment (not executable here — running on an iPhone)

- Compiling the app/keyboard or running `bitrise run` (macOS-only: Xcode,
  `xcodebuild`, `xcodegen`), therefore no new IPA was produced this session.
- Running the Python test suite or the audit script (no shell on this device);
  the audit change was verified by re-reading the edited file, not executed.
- Revyl physical-device sessions (requires a fresh build and the rotated key
  provisioned per run, per `DEVICE_E2E.md`).
- Server-side key rotation and gateway restart (server is remote).

## Acceptance matrix (directive requirement → status)

| Requirement | Status | Evidence / next step |
|---|---|---|
| Audit existing implementation | Done | This record; static inspection of gateway, app client, build config |
| Remove committed secrets | Fixed in source | Search: 0 matches; audit scanner added |
| Secret-leak regression guard | Done | `scripts/audit_repository.py` scanning; enforced remotely by GitHub Actions (`repository-audit` job in `.github/workflows/ci.yml`) |
| Key rotation on server | **Blocked: operator** | Delete `data/access.key`, restart gateway |
| Rebuild IPA via Bitrise | **Blocked: macOS** | `bitrise run --config bitrise.yml --workflow primary` |
| Revyl device testing | **Blocked: fresh IPA** | Re-run `.revyl/tests/*` suites after build with provisioned key |
| Full feature completion per directive | Out of scope for a single static pass | Product is substantially built (backend, app, tests, CI); completion claims require the blocked builds/tests above |
