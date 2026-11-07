---
name: "brain-h1-respond"
description: "Imported from agent-brain: h1-respond"
---

# Skill: h1-respond

**Purpose:** Write complete, placeholder-free HackerOne report responses and triage comments  
**Trigger:** When responding to or triaging an H1 security report  
**Source:** Claude Code (2026-06-25)

---

## Response Types

### Triage Response (Triager → Reporter)

Use when: first response to a new report, acknowledging receipt, asking clarifications.

Required elements:
1. Acknowledge the report and thank the researcher
2. State current triage status (New → Triaged or more info needed)
3. If more info needed: ask EXACTLY what you need, numbered list, specific questions only
4. ETA for next update (use program's stated SLA)

**Never:** Generic "we'll look at it" non-responses. Every triage response must move the report forward.

---

### Clarification Request

Use when: the report is incomplete and you can't reproduce without more information.

Required elements:
1. State specifically what step fails when following the reproduction steps
2. Ask for the exact missing information (not "can you provide more details")
3. Example: "At step 3, I receive a 403 instead of the expected response. Can you share the exact request headers you used, particularly the Authorization and Cookie headers?"

**Never:** Ask for information already in the report. Read fully first.

---

### Informative (Not Applicable)

Use when: the reported behavior is intentional, out of scope, or not a vulnerability.

Required elements:
1. Specific reason why this is informative (cite the scope document or design decision)
2. If out of scope: reference the exact program scope clause
3. If by-design: explain the design rationale briefly
4. Thank the reporter for the submission regardless

**Never:** Close as informative without explaining why. Unexplained closures create bad faith.

---

### Duplicate

Use when: the same vulnerability was already reported.

Required elements:
1. Confirm you've verified this is the same root cause (not just similar behavior)
2. Reference the original report number (if the program allows sharing it)
3. Note whether the original is fixed or still being tracked

---

### Resolved

Use when: fix has been deployed and verified.

Required elements:
1. Confirm fix deployed to production
2. State what was changed (at appropriate level of detail for the program)
3. Acknowledge the researcher's contribution
4. State whether CVE/advisory will be issued (if applicable)

---

## Quality Checks Before Posting

- [ ] No placeholder text (`[reporter_name]`, `TBD`, `TODO`)
- [ ] Specific — no vague statements like "we take security seriously"
- [ ] Matches the report's actual content (read it fully before responding)
- [ ] Correct status being set (don't mark resolved if not actually fixed)
- [ ] Professional tone — no frustration, no dismissiveness, no condescension

All 5 pass → post. Any fail → fix first.
