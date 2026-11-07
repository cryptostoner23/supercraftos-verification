"""Read Gmail verification mail using an authorized IMAP app password or OAuth token."""
from __future__ import annotations

import asyncio
import imaplib
import json
import os
import re
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import urlparse

from runtime_env import ROOT, load_environment


class GmailMailbox:
    def __init__(self, connect=imaplib.IMAP4_SSL):
        self.connect = connect

    def search(self, phrase: str = "Firecrawl", limit: int = 20) -> list[dict]:
        load_environment()
        address = os.getenv("GMAIL_ADDRESS")
        app_password = os.getenv("GMAIL_APP_PASSWORD")
        access_token = os.getenv("GMAIL_OAUTH_ACCESS_TOKEN")
        if not address:
            raise RuntimeError("GMAIL_ADDRESS is missing")
        if not (app_password or access_token):
            raise RuntimeError("GMAIL_APP_PASSWORD or GMAIL_OAUTH_ACCESS_TOKEN is required for backend Gmail access")
        if not 1 <= limit <= 50 or not re.fullmatch(r"[\w .-]{1,80}", phrase):
            raise ValueError("Invalid search options")

        mailbox = self.connect("imap.gmail.com", 993, timeout=20)
        try:
            if access_token:
                auth = f"user={address}\x01auth=Bearer {access_token}\x01\x01".encode()
                mailbox.authenticate("XOAUTH2", lambda _: auth)
            else:
                mailbox.login(address, app_password)
            status, _ = mailbox.select("INBOX", readonly=True)
            if status != "OK":
                raise RuntimeError("Gmail inbox could not be opened")
            status, found = mailbox.search(None, "SUBJECT", f'"{phrase}"')
            if status != "OK":
                raise RuntimeError("Gmail search failed")
            results = []
            for uid in reversed(found[0].split()[-limit:]):
                status, fetched = mailbox.fetch(uid, "(BODY.PEEK[])")
                if status != "OK":
                    continue
                raw = next((item[1] for item in fetched if isinstance(item, tuple) and isinstance(item[1], bytes)), None)
                if raw is None:
                    continue
                message = BytesParser(policy=policy.default).parsebytes(raw)
                body = "\n".join(part.get_content() for part in message.walk()
                                 if part.get_content_type() in {"text/plain", "text/html"}
                                 and part.get_content_disposition() != "attachment")
                links = []
                for candidate in re.findall(r'https://[^\s<>"\']+', body):
                    link = candidate.rstrip(".,;)")
                    parsed = urlparse(link)
                    if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
                        links.append(link)
                results.append({"subject": str(message.get("subject", "")),
                                "from": str(message.get("from", "")),
                                "date": str(message.get("date", "")), "links": links})
            return results
        finally:
            try:
                mailbox.logout()
            except Exception:
                pass


async def pull_verification_mail(phrase: str = "Firecrawl") -> dict:
    try:
        messages = await asyncio.to_thread(GmailMailbox().search, phrase)
    except RuntimeError as exc:
        return {"status": "unavailable", "reason": str(exc)}
    target = ROOT / "data" / "autonomous" / "gmail-backend-messages.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(messages, indent=2) + "\n")
    target.chmod(0o600)
    return {"status": "retrieved", "count": len(messages), "private_file": str(target)}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(pull_verification_mail()), indent=2))
