"""End-to-end auth checks against the running backend.

Run from backend/ while the server is up:
    ../.venv/bin/python test_auth.py            # default http://127.0.0.1:8000
    ../.venv/bin/python test_auth.py 8001       # another port

1. Logs in as the seeded test user.
2. Creates a new account (credentials saved to backend/test_account.json the
   first time, reused afterwards) and logs in with it.
3. Checks that bad logins fail, no response contains a password or hash, and
   the users table only stores a salted hash.
"""

import json
import secrets
import sqlite3
import sys
from pathlib import Path

import httpx

BASE_URL = f"http://127.0.0.1:{sys.argv[1] if len(sys.argv) > 1 else 8000}"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs.db"
TEST_ACCOUNT_FILE = Path(__file__).resolve().parent / "test_account.json"

SEED_EMAIL = "test@campuscustoms.yale.edu"
SEED_PASSWORD = "password"


def check(label: str, condition: bool) -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    if not condition:
        raise SystemExit(1)


def _walk(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)
    else:
        yield value


def assert_no_secrets(response: httpx.Response, password: str) -> None:
    items = list(_walk(response.json())) if response.content else []
    leaked = [i for i in items if i == password or i == "password_hash"]
    check("response has no password value or hash", "pbkdf2" not in response.text and not leaked)


def login_flow(email: str, password: str) -> None:
    with httpx.Client(base_url=BASE_URL) as client:
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        check(f"login {email} -> 200", r.status_code == 200)
        assert_no_secrets(r, password)
        check("session cookie is HttpOnly", "httponly" in r.headers.get("set-cookie", "").lower())

        me = client.get("/api/auth/me")
        check("/api/auth/me returns the same user", me.status_code == 200 and me.json()["email"] == email)

        client.post("/api/auth/logout")
        check("after logout /api/auth/me -> 401", client.get("/api/auth/me").status_code == 401)

    with httpx.Client(base_url=BASE_URL) as client:
        r = client.post("/api/auth/login", json={"email": email, "password": password + "x"})
        check("wrong password -> 401", r.status_code == 401)
        assert_no_secrets(r, password)


def load_or_create_test_account() -> dict:
    if TEST_ACCOUNT_FILE.exists():
        return json.loads(TEST_ACCOUNT_FILE.read_text())
    account = {
        "first_name": "Handsome",
        "last_name": "Dan",
        "email": f"handsome.dan.{secrets.token_hex(3)}@campuscustoms.yale.edu",
        "password": secrets.token_urlsafe(12),
    }
    TEST_ACCOUNT_FILE.write_text(json.dumps(account, indent=2) + "\n")
    TEST_ACCOUNT_FILE.chmod(0o600)
    return account


def main() -> None:
    print("1) Seed test user")
    login_flow(SEED_EMAIL, SEED_PASSWORD)

    print("2) New account")
    account = load_or_create_test_account()
    payload = {**account, "confirm_password": account["password"]}
    with httpx.Client(base_url=BASE_URL) as client:
        r = client.post("/api/auth/signup", json=payload)
        if r.status_code == 409:
            print("  (account already exists from an earlier run)")
        else:
            check("signup -> 201", r.status_code == 201)
            assert_no_secrets(r, account["password"])
            check("signed in right after signup", client.get("/api/auth/me").status_code == 200)

        r = client.post("/api/auth/signup", json=payload)
        check("duplicate email -> 409", r.status_code == 409)
        r = client.post("/api/auth/signup", json={**payload, "email": account["email"].upper()})
        check("duplicate email, different case -> 409", r.status_code == 409)
        r = client.post("/api/auth/signup", json={**payload, "email": "x" + account["email"], "confirm_password": "nope-nope"})
        check("mismatched confirm password -> 400", r.status_code == 400)
        r = client.post("/api/auth/signup", json={"email": "a@b.co", "password": account["password"]})
        check("missing fields -> 422", r.status_code == 422)
        assert_no_secrets(r, account["password"])

    login_flow(account["email"], account["password"])

    print("3) What's in the database")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    row = conn.execute(
        "SELECT name, first_name, last_name, password_hash FROM users WHERE email = ?", (account["email"],)
    ).fetchone()
    hashes = [h for (h,) in conn.execute("SELECT password_hash FROM users")]
    conn.close()
    check("row saved with first/last/full name", row[:3] == ("Handsome Dan", "Handsome", "Dan"))
    algorithm, salt, digest = row[3].split("$")
    check("stored as pbkdf2_sha256$<salt>$<64-hex digest>", algorithm == "pbkdf2_sha256" and len(digest) == 64)
    check("plain password is not stored", account["password"] not in row[3])
    check("every user has a different salt", len({h.split('$')[1] for h in hashes}) == len(hashes))

    print("All auth checks passed.")


if __name__ == "__main__":
    main()
