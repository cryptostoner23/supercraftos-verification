---
name: "brain-deep-research"
description: "Imported from agent-brain: deep-research"
---

# Skill: deep-research

**Purpose:** Multi-source research with adversarial verification and cited synthesis  
**Trigger:** When deep, fact-checked research is needed (not a quick lookup)  
**Source:** Claude Code (2026-06-25)

---

## When to Use vs When to Skip

**Use this skill when:**
- The question spans multiple sources and the answer isn't obvious
- Claims need to be verified (not just summarized)
- The user needs a cited, trustworthy report

**Skip and answer directly when:**
- It's a factual lookup (dates, definitions, formulas)
- The answer is already in the session context or CLAUDE.md
- A single authoritative source is sufficient

**Before starting:** If the question is underspecified (e.g. "what car should I buy" without budget/use-case/region), ask 2–3 clarifying questions first. Narrow scope → better research.

---

## Phase 1 — Fan-Out Search (3–5 parallel queries)

Run searches from different angles simultaneously:
- Primary angle: direct query
- Secondary angle: opposing view / counterargument
- Tertiary angle: recent developments / date-sensitive data
- Domain angle: expert/technical sources
- Validation angle: statistics, studies, primary sources

Record: source URL, publication date, author/org, key claim.

---

## Phase 2 — Deep Read

For each source found in Phase 1:
- Read beyond the headline — what does the full content actually say?
- Note: does it cite primary sources, or is it citing other secondary sources?
- Flag: is the content dated, paywalled, or opinion-only?

Discard sources that are:
- Undated or older than relevant for the query
- Circular (citing each other with no original data)
- Opinion presented as fact without evidence

---

## Phase 3 — Adversarial Verification

For each key claim you plan to include:
1. Actively try to find a source that contradicts it
2. If contradiction found → note the conflict, don't hide it
3. If no contradiction found after genuine effort → claim is provisionally supported

Claims that survive adversarial check → high confidence  
Claims with open contradictions → flag as "disputed" in the report

---

## Phase 4 — Synthesize

Structure the output as:
1. **TL;DR** (2–3 sentences, the answer)
2. **Key Findings** (3–7 bullet points, each citing a source)
3. **Conflicting Views** (if any — what disagrees and why)
4. **Confidence Level** (high / medium / low, with reason)
5. **Sources** (numbered list: URL, author, date, relevance)

---

## Completion Test

- [ ] At least 3 independent sources consulted?
- [ ] At least one adversarial check run per key claim?
- [ ] Conflicting views documented (not hidden)?
- [ ] Every key finding has a citation?
- [ ] TL;DR is accurate — not just a restatement of the question?

All 5 pass → deliver. Any fail → go back to the failing phase.
