# Resume verification — 2026-10-30

Later changes, storage policy and delivery: [mission delivery](MISSION_DELIVERY_2026-10-30.md).

Recovered the saved conversation `01a14c47-bdf4-72b2-9e35-c2e7db95965f`
and continued in `/root/SuperCraftOS`. This report supersedes older verification
counts and operational status; it does not turn historical checks into fresh ones.

## Repairs

The root filesystem was full. The durable worker had restarted over 1,200 times
with SQLite `OperationalError`. Purged pip and uv download/build caches using their
own cache commands. The worker recovered. Application, worker and private gateway
were confirmed active after restarting the application and worker.

A live inference check returned HTTP 404 for the saved primary model,
`nvidia/nemotron-3-super-120b-a12b`. The existing lightweight model,
`nvidia/nemotron-3.5-lightning-30b-a3b`, returned valid JSON with HTTP 200 in 303 ms
for the small health probe, but struggled to execute the complete live task.
Tested an additional available model, `minimaxai/minimax-m3.1-flash`: its small
health probe passed in 1,106 ms, and a real structured code-writing request passed
in 7.59 seconds. Selected it as the runtime/default primary and retained Lightning
as the configured lightweight model. Restarted both worker services so neither
retained the previous in-memory model selection. These probes are not themselves
full task-completion evidence.

Live tasks exposed missing action parameters and repeated read/planning actions.
Replaced the generic action argument schema with action-specific required fields:
plans require acceptance checks, native tools require a tool name and nested
arguments, file writes require content, and blockers require a reason. After two
identical read-only observations, the next generation must choose a different
action. Added regression cases captured from the failed live requests and verified
a real structured native-tool request against the new schema. No task files were
manually supplied to make the acceptance run pass.

## Fresh developer verification

| Check | Result |
| --- | --- |
| Python discovery after the first action-schema repair | 372 tests run; OK, 21 skipped |
| Explicit real Docker isolation/crash recovery suite | 4 tests passed |
| Model configuration and iOS verifier regression checks | 21 tests passed |
| Portable Swift build | Passed |
| Portable Swift tests after the concurrent UI/evidence update | 45 passed |
| Python dependency consistency | No broken requirements |
| Current iOS app artifact checks | All 15 checks passed |
| Repository metadata inventory and maintained-source syntax checks | 45,541 files inventoried, 254 maintained files hashed, no detected issues |

The inventory is not a semantic audit of dependencies or every feature.
Portable Swift checks do not compile SwiftUI or prove physical-device behavior.
The routine suite's skips remain skips; the separate Docker run covers four of them.

## Fresh browser and download verification

Used Chromium against the deployed authenticated HTTPS interface. Entered the
private access key through the sign-in form; no session fixture was injected.

- Navigated all seven tabs at 1440 px and 390 px. No document horizontal overflow
  and no page JavaScript exceptions were observed during these interactions.
- Entered Product Lab specifications for plate, bracket and enclosure, screened
  each, generated real CAD and clicked all five downloads for each design.
  All 15 downloaded files were nonempty. The UI reported solid geometry and
  STEP round-trip checks. This is template CAD, not arbitrary engineering design
  or physical manufacturability certification.
- Downloaded the deployed build-179 App Playground and current personalized IPA
  over HTTPS: both HTTP 200 and valid ZIP contents/CRC. The Playground contained
  14 entries (56,196 bytes); the IPA contained 15 entries (1,106,034 bytes).
- Submitted a new standard-library JSON formatter task through the task form.
  Its execution and final outcome are recorded separately in the evidence directory.
- Executed `register_developer_account` for Steel and Firecrawl through the visible
  Tools form. Both returned `verified_existing`, `credential_verified=true` and
  a fresh authenticated native API check. No signup was attempted.

Evidence and logs: `data/audit/resume-20261030/` (private, excluded from Git).
Initial browser harness mistakes used an unsupported login path and checked the
wrong disabled element; those attempts are not counted as passes. Corrected CAD
checks waited for the entire fieldset to become enabled before downloading files.

## External requirements still open

Fresh service probes authenticated Notion, Apify, Tavily, 0x, Dune, Composio,
Browserless and The Graph. NitroStack authenticated the account only. Provider
catalog access is not inference or installed-feature verification.

Airtable, HYRVE and OpenCode rejected authentication; Skyfire denied access.
Those services cannot be represented as working until their access is corrected.
Browserless remains outside the chosen registration workflow under the owner's
preference, despite its successful independent health probe.

The account interface still records uncertain Hyperbrowser and PeerPush signup
attempts that require provider reconciliation, and DevHunt has no supported native
verification endpoint. Steel and Firecrawl existing-account verification passed
fresh native checks through the UI. No duplicate accounts were created.

Grant catalog, screening and drafting do not establish an official submission.
No new grant application, reward claim or wallet transaction was submitted in this
verification pass. Configured official intake/participation adapters and real
eligibility remain prerequisites.

The IPA requires personal Apple signing and physical-device installation/launch
verification. Linux cannot supply Apple's iOS SDK. The original request's universal
autonomous integrations, arbitrary physical-product feasibility and every external
flow are not completely implemented or verified; this project must not be labeled
fully complete on the basis of these local checks.
