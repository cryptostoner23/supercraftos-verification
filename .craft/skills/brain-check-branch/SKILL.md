---
name: "brain-check-branch"
description: "Imported from agent-brain: check-branch"
---

# Skill: check-branch

**Purpose:** Branch verification + index maintenance  
**Trigger:** Every session start. Before every git push, PR, or branch creation.  
**Source:** Claude Code (2026-06-25)

---

## What This Does

1. Confirms the AI is on the correct branch before making any changes
2. Reads the branch index (BRANCHES.md) to understand the full repo state
3. Checks for active PRs and GitHub Actions workflows
4. Updates BRANCHES.md whenever branch state changes

---

## Step 1 — Verify Current Branch

```bash
git branch --show-current
git status --short
git log --oneline -3
```

Compare to the expected branch from the project's session context file (CLAUDE.md or equivalent).

**If mismatch:** Stop. Report actual vs expected branch. Switch before proceeding.  
**If detached HEAD:** Stop. Report state. Ask user before proceeding.

---

## Step 2 — Read the Branch Index

Look for `BRANCHES.md` in repo root.  
**Found:** Read it. Don't create redundant branches.  
**Not found:** Create it using the template in Step 4.

---

## Step 3 — Check for GitHub Actions

```bash
ls .github/workflows/ 2>/dev/null | head -10
```

Note any workflows in BRANCHES.md. Note open PRs when you learn of them.

---

## Step 4 — Update BRANCHES.md

Update after: new branch created/deleted, PR opened/merged/closed, new Action added, agent scope changes.

```markdown
# Branch Index

_Last updated: YYYY-MM-DD by [AI name]_

## Active Branches

| Branch | Owner | Purpose | Last Updated | Status |
|--------|-------|---------|--------------|--------|
| `main` | All AIs | Production-ready amalgamated code | YYYY-MM-DD | Live |

## Open Pull Requests

| # | Title | Branch → Target | Opened | What It Does |
|---|-------|----------------|--------|--------------|

## GitHub Actions

| File | Trigger | What It Does | Status |
|------|---------|--------------|--------|

## Plain English Guide

- Branch = a working copy of the code. Changes stay isolated until merged.
- PR = a formal request to move changes from one branch into another.
- GitHub Action = an automated script that runs when code is pushed.
- Main = the stable, live version. Always deployable.
```

---

## Completion Test

- [ ] Current branch confirmed correct (or switched)?
- [ ] BRANCHES.md exists and is current?
- [ ] No duplicate or stale branches that should be cleaned up?
- [ ] Any open PRs or pending Actions flagged for the user?

All 4 pass → continue. Any fail → fix first.
