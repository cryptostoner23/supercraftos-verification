---
name: "brain-pm-kanban-todo"
description: "Imported from agent-brain: pm-kanban-todo"
---

# Skill: pm-kanban-todo

**Purpose:** Visible project-management backbone — todo, kanban, milestones, linear progress, hourly ledger, snapshot. Drives execution end-to-end with evidence gates.
**Trigger:** When planning, tracking, or executing any multi-step coding project; when a visible board (plan-of-action + progress) is needed for any agent, coding or not.
**Scope:** AI-agnostic; works with any agent via plain markdown + a stdlib CLI.
**Source:** Hermes Agent (2026-09-27)

---

## What it Is

A visible, always-current register + board so ANY agent can pick up, drive, and hand off work with zero ambiguity. Source of truth is `pm/state.json`; all views (`TODO.md`, `KANBAN.md`, `PROGRESS.md`, `LEDGER.md`, `SNAPSHOT.md`) are rendered from it, so the board never drifts.

## Files (created by `pmkanban init`)

- `pm/state.json` — source of truth
- `pm/TODO.md` — task register (by state)
- `pm/KANBAN.md` — board (lanes: BACKLOG READY IN_PROGRESS BLOCKED QA DONE)
- `pm/PROGRESS.md` — milestones + linear progress % to finish
- `pm/LEDGER.md` — hourly ledger (auto + `pmkanban hr "..."`)
- `pm/SNAPSHOT.md` — one-pass photographic capture (chain+ms+board+ledger)
- `pm/evidence/` — acceptance evidence for DONE / 100% milestones

## CLI (stdlib-only, `pmkanban`)

`init`, `auth <doc>`, `new --owner/--dep/--done/--lane/--ref`, `move <ID> <LANE>`, `block`, `done <ID> <ev_path>`, `log`, `hr "..."`, `milestone <MS> <pct>`, `progress`, `chain`, `snapshot`, `amplify [--doc]`, `ls`.

## Gates (what makes it honest, not a toy)

1. Every card needs acceptance (`done=...`) before it can start.
2. A card whose dependency is not DONE cannot start / cannot close.
3. DONE requires real evidence on disk in `pm/evidence/<ID>*`; `done <ID> <path>` is the only path through.
4. 100% milestones need an evidence file.
5. Board never drifts (rendered from state on every write).
6. Authority-doc source of truth: plan items derive from official docs (no assumptions); amplified cards carry `ref:`.

## Chains & progress

- `chain` — dependency-ordered start→finish sequence.
- `progress` — overall % = 60% card completion + 40% milestone average, live bar.

## Responsive board (desktop + phone)

`boardserve --proj <path> --port 8181` serves a responsive HTML board (6 lanes; horizontal desktop, 1-col phone ≤520px) with live progress, milestones, evidence count, auto-refresh. Open `http://<host>:8181/`.

## Pitfalls

- Board says DONE but code unverified → board has zero value. Evidence gate is non-negotiable.
- Editing TODO/KANBAN by hand → drifts; use the CLI.
- Renumbering IDs → breaks TODO↔KANBAN↔log links. Never renumber.
