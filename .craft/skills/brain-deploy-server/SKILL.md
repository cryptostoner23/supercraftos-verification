---
name: "brain-deploy-server"
description: "Imported from agent-brain: deploy-server"
---

# Skill: deploy-server

**Purpose:** Deploy latest committed code to AliCloud ECS server  
**Trigger:** When deploying Super Agent OS to production  
**Source:** Claude Code (2026-06-25)

---

## Fixed Configuration

| Item | Value |
|------|-------|
| Instance ID | `i-t4n3re71w6gxmenabh24` |
| AliCloud endpoint | `ecs.ap-southeast-1.aliyuncs.com` |
| App path | `/opt/live-v1` |
| Container stack | Docker Compose (3 containers) |
| Health check | `http://localhost:8080/api/healthz` |
| Branch | `claude/alicloud-ubuntu-deploy-23lirb` |

---

## Step 1 — Push Code

```bash
git push -u origin claude/alicloud-ubuntu-deploy-23lirb
```

---

## Step 2 — Server Deploy via RunCommand

```bash
aliyun ecs RunCommand \
  --InstanceId.1 i-t4n3re71w6gxmenabh24 \
  --endpoint ecs.ap-southeast-1.aliyuncs.com \
  --CommandContent 'cd /opt/live-v1
git fetch https://ghp_TOKEN@github.com/cryptostoner94/super-agent-os-replit.git claude/alicloud-ubuntu-deploy-23lirb:refs/heads/dev-latest
git reset --hard dev-latest
git push origin HEAD:main --force
docker compose build app 2>&1 | tail -5
docker compose up -d --force-recreate app
sleep 8
curl -sf http://localhost:8080/api/healthz && echo OK' \
  --Type RunShellScript --Timeout 300 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('InvokeId:', d.get('InvokeId'))"
```

---

## Step 3 — Poll for Result

```bash
until aliyun ecs DescribeInvocationResults \
  --InvokeId [INVOKE_ID] \
  --endpoint ecs.ap-southeast-1.aliyuncs.com 2>&1 | \
  python3 -c "import sys,json; r=json.load(sys.stdin)['Invocation']['InvocationResults']['InvocationResult']; exit(0 if r[0]['InvocationStatus'] in ['Success','Failed'] else 1)"; do sleep 3; done
```

Then read the output:
```bash
aliyun ecs DescribeInvocationResults --InvokeId [INVOKE_ID] --endpoint ecs.ap-southeast-1.aliyuncs.com 2>&1 | \
  python3 -c "import sys,json,base64; r=json.load(sys.stdin)['Invocation']['InvocationResults']['InvocationResult'][0]; print(base64.b64decode(r['Output']).decode())"
```

---

## Step 4 — Verify

```bash
# Health check
curl -sf http://localhost:8080/api/healthz

# Get auth token (replace PORTAL_KEY with actual key from container)
PASS=$(docker exec super-agent-os-ui printenv PORTAL_API_KEY)
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login -H "Content-Type: application/json" -d "{\"password\":\"$PASS\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Models
curl -s http://localhost:8080/api/models/available -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('models:', d.get('total'))"
```

---

## Rollback

```bash
# Reset to previous commit on server
cd /opt/live-v1 && git reset --hard HEAD~1 && docker compose build app && docker compose up -d --force-recreate app
```

---

## Security Rules

- NEVER commit `.env` files or secrets
- NEVER log or expose Doppler tokens in output
- Secrets live in Doppler / container environment only
- NEVER modify: brain scoring, quality gate, bounty pipeline, platform-submit
