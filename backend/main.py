"""Campus Customs API.

FastAPI app that serves the product catalogue, per-size inventory, and
product images from data/campus_customs.db, handles account sign-up / log-in
against the users table, and answers chat messages with the PydanticAI agent
in agent.py.

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000
"""

import logging
import re
import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import Cookie, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded

import auth
import memory
from agent import ChatDeps, is_content_filter, run_chat
from db import IMAGES_DIR, get_connection, get_products_by_ids, load_inventory, serialize_product
from models import ChatHistoryResponse, ChatRequest, ChatResponse, ChatTurn, ProductCard

logger = logging.getLogger("campus_customs")

app = FastAPI(title="Campus Customs API")
memory.ensure_schema()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default 422 body echoes the submitted values back, which would
    # include passwords. Return only the field names and messages.
    errors = [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})

# Images are served at /media/products/<file>.jpg, matching the image_url
# already stored in chat_messages.products_json.
app.mount("/media/products", StaticFiles(directory=IMAGES_DIR), name="product-images")


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/products")
def list_products(
    q: Optional[str] = Query(None, description="Case-insensitive search across name, type, description, colors, tags"),
) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM catalogue"
    params: List[str] = []
    if q:
        like = f"%{q.lower()}%"
        sql += (
            " WHERE lower(name) LIKE ? OR lower(garment_type) LIKE ? OR lower(description) LIKE ?"
            " OR lower(colors) LIKE ? OR lower(search_tags) LIKE ?"
        )
        params = [like] * 5
    sql += " ORDER BY name"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        inventory = load_inventory(conn, [r["product_id"] for r in rows])
    return [serialize_product(r, inventory.get(r["product_id"], [])) for r in rows]


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> Dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        inventory = load_inventory(conn, [product_id])
    return serialize_product(row, inventory[product_id])


# ---------- Accounts ----------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def public_user(row: sqlite3.Row) -> Dict[str, Any]:
    """The only user fields ever sent to the browser (no password hash)."""
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "name": row["name"],
        "email": row["email"],
    }


def set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.create_session_token(user_id),
        max_age=auth.SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )


@app.post("/api/auth/signup", status_code=201)
def signup(body: SignupRequest, response: Response) -> Dict[str, Any]:
    first_name = body.first_name.strip()
    last_name = body.last_name.strip()
    email = body.email.strip().lower()

    if not first_name or not last_name:
        raise HTTPException(status_code=400, detail="First and last name are required.")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords don't match.")

    password_hash = auth.hash_password(body.password)
    conn = get_connection(readonly=False)
    try:
        if conn.execute("SELECT 1 FROM users WHERE lower(email) = ?", (email,)).fetchone():
            raise sqlite3.IntegrityError("duplicate email")
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
                (f"{first_name} {last_name}", email, password_hash, first_name, last_name),
            )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    finally:
        conn.close()

    set_session_cookie(response, row["id"])
    return public_user(row)


@app.post("/api/auth/login")
def login(body: LoginRequest, response: Response) -> Dict[str, Any]:
    email = body.email.strip().lower()
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
    finally:
        conn.close()

    stored_hash = row["password_hash"] if row else auth.DUMMY_HASH
    if not auth.verify_password(body.password, stored_hash) or row is None:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    set_session_cookie(response, row["id"])
    return public_user(row)


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(auth.SESSION_COOKIE)
    response.status_code = 204
    return response


def current_user(cc_session: Optional[str]) -> Optional[sqlite3.Row]:
    user_id = auth.read_session_token(cc_session)
    if user_id is None:
        return None
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()


@app.get("/api/auth/me")
def me(cc_session: Optional[str] = Cookie(None)) -> Dict[str, Any]:
    row = current_user(cc_session)
    if row is None:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return public_user(row)


# ---------- Chat ----------

LOOP_REPLY = "Sorry, I couldn't pin that down. Could you say it another way, or tell me the item or size you're after?"
BLOCKED_REPLY = "Sorry, I can't help with that one. I'm here for Campus Customs gear. Looking for a hoodie, tee, or crewneck?"


@app.get("/api/chat/history")
def chat_history(cc_session: Optional[str] = Cookie(None)) -> ChatHistoryResponse:
    """The logged-in shopper's saved chat (most recent 50 messages). Guests get 401."""
    user = current_user(cc_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Log in to see your chat history.")
    return ChatHistoryResponse(messages=memory.load_history(user["id"]))


@app.post("/api/chat")
async def chat(body: ChatRequest, cc_session: Optional[str] = Cookie(None)) -> ChatResponse:
    user = current_user(cc_session)
    deps = ChatDeps(
        customer=memory.customer_profile(user) if user else None,
        page=memory.resolve_page(body.page),
    )
    # Logged in: memory comes from the database (can't be edited by the browser).
    # Guest: use the history the browser kept for this visit.
    history = memory.agent_history(user["id"]) if user else [
        ChatTurn(role=t.role, content=memory.redact_secrets(t.content)) for t in body.history
    ]
    # Passwords typed into chat are masked before the model sees them or anything is saved.
    message = memory.redact_secrets(body.message)
    try:
        output = await run_chat(message, history, deps, audit_user=f"user:{user['id']}" if user else "guest")
    except UsageLimitExceeded:
        logger.warning("Chat agent hit its per-message request/tool limit")
        return ChatResponse(reply=LOOP_REPLY)
    except ModelHTTPError as exc:
        if is_content_filter(exc):
            # The provider's safety filter blocked the message (e.g. a jailbreak attempt).
            logger.warning("Chat message blocked by provider content filter")
            return ChatResponse(reply=BLOCKED_REPLY)
        logger.error("Chat agent failed: ModelHTTPError %s", exc.status_code)
        raise HTTPException(status_code=502, detail="The shop assistant is having trouble right now. Please try again.")
    except Exception as exc:  # model/gateway errors: log the type only, never the message text
        logger.error("Chat agent failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="The shop assistant is having trouble right now. Please try again.")

    # Cards are built from the database, so names, prices, and stock can't be hallucinated.
    cards = [ProductCard(**p) for p in get_products_by_ids(list(dict.fromkeys(output.product_ids)))]
    page_title = output.page_title.strip() if output.page_title and cards else None
    response = ChatResponse(reply=output.message, products=cards, page_title=page_title)
    if user is not None:
        memory.save_turns(user["id"], message, response)
    return response
