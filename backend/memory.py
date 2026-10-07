"""Customer memory: saved chat history, the customer profile, and page context.

- Chat history lives in chat_messages (one row per turn, logged-in users only).
- The customer profile comes from the users row behind the session cookie.
- Page context comes from the front end, but product ids are checked against
  the catalogue before the agent sees them.
"""

import json
import re
import sqlite3
from typing import List, Optional

from db import get_connection, get_products_by_ids
from models import (
    MAX_HISTORY_TURNS,
    ChatResponse,
    ChatTurn,
    CustomerProfile,
    PageContext,
    ProductCard,
    StoredChatMessage,
    ViewingContext,
)

HISTORY_PAGE_SIZE = 50
PRODUCT_PATH_RE = re.compile(r"^/products/([a-z0-9-]{1,120})/?$")
STATIC_PAGES = {"/": "home", "/products": "products", "/about": "about", "/login": "login", "/signup": "signup"}


def ensure_schema() -> None:
    """Add chat_messages.page_title if missing (nullable, so existing rows are untouched)."""
    conn = get_connection(readonly=False)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(chat_messages)")}
        if "page_title" not in columns:
            with conn:
                conn.execute("ALTER TABLE chat_messages ADD COLUMN page_title TEXT")
    finally:
        conn.close()


# ---------- Secrets ----------

# "my password is hunter2", "pw: abc123", "passcode = 9876" -> "my password is [redacted]"
SECRET_RE = re.compile(r"\b(password|passwd|passcode|pass code|pwd|pw|pin)(\s*(?:is|was|=|:)\s*|\s+)(\S+)", re.IGNORECASE)
SECRET_SKIP = {"is", "was", "reset", "for", "to", "and", "or", "the", "a", "my", "your", "please", "help", "change", "forgot", "?"}


def redact_secrets(text: str) -> str:
    """Mask anything that looks like a password so it is never sent to the model or stored."""
    def mask(m: "re.Match[str]") -> str:
        value = m.group(3).strip(".,!?\"'")
        if value.lower() in SECRET_SKIP or (not m.group(2).strip() and not any(c.isdigit() for c in value)):
            return m.group(0)  # "password reset", "forgot my password" -> leave alone
        return f"{m.group(1)}{m.group(2)}[redacted]"

    return SECRET_RE.sub(mask, text)


# ---------- Customer ----------

def customer_profile(user: sqlite3.Row) -> CustomerProfile:
    return CustomerProfile(
        first_name=user["first_name"],
        last_name=user["last_name"],
        name=user["name"],
        email=user["email"],
        member_since=user["created_at"][:10],
    )


# ---------- Page context ----------

def resolve_page(page: Optional[PageContext]) -> Optional[ViewingContext]:
    """Turn the client's page info into trusted context: only real product ids get through."""
    if page is None:
        return None
    path = page.path.split("?")[0].split("#")[0] or "/"
    # Free text from the browser goes into the agent's instructions: keep it plain and short.
    results_title = re.sub(r"[^\w\s$.,'&/-]", "", page.results_title).strip()[:60] if page.results_title else None

    match = PRODUCT_PATH_RE.match(path)
    if match:
        product = get_products_by_ids([match.group(1)])
        if product:
            p = product[0]
            return ViewingContext(
                path=path, page_type="product", product_id=p["product_id"],
                product_name=p["name"], garment_type=p["garment_type"],
            )
        return ViewingContext(path=path, page_type="other")

    page_type = STATIC_PAGES.get(path.rstrip("/") or "/", "other")
    return ViewingContext(
        path=path,
        page_type=page_type,
        results_title=results_title if page_type == "products" else None,
    )


# ---------- Chat history ----------

def _cards_from_json(products_json: Optional[str]) -> List[ProductCard]:
    """Saved rows store a snapshot; re-read the products so prices and stock are current."""
    if not products_json:
        return []
    try:
        ids = [p["product_id"] for p in json.loads(products_json) if isinstance(p, dict) and "product_id" in p]
    except (ValueError, TypeError):
        return []
    return [ProductCard(**p) for p in get_products_by_ids(list(dict.fromkeys(ids)))]


def load_history(user_id: int, limit: int = HISTORY_PAGE_SIZE) -> List[StoredChatMessage]:
    """The user's most recent messages, oldest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM (SELECT * FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?) ORDER BY id",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()
    return [
        StoredChatMessage(
            id=r["id"],
            role=r["role"],
            content=r["content"],
            products=_cards_from_json(r["products_json"]),
            page_title=r["page_title"] if "page_title" in r.keys() else None,
            created_at=r["created_at"],
        )
        for r in rows
        if r["role"] in ("user", "assistant")
    ]


def agent_history(user_id: int) -> List[ChatTurn]:
    """Recent turns for the model's message_history (text only)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT role, content FROM (SELECT * FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?) ORDER BY id",
            (user_id, MAX_HISTORY_TURNS),
        ).fetchall()
    finally:
        conn.close()
    return [ChatTurn(role=r["role"], content=r["content"]) for r in rows if r["role"] in ("user", "assistant")]


def save_turns(user_id: int, message: str, reply: ChatResponse) -> None:
    """Store both sides of one exchange."""
    products_json = json.dumps([p.model_dump() for p in reply.products]) if reply.products else None
    conn = get_connection(readonly=False)
    try:
        with conn:
            conn.execute(
                "INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)",
                (user_id, message),
            )
            conn.execute(
                "INSERT INTO chat_messages (user_id, role, content, products_json, page_title) VALUES (?, 'assistant', ?, ?, ?)",
                (user_id, reply.reply, products_json, reply.page_title),
            )
    finally:
        conn.close()
