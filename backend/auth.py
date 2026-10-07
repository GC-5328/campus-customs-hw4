"""Password hashing and session tokens for Campus Customs.

Passwords are stored as ``pbkdf2_sha256$<salt>$<hex digest>``, the same format
as the seeded users, so existing accounts keep working:

* PBKDF2-HMAC-SHA256, 120,000 iterations
* a fresh random salt per user (``secrets.token_hex``)
* only the salt and digest are stored, never the password

Sessions are an HMAC-signed token (user id + expiry) kept in an HttpOnly
cookie, so the browser never sees the password hash or anything secret.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 120_000
SALT_BYTES = 16

SESSION_COOKIE = "cc_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
SECRET_FILE = Path(__file__).resolve().parent / ".session_secret"


# ---------- Passwords ----------

def _pbkdf2(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERATIONS).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    return f"{ALGORITHM}${salt}${_pbkdf2(password, salt)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt, expected = stored_hash.split("$")
    except ValueError:
        return False
    if algorithm != ALGORITHM:
        return False
    return hmac.compare_digest(_pbkdf2(password, salt), expected)


# Used when the email doesn't exist so a failed login takes the same time
# either way (doesn't reveal which emails have accounts).
DUMMY_HASH = hash_password(secrets.token_hex(16))


# ---------- Session tokens ----------

def _load_secret() -> bytes:
    env_secret = os.getenv("CC_SESSION_SECRET")
    if env_secret:
        return env_secret.encode("utf-8")
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32))
        SECRET_FILE.chmod(0o600)
    return SECRET_FILE.read_text().strip().encode("utf-8")


_SECRET = _load_secret()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(_SECRET, payload.encode("ascii"), hashlib.sha256).digest())


def create_session_token(user_id: int) -> str:
    payload = _b64(json.dumps({"uid": user_id, "exp": int(time.time()) + SESSION_TTL_SECONDS}).encode("utf-8"))
    return f"{payload}.{_sign(payload)}"


def read_session_token(token: Optional[str]) -> Optional[int]:
    if not token or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    try:
        data = json.loads(_unb64(payload))
    except ValueError:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data.get("uid")
