---
name: pov-testing
description: Test the product from the human user's point of view with demanding real tasks, repeated visible interactions, and verified outcomes.
---

# POV TESTING SKILL

User-authored acceptance standard for SuperCraftOS, recorded 2026-10-19 by Kqcx5r.

## Required approach

Test through the actual user-facing interface as a human would. Navigate, enter real inputs, submit work, follow progress, inspect outputs, download/open files, change settings, and revisit state. Rendering or an HTTP 200 is not completion. Do not use direct backend calls, database edits, mocks, fixture injection, hidden test controls, or server-side state inspection to make a user-facing acceptance test pass. Implementation and deployment work may use developer tools, but label their checks separately from POV acceptance.

Cover every available component and module. Repeat each core path two to three times, including a fresh session and a return/reload where applicable. Inspect error handling, cancellation, retries, persistence, downloads, and cross-module navigation. Record untested platforms explicitly; web checks do not prove a SwiftUI/iPad build works.

Prefer demanding real-life tasks at the user's requested 9.5/10 complexity target. Define difficulty through concrete requirements, edge cases, dependencies, and acceptance evidence rather than inventing a numerical certification. Include actual human workflows such as registering with a platform, obtaining an API key, configuring it, and using it successfully. A registration claim requires an actual account; a working integration requires a successful authenticated operation. Do not count a catalog, a login screen, a draft, or a pending receipt as the final outcome.

Use existing user-authorized accounts, credentials, resources, and free tiers first. Keep cost as low as practical without weakening output correctness, precision, completeness, or verification. Prefer completing correctly in one attempt, but repair observed defects and retest instead of hiding failures. Do not create duplicate accounts or repeat chargeable/irreversible actions simply to increase a repetition count: repeat the user flow through existing-account recovery, idempotent operations, and credential verification where appropriate.

## Evidence and reporting

Maintain a matrix with module, scenario, prerequisites, run number, visible actions, expected result, actual result, evidence, cost if known, and pass/fail/blocked/untested status. Use browser-visible task receipts and downloaded outputs as evidence; keep screenshots and recordings free of credentials. Give concise explanations of observed decisions, changes, checks, and uncertainty. Never expose private internal reasoning, secret prompts, credentials, or unrelated private data.

Report exactly which real tasks completed and which did not. A blocked provider, expired key, missing account connection, unavailable Apple device/SDK, or insufficient resources is an explicit remaining requirement, never a simulated success. Keep working on reachable fixes; do not request repeated permission for work already authorized by the user.

For SuperCraftOS, cover autonomous task creation and completion; scheduling/cancel/retry; files and receipts; memory/forget; grants/catalog/screen/draft/submission availability; quest discovery/screen/action/receipts; Product Lab/CAD/download; engine readiness; tools/integrations; account registration; connection authentication/session restore; and native local utilities when an Apple runtime is available.
