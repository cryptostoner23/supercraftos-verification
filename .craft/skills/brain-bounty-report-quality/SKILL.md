---
name: "brain-bounty-report-quality"
description: "Imported from agent-brain: bounty-report-quality"
---

# Skill: bounty-report-quality

**Purpose:** Component-level quality gate for bug bounty reports using STAR methodology  
**Trigger:** Before writing any bounty report section. Validate each section before moving to the next.  
**Target:** 75%+ quality floor automatically when process is followed  
**Source:** Claude Code (2026-06-25)

---

## STAR × 6 Components Framework

Every bounty report tells one story. STAR is the narrative spine:

```
SITUATION  →  Component 1 (Title) + Component 2 (Summary: context)
TASK       →  Component 2 (Summary: attacker capability) + Component 4 (Impact)
ACTION     →  Component 3 (Steps to Reproduce) + Component 5 (Evidence)
RESULT     →  Component 4 (Impact: achieved) + Component 6 (Remediation: prevent)
```

---

## Source of Truth — Only These Are Allowed

| Allowed | Not Allowed |
|---------|-------------|
| Program's policy / scope document | Assumptions about scope |
| Actual vulnerability observed and reproduced | Theoretical, unverified vulnerabilities |
| Steps you actually performed | Steps that "should" work but weren't tested |
| Real evidence: screenshots, HTTP requests, PoC | Fabricated or hypothetical evidence |
| The target's actual behavior | What the target "typically" does |
| CVE/CWE that directly matches | Generic references that loosely apply |

---

## Component 1 — Title [SITUATION]

One sentence: Vulnerability type + affected component + impact.

**Completion test:**
- [ ] Matches what program scope covers?
- [ ] Vulnerability type is correct (not a guess)?
- [ ] Triage engineer understands the issue from the title alone?

---

## Component 2 — Vulnerability Summary [SITUATION + TASK]

3–5 sentences. Situation: what system, what feature, what was observed. Task: what can an attacker do?

**Completion test:**
- [ ] Situation names the exact endpoint, feature, or component?
- [ ] Task is framed as attacker capability, not abstract flaw?
- [ ] Every claim sourced from direct observation?
- [ ] No copy-paste from generic templates?

---

## Component 3 — Steps to Reproduce [ACTION]

Numbered, exact, reproducible steps. Each step = one concrete action with exact inputs (URLs, params, payloads, headers). No skipped steps.

**Completion test:**
- [ ] Steps were actually performed and produced the described result?
- [ ] All parameters, headers, payloads shown exactly as used?
- [ ] Another researcher following these steps hits the same bug?
- [ ] Evidence (Component 5) matches what these steps produce?

---

## Component 4 — Impact [TASK + RESULT]

What the attacker achieves. State in CIA triad terms. Tie to program's stated assets.

**Completion test:**
- [ ] Impact grounded in what was proven, not theoretical chaining?
- [ ] Matches program's severity criteria?
- [ ] No severity inflation — realistic scenario only?
- [ ] Answers: "What can an attacker now do that they couldn't before?"

---

## Component 5 — Evidence [ACTION proof]

Screenshots, HTTP request/response, PoC code, video. Proves the action happened.

**Completion test:**
- [ ] Evidence directly shows the vulnerability?
- [ ] Matches exact steps in Component 3 (same payload, same endpoint)?
- [ ] Sensitive data (real PII, credentials) redacted?
- [ ] Covers both the trigger (action) and the outcome (result)?

---

## Component 6 — Remediation [RESULT → response]

One specific, implementable fix for the exact root cause. Not generic advice.

**Completion test:**
- [ ] Fix directly addresses root cause, not a symptom?
- [ ] Implementable by the program's team with their current stack?
- [ ] References the CWE / OWASP entry that directly applies?
- [ ] If implemented, would it prevent Component 3 steps from succeeding?

---

## Final Alignment Check

1. **In scope?** — Target, vulnerability class, impact all confirmed in-scope
2. **STAR coherent?** — Situation → Task → Action → Result is one consistent story
3. **Not a duplicate?** — Checked platform's known issues and disclosed reports
4. **Severity aligned?** — Assigned severity matches program's CVSS matrix
5. **No out-of-scope actions?** — No automated scanning, no unauthorized data access
6. **Language neutral?** — No urgency manipulation, no threats, no demands

All 6 pass → submit. Any fail → fix that component, re-run its test, re-run this check.
