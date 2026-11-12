#!/usr/bin/env python3
"""The server side of the signing: stored credentials, a signed session, and
renewal before the seven days are up.

Three things live here.

**The credential store.** The app specific password for an account is kept on
the server, encrypted, so the account is set up once and not asked for again.
More than one can be kept for an account, and they are tried in turn, so a
revoked one does not stop the others. The file is mode 600, the key is mode
600, and nothing here ever prints a credential.

**The session token.** A JSON Web Token, signed with HMAC, that proves to the
server that the browser that signed in is still the one that signed in. It
travels in an HttpOnly cookie, so the page cannot read it, and it is scoped
to one device and one account. It expires after a month and slides, so a
device that is used keeps its sign in.

**Renewal.** A free account's profile lasts seven days. The bundle is
re-signed on the sixth day, before it lapses, and the fresh one is published
under the same name, so the install link on the device never changes and the
app is replaced rather than removed. The old bundle stays available until the
new one is written.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

DEFAULT_CREDENTIALS = "/var/lib/supercraftos/ios-credentials.json"
DEFAULT_CREDENTIAL_KEY = "/var/lib/supercraftos/ios-credentials.key"
DEFAULT_TOKEN_KEY = "/var/lib/supercraftos/ios-token.key"


def _path(variable: str, default: str) -> Path:
    return Path(os.environ.get(variable) or default)


def credentials_file() -> Path:
    return _path("SUPERCRAFTOS_CREDENTIALS", DEFAULT_CREDENTIALS)


def credential_key() -> Path:
    return _path("SUPERCRAFTOS_CREDENTIAL_KEY", DEFAULT_CREDENTIAL_KEY)


def token_key() -> Path:
    return _path("SUPERCRAFTOS_TOKEN_KEY", DEFAULT_TOKEN_KEY)

TOKEN_TTL = 30 * 24 * 3600
RENEW_AFTER = 5 * 24 * 3600      # five days, so a renewal lands on the sixth
PROFILE_LIFETIME = 7 * 24 * 3600


# ------------------------------------------------------------- the key files

def _key(path: Path) -> bytes:
    """The server's secret, made once and kept with mode 600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(os.urandom(64))
        os.chmod(path, 0o600)
    return path.read_bytes()


def _fernet() -> Fernet:
    raw = _key(credential_key())
    digest = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _token_secret() -> bytes:
    return _key(token_key())


# ------------------------------------------------------- the credential store

def _load() -> dict:
    path = credentials_file()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _save(data: dict) -> None:
    path = credentials_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2))
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def remember_password(account: str, password: str) -> None:
    """Keep an app specific password for an account, most recent first."""
    if not account or not password:
        return
    data = _load()
    entries = [entry for entry in data.get(account, []) if entry.get("password") != password]
    entries.insert(0, {"password": _fernet().encrypt(password.encode()).decode(),
                        "stored": int(time.time())})
    data[account] = entries[:5]
    _save(data)


def passwords_for(account: str) -> list[str]:
    """Every stored password for an account, most recent first."""
    data = _load()
    out = []
    for entry in data.get(account, []):
        try:
            out.append(_fernet().decrypt(entry["password"].encode()).decode())
        except (InvalidToken, KeyError, ValueError):
            continue
    return out


def has_password(account: str) -> bool:
    return bool(passwords_for(account))


def forget(account: str) -> None:
    data = _load()
    data.pop(account, None)
    _save(data)


# ----------------------------------------------------------------- the token

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(account: str, udid: str, build: str = "app") -> str:
    """A signed token for one account, one device and one build."""
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {"sub": account, "device": udid, "build": build,
              "iat": int(time.time()), "exp": int(time.time()) + TOKEN_TTL}
    body = _b64(json.dumps(header, separators=(",", ":")).encode()) + "." + \
        _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = hmac.new(_token_secret(), body.encode(), hashlib.sha256).digest()
    return body + "." + _b64(signature)


def read_token(token: str) -> dict | None:
    """The claims of a token, if it is genuine and has not expired."""
    try:
        header, body, signature = token.split(".")
    except ValueError:
        return None
    expected = hmac.new(_token_secret(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(_unb64(signature), expected):
        return None
    try:
        claims = json.loads(_unb64(body))
    except Exception:
        return None
    if int(claims.get("exp", 0)) < time.time():
        return None
    return claims


# ------------------------------------------------------------- the renewal

def signed_at(bundle: Path) -> int:
    """When the bundle was signed, from the file itself."""
    try:
        return int(bundle.stat().st_mtime)
    except OSError:
        return 0


def needs_renewal(bundle: Path) -> bool:
    """True when the bundle is old enough to be re-signed."""
    if not bundle.exists():
        return True
    return time.time() - signed_at(bundle) > RENEW_AFTER


def expiry_of(bundle: Path) -> int:
    return signed_at(bundle) + PROFILE_LIFETIME
