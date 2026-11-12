# Execution delivery, 2026-10-30

The device app is [build 190](https://agent.commetai.ca/ios/SuperCraftOS-build-190-unsigned.ipa), with native source `d88a525`. The changes in this delivery are on the server and take effect without replacing that binary. Signing and physical iPhone installation remain the user's distribution step.

## Execution fixes

- Model calls have total wall-clock deadlines as well as connection/read timeouts. Acceptance verdicts have bounded output, with reasoning disabled where supported.
- HTTP success with an empty or truncated structured completion is a provider failure and triggers verified failover. Usage/cost reported by an unsuccessful completion is retained.
- Numeric and HTTP-date cooldowns are honored. Two bounded automatic recovery waits preserve the task and successful actions; a model request that times out does not spend an action step. Cancellation fences prevent an old worker reviving a cancelled job. External side-effecting tool timeouts are not automatically replayed as model calls.
- Detected Python tests run in the existing isolated, network-disabled Docker workspace once per revision. Zero discovered tests does not certify a delivery. Listings, file printing and echo commands cannot certify software.
- Passing source and tests go directly to independent acceptance review. Rejected acceptance returns repair feedback; it is not presented as success.
- The implementation action uses raw file blocks, validates file paths and Python syntax, then writes the batch. It avoids nested JSON source escaping. Coding uses the existing configured implementation model; specialist Web3 research continues to use the existing Web3 AI.
- Negative constraints such as “no grants, RPC or network” do not turn an unrelated coding request into a grant workflow.

## Saved task delivery

Task `fe09b5a40bcc4e318398d04062c09e58` is **completed**, with actual runnable project files, nine passing tests in the real Docker runner, and independent acceptance `{accepted:true, issues:[]}`. The malformed EBD stub was replaced by the maintainer with `projects/v4-route-verifier`; the task's repair audit identifies this origin. The worker performed verification and acceptance. This is not represented as autonomous authorship of the replacement source.

The delivered read-only route verifier has a CLI, exact-integer quote comparison, hop-continuity and minimum-output checks, hook permission review flags, deterministic fixture receipts, and usage documentation. Its scope and limitations are explicit: it does not independently simulate PoolManager or execute trades. The existing application submission was not duplicated. Grant award and payment remain external provider outcomes, not software-completion claims.

[Download source, fixtures and report](https://agent.commetai.ca/ios/SuperCraftOS-v4-route-verifier-1.0.zip). SHA256: `943cf52f5b07d7b4c7b9467b882554f0a8819ac738ad1a4f4aafa2a638ea1cd9`.

The package also built as a wheel, installed into an isolated target without runtime dependencies, and its installed CLI successfully replayed all three passing fixture routes. The installed-package output report is included in the source release.

## Validation

93 focused tests passed across worker execution/recovery, file generation/parsing, funding intent, model routing/failover/usage, rate limits, gateway, task MCP and optional-provider recovery. The nine project tests passed in Docker. Previously completed native validation remains: 46 portable Swift tests, successful arm64 build and all 15 delivered bundle checks. The public IPA and project archive were re-downloaded and matched their published hashes.

The additional unseeded coding acceptance task is `c865e507f1ae4267b3b77e9fdb65e326`; its actual state is reported in the release receipt after completion. No result is inferred from a queued or running job.
