---
name: "brain-task-execute"
description: "Imported from agent-brain: task-execute"
---

# Skill: task-execute

**Purpose:** End-to-end agent task execution protocol  
**Trigger:** When running any marketplace task, bounty, freelance job, or web3 quest  
**Platforms:** Works across all 21+ supported platforms  
**Source:** Claude Code (2026-06-25)

---

## Execution Pipeline

```
DISCOVER → CLASSIFY → ASSIGN → EXECUTE → VERIFY → DELIVER
```

---

### Phase 1 — Discover

```
POST /api/marketplace/discover
```

Returns opportunities from 21+ platforms. Each opportunity has:
- `source`: platform name
- `category`: BUG_BOUNTY | FREELANCE_TASK | WEB3_TASK | DATA_TASK | SAAS_AUTOMATION_TASK | ARBITRAGE
- `assignedAgent`: which agent handles it
- `requiresAuth`: true if platform needs human login first
- `rewardMax`: maximum payout

Filter for `requiresAuth: false` first — these can run autonomously.

---

### Phase 2 — Classify

Classification is automatic from the discover response. If manual classification needed:

| Source keywords | Category | Agent |
|-----------------|----------|-------|
| hackerone, bugcrowd, intigriti, yeswehack | BUG_BOUNTY | bounty-hunter |
| upwork, fiverr, freelancer | FREELANCE_TASK | executor |
| gitcoin, dework, layer3, galxe | WEB3_TASK | money-maker |
| kaggle, apify, rapidapi | DATA_TASK | analyst |
| automation, integration, crm | SAAS_AUTOMATION_TASK | coder |
| arbitrage, spread, prediction | ARBITRAGE | negotiator |

---

### Phase 3 — Assign

```
POST /api/marketplace/jobs
{
  "opportunityId": "opp_XXX",
  "agentId": "bounty-hunter",   ← use assignedAgent from discover
  "expectedPayout": 500
}
```

Returns a `jobId`.

---

### Phase 4 — Execute

Execution path by category:

**BUG_BOUNTY:**
1. Recon → find in-scope targets
2. Discover vulnerabilities
3. Write report (use bounty-report-quality skill)
4. Submit via platform API or browser

**FREELANCE_TASK:**
1. Read full requirements
2. Deliver the work artifact
3. Submit via platform

**WEB3_TASK:**
1. Connect wallet or account
2. Complete on-chain or off-chain quest steps
3. Claim reward

---

### Phase 5 — Verify

Before marking complete:
- [ ] Deliverable matches the opportunity's requirements?
- [ ] Evidence of completion captured (screenshot, hash, confirmation)?
- [ ] No personal data of third parties exposed?
- [ ] Within scope — no actions taken outside what was required?

---

### Phase 6 — Deliver

```
PATCH /api/marketplace/jobs/:jobId
{ "status": "completed", "result": { ... } }
```

Update `BRANCHES.md` if this was a significant milestone.

---

## Error Handling

- **requiresAuth: true** → flag for human to authenticate, do not proceed autonomously
- **Platform rate limit** → wait and retry with exponential backoff
- **Submission rejected** → read rejection reason, fix the specific issue, resubmit once
- **Out-of-scope finding** → do not submit; note it and move to next opportunity
