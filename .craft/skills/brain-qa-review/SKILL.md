---
name: "brain-qa-review"
description: "Imported from agent-brain: qa-review"
---

# Skill: qa-review

**Purpose:** Final quality assurance check before any submission, deployment, or delivery  
**Trigger:** Before any deliverable — code deploy, report submission, feature handoff  
**Source:** Claude Code (2026-06-25)

---

## The 5-Point QA Check

Run all 5 before declaring anything done.

---

### 1 — No Placeholders

Search the deliverable for:
- `TODO`, `FIXME`, `PLACEHOLDER`, `YOUR_KEY_HERE`, `example.com`, `<INSERT>`
- Hardcoded test values left in production code
- Empty functions / stub implementations that aren't intentional stubs

**Pass:** Zero unintentional placeholders found  
**Fail:** Find and replace every one before proceeding

---

### 2 — Completeness

- Does the deliverable cover the full original ask — not just the easy parts?
- Are all referenced files, endpoints, or dependencies actually created/available?
- Are error states handled, not just the happy path?

**Pass:** Original ask is 100% addressed  
**Fail:** Identify what's missing, complete it, re-run this check

---

### 3 — Accuracy

- Do all stated facts (URLs, IDs, config values) match what's actually on the server/in code?
- Are version numbers current?
- Do all API endpoint paths match the running implementation?

**Pass:** Every factual claim is verifiable and correct  
**Fail:** Correct the inaccurate claims before proceeding

---

### 4 — Security

- No secrets, tokens, or passwords in the deliverable
- No SQL injection, XSS, or command injection vectors introduced
- External inputs validated at system boundaries
- No `--no-verify`, disabled TLS, or bypassed security checks

**Pass:** No security issues found  
**Fail:** Fix before delivery — security issues are never "fix later"

---

### 5 — User Perspective Test

Read the deliverable as the user would:
- If they follow the instructions literally, do they reach the right outcome?
- Are technical terms explained or at least not required to understand the main point?
- Is the format appropriate for the user's technical level?

**Pass:** A non-expert can follow/use this without getting stuck  
**Fail:** Clarify the confusing parts

---

## Completion Gate

All 5 checks pass → deliver.  
Any check fails → fix that item, re-run the failing check, then verify all 5 again.

Do not skip checks because you're confident. Confidence is not a substitute for verification.
