"""Append-only audit trail of agent loops: output/audit_trail.json.

One row per step of every agent run:
  - each tool call      -> tool name, short args, short result, stop_reason "tool_call"
  - each validator retry -> tool "output_validator", the reason, stop_reason "retry"
  - the end of the run   -> tool "final_answer" (or "-" on failure) with the run's stop reason:
                            final_answer | usage_limit | content_filter | model_error |
                            output_retries_exhausted | error

The file is a JSON array that only ever grows: rows are appended under a lock and
written atomically (temp file + rename). It's never truncated between runs. If the
file can't be parsed, it's moved aside to audit_trail.corrupt-<time>.json, not overwritten.

Privacy: no user message text, no emails, no passwords. Customer profile
results are summarised as "profile returned", and emails in replies are masked.
"""

import fcntl
import json
import logging
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, RetryPromptPart, ToolCallPart, ToolReturnPart
from pydantic_core import to_jsonable_python

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
LOCK_PATH = Path(__file__).resolve().parent / ".audit.lock"  # kept out of output/
ARGS_MAX = 120
RESULT_MAX = 160

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
logger = logging.getLogger("campus_customs.audit")
_thread_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _short(text: str, limit: int) -> str:
    text = EMAIL_RE.sub("[email]", " ".join(str(text).split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _short_args(args: Any) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return _short(args, ARGS_MAX)
    return _short(json.dumps(args, separators=(",", ":"), ensure_ascii=False), ARGS_MAX)


def _short_result(tool: str, content: Any) -> str:
    data = to_jsonable_python(content)
    if isinstance(data, dict) and "error" in data:
        return _short(f"not found: {data['error']}", RESULT_MAX)
    if tool == "search_products" and isinstance(data, dict):
        ids = ", ".join(m["product_id"] for m in data.get("matches", [])[:3])
        more = "…" if data.get("count", 0) > 3 else ""
        return _short(f"{data.get('count', 0)} matches: {ids}{more}", RESULT_MAX)
    if tool == "get_product_info" and isinstance(data, dict):
        return _short(f"{data.get('name')} ${data.get('price')}, in stock: {','.join(data.get('sizes_in_stock', []))}", RESULT_MAX)
    if tool == "check_stock" and isinstance(data, dict):
        return _short(data.get("note", ""), RESULT_MAX)
    if tool == "get_customer_profile":
        return "profile returned" if isinstance(data, dict) else "guest (no profile)"
    return _short(json.dumps(data, ensure_ascii=False), RESULT_MAX)


def rows_for_run(
    messages: Sequence[ModelMessage],
    *,
    run_id: str,
    user: str,
    stop_reason: str,
    final: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Turn one run's new messages into audit rows."""
    rows: List[Dict[str, Any]] = []
    calls: Dict[str, ToolCallPart] = {}

    def add(tool: str, args: str, result: str, reason: str, when: Optional[datetime] = None) -> None:
        rows.append({
            "time": (when.astimezone(timezone.utc).isoformat(timespec="seconds") if when else _now()),
            "run_id": run_id,
            "step": len(rows) + 1,
            "user": user,
            "tool": tool,
            "args": args,
            "result": result,
            "stop_reason": reason,
        })

    for message in messages:
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    calls[part.tool_call_id] = part
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, ToolReturnPart) and part.tool_call_id in calls:
                    call = calls[part.tool_call_id]
                    add(call.tool_name, _short_args(call.args), _short_result(call.tool_name, part.content), "tool_call", part.timestamp)
                elif isinstance(part, RetryPromptPart):
                    reason = part.content if isinstance(part.content, str) else json.dumps(to_jsonable_python(part.content))
                    add(part.tool_name or "output_validator", "", _short(reason, RESULT_MAX), "retry", part.timestamp)

    if final is not None:
        add("final_answer", "", _short(
            f"{len(final.get('product_ids', []))} cards"
            + (f", page '{final['page_title']}'" if final.get("page_title") else "")
            + f" | {final.get('message', '')}", RESULT_MAX), stop_reason)
    else:
        add("-", "", _short(error or "", RESULT_MAX), stop_reason)
    return rows


def append(rows: List[Dict[str, Any]]) -> None:
    """Append rows to the audit file. Never raises: auditing must not break the chat."""
    if not rows:
        return
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _thread_lock, open(LOCK_PATH, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)  # also safe across uvicorn worker processes
            existing: List[Dict[str, Any]] = []
            if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size:
                try:
                    existing = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
                    if not isinstance(existing, list):
                        raise ValueError("audit file is not a JSON array")
                except ValueError:
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    AUDIT_PATH.rename(AUDIT_PATH.with_name(f"audit_trail.corrupt-{stamp}.json"))
                    logger.error("Audit file was unreadable; moved aside, starting a new one")
                    existing = []
            tmp = AUDIT_PATH.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(existing + rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, AUDIT_PATH)
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not write audit trail: %s", type(exc).__name__)


def new_run_id() -> str:
    return uuid.uuid4().hex[:8]
