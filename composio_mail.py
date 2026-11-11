"""Gmail/notes integration via Composio (preferred) with IMAP fallback.

This module exposes durable, real integrations:

  * Composio — when COMPOSIO_API_KEY is set and a Gmail account is connected
    through Composio's auth flow, it uses Composio's Gmail tools to send and
    read mail.
  * IMAP fallback — when GMAIL_ADDRESS + GMAIL_APP_PASSWORD (or OAuth token)
    are set, it reads the inbox directly over IMAP.

All operations either succeed with real evidence or return a clear, honest
status (e.g. authentic_required). Nothing is simulated.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import httpx


# ── Composio helpers ─────────────────────────────────────────────────────────

_env_loaded = False


def _ensure_env():
    global _env_loaded
    if not _env_loaded:
        try:
            from runtime_env import load_environment
            load_environment()
        except Exception:
            pass
        _env_loaded = True


def composio_key() -> str:
    _ensure_env()
    return os.getenv("COMPOSIO_API_KEY") or ""


def composio_base() -> str:
    # The Composio MCP endpoint is the supported route for account-authenticated
    # tool execution. The legacy v1 REST API and CLI are retired.
    return os.getenv("COMPOSIO_MCP_URL", "https://connect.composio.dev/mcp")


async def _composio_headers() -> Dict[str, str]:
    key = composio_key()
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if key:
        # MCP clients authenticate with the consumer API key in this header.
        headers["x-consumer-api-key"] = key
    return headers


def _parse_mcp_sse(raw: bytes) -> List[Any]:
    """Extract the JSON payloads from an MCP SSE response."""
    results: List[Any] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if line.startswith("data: "):
            payload = line[len("data: "):]
            try:
                results.append(json.loads(payload))
            except (ValueError, json.JSONDecodeError):
                continue
    return results


async def _mcp_call(method: str, params: Dict[str, Any], request_id: int) -> Any:
    """Perform a JSON-RPC call over the Composio MCP endpoint."""
    key = composio_key()
    if not key:
        raise RuntimeError("COMPOSIO_API_KEY is required for Composio mail")
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=15)) as client:
        resp = await client.post(composio_base(), headers=await _composio_headers(), json=payload)
        resp.raise_for_status()
        messages = _parse_mcp_sse(resp.content)
        for msg in messages:
            if msg.get("id") == request_id:
                if "error" in msg:
                    raise RuntimeError(f"Composio MCP error: {msg['error']}")
                return msg.get("result")
    return None


def _extract_text_json(result: Any) -> Any:
    """MCP tool results carry the JSON payload as text inside content[].text."""
    if isinstance(result, dict):
        content = result.get("content") or []
        for item in content:
            text = item.get("text") if isinstance(item, dict) else None
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except (ValueError, json.JSONDecodeError):
                    continue
    return result


async def composio_list_connected_accounts() -> List[Dict[str, Any]]:
    """Return the connected Gmail accounts via the Composio MCP search tool.

    Returns a list of records with keys: app, status, id, email, alias.
    """
    try:
        result = await _mcp_call("tools/call", {
            "name": "COMPOSIO_SEARCH_TOOLS",
            "arguments": {"query": "GMAIL_GET_PROFILE"},
        }, request_id=20)
        result = _extract_text_json(result)
    except Exception:
        return []
    accounts: List[Dict[str, Any]] = []
    if not isinstance(result, dict):
        return accounts
    data = result.get("data") or {}
    for status in (data.get("toolkit_connection_statuses") or []):
        if not status.get("has_active_connection"):
            continue
        for acc in status.get("accounts", []):
            if acc.get("status", "").upper() == "ACTIVE":
                email = (acc.get("user_info") or {}).get("email", "")
                accounts.append({
                    "app": status.get("toolkit", "gmail"),
                    "status": acc.get("status", "ACTIVE"),
                    "id": acc.get("id"),
                    "email": email,
                    "alias": acc.get("alias"),
                    "display_name": email,
                })
    return accounts


async def composio_gmail_status() -> Dict[str, Any]:
    """Status of Composio Gmail integration."""
    if not composio_key():
        return {"provider": "composio", "connected": False, "reason": "COMPOSIO_API_KEY missing"}
    try:
        accounts = await composio_list_connected_accounts()
        gmail = [a for a in accounts if a.get("app", "").lower() == "gmail"]
        return {
            "provider": "composio",
            "connected": bool(gmail),
            "gmail_accounts": len(gmail),
            "total_accounts": len(accounts),
            "gmail_addresses": [a.get("email") or a.get("alias") for a in gmail if a.get("email") or a.get("alias")],
        }
    except Exception as exc:
        return {"provider": "composio", "connected": False, "reason": type(exc).__name__}


async def _first_active_gmail_account() -> Optional[Dict[str, Any]]:
    """Return the first ACTIVE Composio Gmail connection (for account selection)."""
    for account in await composio_list_connected_accounts():
        if account.get("app", "").lower() == "gmail" and account.get("status", "").upper() == "ACTIVE":
            return account
    return None


async def _composio_session_id() -> str:
    """Obtain a reusable session id from the Composio search meta-tool."""
    result = await _mcp_call("tools/call", {
        "name": "COMPOSIO_SEARCH_TOOLS",
        "arguments": {"query": "GMAIL_GET_PROFILE"},
    }, request_id=22)
    payload = _extract_text_json(result)
    session = (payload or {}).get("session") or {}
    return session.get("id") or "held"


async def composio_execute_tool(tool: str, arguments: Dict[str, Any], account_id: Optional[str] = None) -> Dict[str, Any]:
    """Execute a Composio tool via the MCP multi-execute endpoint using a connected account."""
    if not composio_key():
        raise RuntimeError("COMPOSIO_API_KEY is required for Composio mail")
    account = account_id or (await _first_active_gmail_account() or {}).get("id")
    if not account:
        return {"successful": False, "reason": "No active Gmail connection in Composio"}
    execution = {"tool_slug": tool, "arguments": arguments or {}, "account": account}
    try:
        session_id = await _composio_session_id()
        result = await _mcp_call("tools/call", {
            "name": "COMPOSIO_MULTI_EXECUTE_TOOL",
            "arguments": {"tools": [execution], "session_id": session_id},
        }, request_id=21)
        payload = _extract_text_json(result)
        results = (payload or {}).get("data", {}).get("results", [])
        if results and results[0].get("response", {}).get("successful"):
            return {"successful": True, "data": results[0]["response"].get("data")}
        error = results[0].get("error") if results else (payload or {}).get("error")
        return {"successful": False, "reason": error or "Execution failed"}
    except Exception as exc:
        return {"successful": False, "reason": f"{type(exc).__name__}: {exc}"}
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90)
        body = json.loads(stdout.decode())
    except Exception as exc:
        return {"successful": False, "reason": f"cli_error: {type(exc).__name__}"}
    return {
        "successful": bool(body.get("successful")),
        "response_data": body.get("data"),
        "error": body.get("error"),
    }


# ── IMAP fallback ────────────────────────────────────────────────────────────

async def imap_read_mail(limit: int = 10) -> List[Dict[str, Any]]:
    from gmail_mailbox import GmailMailbox
    try:
        messages = await asyncio.to_thread(GmailMailbox().search, phrase="", limit=limit)
    except RuntimeError as exc:
        raise RuntimeError(f"IMAP unavailable: {exc}") from exc
    return messages


# ── High-level tools (bound to MCP handlers) ────────────────────────────────

async def gmail_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Report Gmail integration status across Composio and IMAP."""
    composio = await composio_gmail_status()
    imap_configured = bool(os.getenv("GMAIL_ADDRESS") and (os.getenv("GMAIL_APP_PASSWORD") or os.getenv("GMAIL_OAUTH_ACCESS_TOKEN")))
    return {
        "composio": composio,
        "imap_configured": imap_configured,
        "provider": "composio" if composio.get("connected") else ("imap" if imap_configured else "not_connected"),
        "connected": bool(composio.get("connected") or imap_configured),
    }


async def gmail_send(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Send an email. Uses Composio Gmail if a Gmail account is connected; otherwise reports the blocker."""
    to = arguments.get("to", "")
    subject = arguments.get("subject", "")
    body = arguments.get("body", "")
    if not (to and subject and body):
        return {"accepted": False, "reason": "to, subject and body are all required"}

    # Prefer Composio when a Gmail account is connected.
    status = await composio_gmail_status()
    if status.get("connected"):
        return await composio_execute_tool("GMAIL_SEND_EMAIL", {
            "recipient_email": to, "subject": subject, "body": body,
        })

    # No live sender available without credentials.
    return {
        "accepted": False,
        "reason": "No connected Gmail account. Connect one through Composio, or set GMAIL_ADDRESS/GMAIL_APP_PASSWORD for read-only IMAP (sending still needs a provider).",
    }


async def gmail_read(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Read recent Gmail messages. Uses Composio if connected, else IMAP."""
    limit = int(arguments.get("limit", 10))
    limit = max(1, min(limit, 50))
    status = await composio_gmail_status()
    if status.get("connected"):
        # Composio read: fetch recent messages.
        return await composio_execute_tool("GMAIL_LIST_MESSAGES", {"user_id": "me", "max_results": limit})
    if os.getenv("GMAIL_ADDRESS"):
        return {"messages": await imap_read_mail(limit=limit)}
    return {"reason": "No Gmail credentials. Connect a Gmail account through Composio or set GMAIL_ADDRESS."}


def gmail_tools() -> List[Dict[str, Any]]:
    """Tool schemas registered into the MCP registry."""
    return [
        {
            "name": "gmail_status",
            "description": "Check whether Gmail integration is available (Composio connected account or IMAP credentials). Returns the active provider.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "gmail_send",
            "description": "Send an email through the connected Gmail integration. Uses Composio Gmail. Returns real delivery evidence or the exact blocker (never simulates sending).",
            "inputSchema": {"type": "object", "properties": {
                "to": {"type": "string", "minLength": 3},
                "subject": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            }, "required": ["to", "subject", "body"], "additionalProperties": False},
        },
        {
            "name": "gmail_read",
            "description": "Read recent Gmail inbox messages via Composio or IMAP. Returns message subjects, senders and dates.",
            "inputSchema": {"type": "object", "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            }, "additionalProperties": False},
        },
    ]

EMAIL_FEED_INTERVAL_SECONDS = 960  # 16 minutes


async def pull_email_feed(limit: int = 10) -> Dict[str, Any]:
    """Scheduled (not continuous) email pull.

    Fetches the most recent Gmail messages once and records a short, honest
    digest locally (data/email-feed.json) plus a Digital Me memory line. The
    caller (dashboard scheduler) invokes this every EMAIL_FEED_INTERVAL_SECONDS.
    """
    try:
        result = await gmail_read({"limit": limit})
    except Exception as exc:
        return {"status": "failed", "reason": type(exc).__name__}
    path = ROOT / "data" / "email-feed.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    messages = (result.get("response_data") or {}).get("messages") if isinstance(result, dict) else None
    count = len(messages) if isinstance(messages, list) else 0
    try:
        from digital_me import add_memory_entry
        add_memory_entry({"note": f"Scheduled email-feed pull completed: {count} recent messages fetched."})
    except Exception:
        pass
    return {"status": "ok", "count": count, "scheduled_every_s": EMAIL_FEED_INTERVAL_SECONDS}
