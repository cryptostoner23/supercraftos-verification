---
name: "brain-cli-first"
description: "Imported from agent-brain: cli-first"
---

# Skill: cli-first

**Purpose:** Always prefer CLI commands and API calls when credentials exist. Never ask for something already documented.  
**Trigger:** Before any action involving a platform, service, or tool.  
**Source:** Claude Code (2026-06-25)

---

## Step 1 — Check Credentials Inventory First

Before asking the user for anything, check:
1. Session context file (CLAUDE.md or equivalent) — server IDs, tokens, deploy commands
2. Container environment — `docker exec CONTAINER printenv` for running services
3. `.env` files on server
4. Session history — credentials shared earlier in conversation

**Never ask the user for things already documented.**

---

## Step 2 — CLI Over Browser

| Task | Avoid | Prefer |
|------|-------|--------|
| Server management | Web console, SSH | `aliyun ecs RunCommand` |
| GitHub operations | Web UI clicking | GitHub MCP tools / `gh` CLI |
| Container checks | Web dashboards | `docker exec / docker logs` |
| API testing | Browser DevTools | `curl` |
| Secret management | Web UI | `doppler secrets get KEY` |
| Deployments | Manual upload | `git push` + RunCommand |

---

## Step 3 — API Before Browser for Platform Tasks

Check credentials → if they exist → use API/CLI, not browser.

```
Platform      Credential keys to check
HackerOne  →  HACKERONE_API_KEY + HACKERONE_USERNAME
Bugcrowd   →  BUGCROWD_API_TOKEN + BUGCROWD_HTTP_USERNAME
YesWeHack  →  YESWEHACK_EMAIL + YESWEHACK_PASSWORD
Telegram   →  TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
GitHub     →  GITHUB_TOKEN or GitHub MCP session tools
```

---

## Completion Test

- [ ] Checked session context before asking user for any credential?
- [ ] Used CLI/API instead of browser where both exist?
- [ ] Not re-asking for something provided in this session?

All 3 pass → proceed.
