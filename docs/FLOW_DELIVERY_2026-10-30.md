# Live account and grant delivery — 2026-10-30

Steel and Firecrawl completed through the authenticated app. Both returned
`verified_existing`, `credential_verified=true`, and an authenticated provider API
check. Their receipt files were downloaded through the task UI and checked.
Existing-account verification now uses a fixed native workflow with no model
planning/review calls. New signups can still use the bounded browser planner.

The USD 7,500 application **SuperCraftOS: Open Uniswap v4 Route Verification Kit**
was submitted once through the app to the current official Uniswap Notion form.
The provider confirmed: **“Your response has been submitted.”**

- Packet: `9be6c6aa-ba2c-4283-bc74-834583de2504`.
- Local attempt: `442fd33a51ca0e165eeb9fe438728375`.
- Official form: https://uniswap.notion.site/bdb023b007ec444f8616d38b554163fa.
- The provider supplied no visible receipt ID; the local attempt is not presented
  as one. Submission is not a funding award.

The obsolete HubSpot link was replaced. The new adapter fills visible controls,
requires a provider confirmation, and prevents replay after dispatch. The proposal
describes future work, identifies public applicant identity as a pseudonym, and
makes no invented legal-name, deployment, TVL, revenue or personnel claims.

Open **Grants → Saved applications & provider receipts** to view the persisted
submission and download its record. Itemized budgets can now be entered in the
normal grant profile and are preserved and validated before submission.

The final focused account/grant/API suite passed **48 tests**; the earlier
integrated worker/API/account/grant suite passed **77 tests**. JavaScript syntax
validation passed. The mobile Grants page displayed the confirmation and downloaded
the record, with no page errors or horizontal overflow.

Private evidence: `data/audit/resume-20261030/direct-account-workflow-acceptance.json`,
`official-grant-ui-result.json`, `submitted-uniswap-application-record.json`, and
`submitted-grant-mobile.png`. Earlier reports saying this packet was unsubmitted
are superseded. Other providers retain their actual individual access statuses.

Skyfire recovery is complete: the supplied key passed the official buyer balance
endpoint with HTTP 200. The earlier direct 403 was a Cloudflare HTML challenge,
not a provider credential rejection. The service uses the existing server SOCKS
route via `SUPERCRAFTOS_PROVIDER_PROXY`; no token is created or charged.
`skyfire_wallet_balance` now executes from the app's Tools screen and returns
only available funds, held amounts, pending charges/deposits and a timestamp.
Actual mobile UI execution completed; evidence is private at
`data/audit/skyfire-balance-delivery.json` and
`data/audit/resume-design-20261030/skyfire-tool-mobile.png`.

The Connect screen includes developer accounts and secure reconnection for eight
providers. Keys are checked against fixed official endpoints and persisted privately
only after an accepted response. Rejected replacements preserve previous keys;
upstream bodies and credentials are excluded from the public recovery receipts.
Airtable, HYRVE and OpenCode still reject the available credentials. Pending
Hyperbrowser/PeerPush signup evidence remains preserved without duplicate signup.

Final provider/MCP/vault/API suite: 32 tests passed. The eight reconnection forms
were exercised at mobile width, including rejected-key clearing, with no page errors
or overflow. DevHunt has no supported authenticated API endpoint in the current
adapter; the catalog states that limitation rather than claiming onboarding.

## Email and public-profile workflow correction

PeerPush is now completed. The connected Gmail account supplied the official
six-digit sign-in code, the authenticated browser saved public name **HSK**, and
the saved settings were reloaded. Public profile:
https://peerpush.com/u/cryptostoner94. One SuperCraftOS API key was created,
retrieved through the website's Reveal action, stored privately and accepted by
`GET https://peerpush.com/api/v1/products?limit=1`. The durable account workflow
`f5836298948d4455b0bedc3174d40e59` completed and delivered its receipt and README.
This supersedes the earlier PeerPush verification blocker. No code or key is
included in the delivered files or source.

DevHunt is a public-profile website workflow, not a missing-API failure.
`devhunt_profile.py` implements an on-demand browser process with the private
persistent profile, a process lock, bounded execution, fixed DevHunt navigation,
visible profile controls, HSK-only name updates and a save/reload check. The MCP
`manage_devhunt_profile` tool and normal account workflow use this process.
The Accounts screen enables its public-profile action without an API key.
Website authentication evidence is kept distinct from API credential evidence.

Actual sign-in attempts reached DevHunt's Google/GitHub OAuth screens. GitHub
requested sign-in; Google rejected the browser with “This browser or app may not
be secure.” A separate Hyperbrowser attempt using the correct applicant email
received the same Google browser rejection. Hyperbrowser's email/password recovery
also explicitly reported that this email has no Email and Password login: its
existing account uses Google sign-in. These are current sign-in requirements,
not outstanding email-verification codes or evidence of a missing DevHunt API.
No account duplication, voting, product launch, purchase or OAuth grant is claimed.

Focused profile/account/API/MCP tests: 60 passed. Private browser evidence is in
`data/audit/provider-web-recovery/`. The current IPA consumes these server-side
workflow changes without another iOS build.

## Build 190: conversation and general execution repair

The native home screen now keeps requests, observed execution, stop/resume controls and authenticated file downloads together. It removes the decorative hero and workflow grid from that primary flow; all functional destinations remain. History and detailed evidence remain accessible. Activity is fetched every three seconds while active; connection failures are visible. Action budget usage is no longer presented as completion percentage. The browser workspace uses the same conversation pattern with compact history, an anchored composer, concise trace events and inline files.

The existing `/opt/web3-agent` AI is reused through `consult_web3_specialist`. Its actual OpenRouter Nemotron backend answered a live gas query using `brain_gas`. The bridge enforces the existing service's new read-only tool allowlist; it cannot invoke automation or notification tools. The deploy patch is `deploy/web3-specialist-read-only.patch`. No additional AI runtime, model download or blockchain cache was created.

General runner repairs include safe virtual `/task` and `/workspace` paths, bounded multi-file writing with validation before writes, stronger structured actions, and checkpoint-preserving provider-outage classification. Funding-specific source and project-scope enforcement supplements these general repairs; funding is one workflow, not the product scope.

Validation: 52 focused app/gateway/MCP/packaging tests; 92 account/quest/grant/product/provider/research tests; 46 portable Swift tests; four real Docker execution/isolation/cancellation/recovery tests; a separate provider-outage regression. Browser checks at 390px and 1440px found no horizontal overflow or JavaScript errors. Bitrise `ipa_release` build 190 compiled the device app successfully and the downloaded IPA passed all 15 bundle checks. No physical iPhone installation was performed here.

Release: https://agent.commetai.ca/ios/SuperCraftOS-build-190-unsigned.ipa
SHA256: `ba113203269f8c3d7e9f3fbdc5436e8ca496d96bd243e8680102612f7d824248`.
Native source: `d88a525`; subsequent browser/backend commits do not require another IPA. GitHub source is updated. About 100 GiB remains free on the root filesystem.

Outstanding outcomes: task `fe09b5a40bcc4e318398d04062c09e58` ended in a model ReadTimeout at step 24; its saved files and evidence remain, and it has not delivered the requested funded project. It was not automatically restarted for another full model budget. Hyperbrowser/DevHunt identity authentication and previously rejected provider credentials remain unresolved. The confirmed Uniswap submission is not an award or payment. These are not claimed complete by this release.

### LLM cooldown correction

Provider backlog is optional and is not a prerequisite for unrelated app functions. The LLM retry wrapper now honors both numeric and HTTP-date `Retry-After` values. Cooldowns longer than 60 seconds return control to verified fallback/checkpoint recovery instead of being shortened into an early retry. Transport retries remain bounded; credentials and validation failures are not retried unchanged. External rate limiting and model availability cannot be guaranteed by client code. This server-only correction does not change build 190's native binary.
