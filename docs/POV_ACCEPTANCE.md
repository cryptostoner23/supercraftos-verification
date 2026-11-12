# POV acceptance — 2026-10-19

Tests used the deployed private HTTPS UI, visible controls, actual form submission,
status views and downloads. Desktop viewport 1440px; mobile viewport 390px. Browser
screenshots and JSON evidence are retained in the workspace. Credentials are excluded.

| Module / scenario | Repetitions | Actual outcome |
| --- | --- | --- |
| Login, session restoration, six-tab navigation | Fresh/reused sessions, desktop/mobile | Passed; six functional tabs, no document horizontal overflow |
| Mobile keyboard navigation | End key to final tab | Passed; final tab focused and visible inside scrollable navigation |
| Task scheduling and cancellation | 3 | Passed; each correct selected goal was visibly cancelled before its future scheduled start |
| Account task retry | 1 | Passed queue transition; provider verification result still assessed separately |
| Product Lab enclosure/plate/bracket | 3 | Passed actual screening/build and STEP/STL/DXF/report/spec downloads, all nonempty |
| Product Lab changed dimensions | 3 | Passed; old exports invalidated after changing the draft |
| Grant profile/screen/draft/download | 3 | Passed; project details retained in downloaded JSON. No submission claimed |
| Quest discovery and ranking | 3 | First runs returned zero leads. Investigation identified dynamic HTML shells and nonmatching RSS; fixed explicit source outcome reporting. Live retest required |
| MCP catalog search, empty search and reset | 3 | Passed, including the new account tool |
| Legacy control views and return-to-tasks link | 3 | Navigation/state visibility passed; no external-message runtime or approval workflow executed |
| Integration/account catalogs | 3 | Actual stored health/blocker records visible; presence alone is not live verification |
| Warehouse event ledger task | 1 initial run | In progress at report preparation; not yet counted as a completed acceptance pass |
| Incident triage task | 1 initial run | In progress at report preparation; not yet counted as a completed acceptance pass |
| Existing Steel credential verification | 1 retry queued | Result pending at report preparation; no account creation claimed |
| Memory source navigation/forget | Pending | Requires a completed UI-created task with a retained lesson |
| Native SwiftUI / Apple Shortcuts | Deferred by owner | Apple SDK/device compilation and interaction remain outside the completed checks |

Demanding task goals include exact decimal accounting, Unicode, timezone-aware
normalization, transaction rollback, conflicting duplicates, deterministic exports,
malformed streaming input, secret redaction and tests of actual edge cases. A numeric
9.5/10 label is not a certification. Failed or incomplete tasks stay visible here.

Some early browser harness attempts selected stale task details or waited on a
final message containing “Screening”; those attempts were discarded, and selection
waits were corrected to match the exact goal before mutating a task. A cancelled
account task was retried visibly. Those harness corrections are not app passes.

Testing reused existing infrastructure/provider credentials and did not purchase
plans or create duplicate accounts to inflate repetition counts. Provider usage
prices were not independently audited; no assertion of zero total cost is made.
