---
name: "brain-genuine-audit"
description: "Imported from agent-brain: genuine-audit"
---

# Skill: genuine-audit

**Purpose:** SERIOUS auditing — verify delivered work genuinely, never lie. Treat every self-report, claim, and kanban DONE card as an unverified CLAIM to be checked against reality, then report exactly what is found.
**Trigger:** Before accepting any agent's "done/works/successful" claim, before shipping a deliverable, or whenever a kanban DONE card appears. Use as the "not lying" enforcement layer on top of verification.
**Scope:** AI-agnostic; pairs with `verification-and-proof`. Uses the `pmaudit` CLI.
**Source:** Hermes Agent (2026-09-27)

---

## Core rule

**A claim is a claim until verified.** "I built it," "it works," "profit is positive," "uploaded successfully," a kanban DONE card — all unverified until audited against real evidence.

## Audit by layer

1. **Code/artifact:** syntax/build/tests actually run here with captured exit codes — not reported. No placeholder stubs, no symlink-to-nothing, no dependency impostor. Flag re-skins (hash/diff vs known baseline).
2. **Claims/done-state:** every DONE card points to a real evidence file whose CONTENT proves the claim (read it, don't trust the filename). "Done" = real run log + exit code + (web) visible page, not a listening port.
3. **External side effects:** deploys/uploads/contracts demand a verifiable handle (URL, id, txhash), then YOU read the live handle. An agent's "uploaded" is a claim; the live URL is the fact. On-chain needs real mined receipts or fresh reads — simulation/stale "confirmed profit" is NOT proof.
4. **The auditor itself:** record what you ACTUALLY verified vs inferred; report gaps and unknowns; "we did not verify X" is a valid outcome.

## Method (bounded)

claim → evidence path required (absent = FAIL) → reproduce/run evidence yourself → compare to claim → log PASS/FAIL/UNVERIFIED with basis → verdict SUPPORTED/REFUTED/UNVERIFIED → fix only genuine defects, never re-run an identical fake.

## Genuine, not lying — rules

- Never accept a self-report as proof; never count compiled as works; never let a port stand for a feature.
- Never invent evidence, screenshots, receipts, hashes; never let simulation stand for real execution.
- Never repeat an unverified claim as fact; say "we do not know / did not verify" plainly.
- Open to refuting evidence; a passed audit is not sacred.

## Tool: pmaudit

`pmaudit --proj <path> [--loud]` audits DONE cards vs their evidence: reads real file content (not the name); SUPPORTED/REFUTED/UNVERIFIED; empty or absent evidence = REFUTED; reports genuine support rate and demands REFUTED cards leave DONE until real evidence exists. Never fabricates.

## Pitfalls

- Auditing a filename instead of its content.
- Trusting a teammate/agent sub-report.
- Counting compile as working / a port as a feature.
- Letting a plausible "done" slide to fit the expected story — distrust with reason, not accept with hope.
- Loops: max 2 passes per check, then UNVERIFIED/REFUTED and report.
