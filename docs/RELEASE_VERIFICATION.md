# Release verification — 2026-10-19

The Linux service is deployed with supervised non-root application, worker and
private gateway services, durable state, TLS ingress and a daily private backup.
The native app and App Playground archive are generated from the same source.
Apple SDK compilation is explicitly deferred to Swift Playgrounds by the owner.
This report separates implementation checks from real user-facing acceptance.

## Developer checks

| Check | Observed result |
| --- | --- |
| Python 3.12 native integrated suite | 196 tests passed, including real Docker and CAD generation; subsequent focused runtime/model/account/backup checks: 63 passed |
| Clean core Docker image, no network or mounted secrets | 196 discovered: 191 passed, 5 intentional skips (one optional CAD generation, four opt-in Docker tests) |
| Latest quest parser/regression suite | 31 passed, including six additional dynamic-page/RSS cases |
| Swift shared networking/models/utilities | 8 tests passed with Swift 6.0.3; all app source files parsed |
| Swift archive | All 12 bundle files match canonical sources; deterministic ZIP corruption/content checks passed |
| Configuration | Compose validation, actionlint, Python compilation and dependency checks passed |
| Sandbox lifecycle | Real Docker execution, failed command, timeouts, cancellation cleanup, killed-worker recovery, no network/credential forwarding passed |
| Gateway | Authentication, exact Host/Origin checks, mixed invalid bearer/cookie rejection, bounded handlers and early anonymous rejection passed |
| Backup | SQLite WAL snapshot and private archive checks passed; deployed timer and initial archive verified |
| Optional Rust worker | Built and cargo test completed; the crate contains zero Rust tests |

Commands and installation prerequisites are in [DEPLOYMENT.md](../DEPLOYMENT.md).
The offline core image deliberately excludes CAD and the Docker socket; its skips
are covered by the separate native integration run, not claimed as image coverage.

## Real model execution

The existing live NVIDIA route returned real completions. An expense-summarizer
job delivered source, README, sample CSV and nine passing tests, plus a demonstrated
CLI invocation and an accepted independent review. A seeded missing-CSV-cell repair
case exposed model repetition/protocol problems: canonical/flat response handling,
structured generation, tool-argument history, recent check context and repeated
command guards were strengthened. Its repair ran two new tests successfully but
exhausted its step budget before final delivery; it is not a passed acceptance run.

Two larger UI-created jobs exercise warehouse event reconciliation and SaaS incident
triage. Their final observed results belong in the POV report. Model success is
not inferred from a queued/running state or from self-authored tests alone.

## User-facing checks

See [POV testing](POV_ACCEPTANCE.md) and the saved [POV TESTING SKILL](POV_TESTING_SKILL.md).
Live browser checks use the public authenticated UI, real forms, navigation,
clicks, downloads and returned task receipts. Developer fixtures are not counted
as provider account creation or real user acceptance.

## Provider and platform boundaries

- Existing credentials were retained server-side. NVIDIA inference works. Some
  supplied providers reject authentication or time out; a key’s presence is not a
  verified integration. The UI reports measured or stored provider state.
- Galxe and Zealy Explore currently return JavaScript application shells to the
  HTTP discovery adapter. They are explicitly unavailable there. Bloomberg returned
  two real articles without the configured launch/quest signals, a valid no-match
  result. No campaign, participation or reward is fabricated.
- Registration success requires a native authenticated provider response. Pending
  email/challenge flows, missing verification APIs and uncertain attempts stay
  blocked/pending and are not blindly replayed. DevHunt has no supported native
  verification endpoint in this release.
- Grants can be screened and drafted. External submission requires a configured
  official intake adapter; a draft is not a submitted application or awarded grant.
- Native SwiftUI/App Intents rendering, Apple SDK compilation, Siri discovery,
  Shortcuts installation/chaining and device Keychain behavior are unverified here.
  No Mac allocation was available. Linux parsing/core tests do not prove them.
- GitHub Actions previously returned startup_failure before creating any jobs
  (BuildFailed workflow record); local equivalent checks passed. Hosted CI success
  must be assessed separately from those local results.

This is an original runtime, tool, instruction and retrieval-memory implementation.
No model weights were trained and no private Solid internals are included. Sandboxed
commands have no external network or credentials; native integrations provide their
explicit configured capabilities. No universal arbitrary-site/database/device
control, reward guarantee, or error-free generated code is claimed.
