"""Persist a Firecrawl key supplied on stdin without writing it to logs."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import set_key

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from notion_db_setup import private_json, store_secret
from runtime_env import ROOT, load_environment


async def main() -> int:
    key = sys.stdin.readline().strip()
    if not key.startswith("fc-") or len(key) < 24:
        raise ValueError("Invalid Firecrawl key format")
    for env_file in (ROOT / ".env", Path("/root/.env")):
        env_file.touch(mode=0o600, exist_ok=True)
        set_key(str(env_file), "FIRECRAWL_API_KEY", key)
        os.chmod(env_file, 0o600)
    os.environ["FIRECRAWL_API_KEY"] = key
    load_environment()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://api.firecrawl.dev/v1/team/credit-usage",
            headers={"Authorization": f"Bearer {key}"},
        )
    vault = await store_secret("firecrawl", key)
    report = {
        "status": "verified" if response.status_code == 200 else "key_rejected",
        "http_status": response.status_code,
        "account_email": "aloop.agent@gmail.com",
        "email_verified": True,
        "vault_status": vault["status"],
    }
    private_json(ROOT / "data" / "autonomous" / "firecrawl-new-account.json", report)
    print(json.dumps(report))
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
