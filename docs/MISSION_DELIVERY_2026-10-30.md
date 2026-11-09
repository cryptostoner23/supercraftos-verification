# Mission delivery — 2026-10-30

This continues conversation `01a14c47-bdf4-72b2-9e35-c2e7db95965f`.

## What changed

The web workspace uses larger typography, clearer surfaces, an operational overview,
search across goals/results/IDs, and filters for active, attention-needed and completed
missions. On phones, selecting a task brings its execution detail into view. Its current
state and next useful action appear before the recorded activity.

All installed web tools now get labeled input controls from their actual schemas.
Required values, enums, numbers, booleans, string arrays and structured arguments have
corresponding controls. Advanced JSON remains available; switching modes preserves
values and refuses invalid JSON rather than silently discarding it. This is generated
from the executable registry, so newly registered tools receive the same treatment.

The iPhone and iPad home screens both prioritize the mission stream, composer and real task results. On iPad, telemetry and topology are an optional disclosure rather than the primary workspace. The mission stream opens the selected task directly. The queue supports goal/result
search and status filtering. Tool-only task results now decode and display their native
evidence. Task details refresh while active and retain the actual recorded failure or
provider status. Both clients use a coordinated dark blue and mint palette.

The runtime rejects repeated planning without execution and retains the saved plan with
an actionable blocked status if the model does not recover. Offline tests also prove
that the model can recover from a redundant plan and finish a checked deliverable.
The model's action schema now couples each action with its required argument fields,
preventing the incomplete requests observed during live execution.

Design references: [Linear agent lifecycle](https://linear.app/developers/agent-interaction)
and [Apple content hierarchy](https://developer.apple.com/videos/play/wwdc2025/219/).
These are design references, not claims that this app implements those products.

## Fresh verification

- Python discovery: 375 tests, zero failures, 21 opt-in skips. Dependency checks pass.
- Deployed Web3 on-demand patch: four separate offline tests pass, including no
  ingestion at startup, memory-only graph access, explicit unavailable history and
  request-time RPC transport.
- Real Docker isolation/crash recovery: four tests pass separately.
- Portable Swift: 46 tests pass. These tests do not compile SwiftUI.
- Chromium: all eight sections opened at 1440, 390 and 320 pixels; 24 section/viewport
  combinations, 12 filter checks, no page errors or horizontal overflow.
- Connections hub initially loaded 20 provider records; the final hub includes 25 records; search, the attention filter and a
  direct link into the installed Browserless tool were exercised through the browser.
- Tool forms: all 22 installed tools produce controls without overflow; numeric/enum
  inputs survive JSON round trips, invalid JSON stays editable, and the generated
  product-screen form executes its real handler successfully.
- Live Product Lab: an enclosure was generated through the visible form and STEP,
  STL, DXF, specification and report files were downloaded, all nonempty. The result
  records a valid solid and STEP round trip; it does not certify manufacturing safety.
- Live autonomous coding: the JSON formatter acceptance task completed through the
  browser. Its Python source, unittest file and README were downloaded. The result,
  checks and acceptance review are recorded in the task detail.

Private evidence: `data/audit/resume-design-20261030/`. Credentials are excluded.
The macOS build and physical installation are separate verification steps; see the
release record below rather than inferring them from the portable tests.

## Storage policy

At the owner's explicit request, persisted raw blockchain transfers, swaps, pool
caches, ingestion cursors and token metadata were removed. The Web3 SQLite database
was rebuilt from approximately 85.05 billion bytes to 4.32 million bytes. Every retained
table was compared before replacement, preserving automation rules/versions, paper
account state, conversations/messages, signal history and transaction/audit records.
The separate DuckDB blockchain graph/cache was removed.

The deployed Web3 agent now defaults to on-demand mode, creates its graph connection
in memory, and does not start Rust/Python background chain ingestors or sync loops.
`/api/intel/status` reports this mode explicitly. Existing request-time RPC and token-risk
helpers remain available. Historical graph analyses require an upstream historical
adapter and return an explicit unavailable status; an empty local cache is not
presented as a historical analysis. The deployable patch is `deploy/web3-on-demand.patch`.
The live service override sets `W3A_INTEL_ON_DEMAND=1` and clears ingestion chains.

Docker build cache, npm cache, apt download cache and obsolete quarantined runtimes
were cleaned. Required sandbox images, live credentials, active app environments and
unreconciled private/source state were retained. Disk usage changed from essentially
100% to approximately 49%, leaving about 100 GiB available. `/root` and `/var/lib`
are parent totals and must not be added to their child directories.

## Use

Open the authenticated `/agents` workspace, describe a concrete result and select
**Start task**. Use **Needs attention** for blockers and **Completed** for results.
Select a task to open its activity, files and verification receipts. In **Tools**, choose
a capability and fill its labeled inputs; advanced JSON is optional. Product Lab generates
the supported enclosure, plate and bracket templates. Grant Ops screens and prepares
applications; only an actual provider acknowledgement establishes a submission.

No new grant award, reward receipt, universal account signup, trading execution or
physical iPhone launch is asserted. Missing third-party access and unsupported official
intakes remain real external requirements.

## iOS release

[Bitrise build 189](https://app.bitrise.io/build/dc033f19-aafa-46e4-87a2-a247563e6fa0)
compiled native source commit `116c522652a104fe4fa8bef97ca78ecddeb4b41a` successfully.
The downloaded app archive passed all 15 bundle checks. The generated IPA passed ZIP
CRC, Payload layout, expected server-origin and absence-of-embedded-key checks.

- [Unsigned IPA](https://agent.commetai.ca/ios/SuperCraftOS-build-189-unsigned.ipa)
- [Swift Playgrounds source](https://agent.commetai.ca/ios/SuperCraftOS-Swift-Playgrounds-build-189.swiftpm.zip)
- IPA SHA-256: `73a3d55db40d3f69814f9ecfd5201c1e2d6ba824c7eb9fa0890479e48d92ddb2`.

Signing/installing with the owner's Apple account and physical-device launch remain
separate steps. Credentials are kept in Keychain after connecting with the private
access link; this release does not distribute access keys inside build artifacts.

Full baseline Bitrise build 181 also passed: app and keyboard simulator/device
compilation, fixture backend tests, six keyboard interaction tests and all eight
app UI interaction tests. The later iPhone/iPad acceptance build 188 stalled at simulator runner launch and
was stopped to preserve resources; no passing UI result is attributed to it. The
current mission-first app compiled successfully for devices in build 189.
