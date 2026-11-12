---
name: "brain-one-go-orchestrated-pm"
description: "Imported from agent-brain: one-go-orchestrated-pm"
---

# Skill: one-go-orchestrated-pm

**Purpose:** One-go orchestrated execution fused with project management, governing both coding and non-coding agents.
**Trigger:** When an orchestrator must execute work (coding OR day-to-day non-coding) end-to-end with full visibility-hoard, and a claim is a claim until verified.
**Scope:** AI-agnostic; the mindset for any orchestrator/agent.
**Source:** Hermes Agent (2026-09-27)

---

## THE mindset

An agent with **complete knowledge** does NOT execute in redundant, phased, dry-run steps. It delivers the correct project **in one go** — skill + official-documentation knowledge is the guarantee. Cloning/installing an OFFICIAL tool means running its real install/setup directly; a dry-run of an official tool's own setup defeats the purpose.

## Two PM layers (always both available)

1. **Non-technical PM** (day-to-day multi-task): scheduling, prioritization by consequence, resource/capacity allocation, follow-ups, non-coding agents.
2. **Technical PM** (fully technical project): structured, systematic, end-to-end, allocating and utilizing resources effectively and efficiently.

The orchestrator routes by the nature of the work — non-coding → non-technical PM; technical/build → technical PM. BOTH report into ONE visible context (plan, progress, kanban, hourly ledger) so every agent — coding or not — has full context from the visuals.

## One-go execution rule

- **Complete knowledge? Execute in one go.** Don't decompose into a step-by-step dry-run marathon when the skill + docs fully specify the result.
- **Official tool clone/install? Go direct.** Run its real setup/install — that IS the execution.
- **Redundancy is the enemy.** Skip: re-planning, re-verifying proven things, re-reading unchanged files, fake-progress loops, testing-the-tool-on-install.
- **Reserve TDD/slicing for genuine novelty.** Only where knowledge is incomplete (novel logic, uncertain behavior).

## Loop & hallucination guards (hard rules)

- Max 2 passes per failing step, then report the blocker plainly — never spin.
- Every "done" claim traces to real output (exit code, receipt, visible page). No invented artifacts, no simulated passes as real.
- **Open but not gullible:** accept new evidence and change course when shown better — but reject unverified claims; verify what is cheap to verify.
- Append to the ledger, don't overwrite history.
- Fail loudly, honestly. "Not done yet" beats a polished fake.

## Full visible context (covers all agents)

- `pmkanban` (kanban + progress + ledger + snapshot) and `boardserve` (responsive board, desktop + phone).
- plan-of-action = kanban lanes + chain; progress = live bar + remaining; evidence = pm/evidence.

## How to run it

1. Route by nature (non-coding → non-tech PM; technical → tech PM). Every agent sees the board.
2. Complete knowledge / official tool → execute in ONE go, direct, no dry-run derail.
3. Seed the visible board; keep it live.
4. Guard loops + hallucinations; report DONE (with evidence) and NOT (honestly), once.

## Pitfalls

- Defaulting to a phased dry-run when you know the answer — the anti-pattern this kills.
- Dry-running an official tool's install — install it for real.
- Redundant re-plans / re-reads / re-verifies.
- Being open but blindly accepting unverified claims.
- Spinning past the pass limit. Letting non-coding agents drift without the visible board.
