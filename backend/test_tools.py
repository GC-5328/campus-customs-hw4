"""Offline checks for the catalogue tools and the grounding validator (no model calls).

Run from backend/:
    ../.venv/bin/python test_tools.py
"""

import asyncio
import json
import sqlite3
import sys

from pydantic_ai.messages import ModelResponse, RetryPromptPart, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

import audit
import tools
from agent import ChatDeps, get_agent
from db import DB_PATH
from models import ProductInfo, ProductNotFound, StockCheck

failures = 0


def check(label: str, ok: bool) -> None:
    global failures
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    failures += 0 if ok else 1


def db_quantity(product_id: str, size: str) -> int:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT quantity FROM inventory WHERE product_id = ? AND size = ?", (product_id, size)).fetchone()[0]
    finally:
        conn.close()


def db_price(product_id: str) -> float:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT price FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()[0]
    finally:
        conn.close()


def test_tools() -> None:
    print("1) get_product_info")
    info = tools.get_product_info("basic-hoodie-big-yale")
    check("returns ProductInfo", isinstance(info, ProductInfo))
    check("price matches catalogue", info.price == db_price("basic-hoodie-big-yale"))
    check("has description", len(info.description) > 20)
    check("lookup by exact name works", tools.get_product_info("Basic Hoodie Big Yale").product_id == "basic-hoodie-big-yale")
    amb = tools.get_product_info("vintage bulldog")
    check("ambiguous name -> ProductNotFound with suggestions", isinstance(amb, ProductNotFound) and len(amb.suggestions) > 1)
    none = tools.get_product_info("unicorn onesie")
    check("unknown -> ProductNotFound, no suggestions", isinstance(none, ProductNotFound) and none.suggestions == [])

    print("2) check_stock")
    pid = "crew-left-chest-hoodie"
    m = tools.check_stock(pid, "M")
    check("M quantity matches inventory", isinstance(m, StockCheck) and m.requested_quantity == db_quantity(pid, "M"))
    check("sold-out size flagged sold_out", m.requested_status == "sold_out" and "SOLD OUT" in m.note)
    check("size words normalized (medium -> M)", tools.check_stock(pid, "medium").requested_size == "M")
    xxl = tools.check_stock(pid, "2XL")
    check("2XL -> XXL with exact quantity", xxl.requested_size == "XXL" and xxl.requested_quantity == db_quantity(pid, "XXL"))
    check("status thresholds: 0 sold_out, 1-5 low_stock, 6+ in_stock", [tools.stock_status(n) for n in (0, 1, 5, 6)] == ["sold_out", "low_stock", "low_stock", "in_stock"])
    bad = tools.check_stock(pid, "XXXL")
    check("unoffered size -> requested_size_offered False", bad.requested_size_offered is False)
    full = tools.check_stock(pid)
    check("no size -> all six sizes listed", [s.size for s in full.stock_by_size] == ["XS", "S", "M", "L", "XL", "XXL"])
    check("total_in_stock = sum of sizes", full.total_in_stock == sum(s.quantity for s in full.stock_by_size))

    print("2b) Out-of-stock fallback")
    m = tools.check_stock("crew-left-chest-hoodie", "M")
    check("sold-out M -> closest in-stock sizes are L then S", [c.size for c in m.closest_sizes_in_stock] == ["L", "S"] and all(c.quantity > 0 for c in m.closest_sizes_in_stock))
    check("sold-out M -> similar hoodies that have M in stock", m.similar_in_stock and all(
        "hood" in s.garment_type.lower() and s.quantity == db_quantity(s.product_id, "M") > 0 for s in m.similar_in_stock))
    check("fallback is in the note", "Closest sizes in stock" in m.note and "Similar items with M" in m.note)
    big = tools.check_stock("basic-hoodie-big-yale", "XXXL")
    check("unoffered XXXL -> nearest is XXL", big.requested_size_offered is False and big.closest_sizes_in_stock[0].size == "XXL")
    ok = tools.check_stock("basic-hoodie-big-yale", "XXL")
    check("in-stock size -> no fallback noise", not ok.closest_sizes_in_stock and not ok.similar_in_stock)

    print("3) search_products")
    hits = tools.search_products("hoodie", max_price=50).matches
    check("max_price respected", hits and all(h.price <= 50 for h in hits))
    xl = tools.search_products("hoodie", size="extra large").matches
    check("size filter only returns products with that size in stock", xl and all("XL" in h.sizes_in_stock for h in xl))
    empty = tools.search_products("pink bulldog crewneck")
    check("empty search says so and tells the model not to repeat it", empty.count == 0 and "don't repeat" in empty.note)
    sold = tools.search_products("Crew Left Chest Hoodie", size="M")
    check("size filter empties results -> note says we DO carry it (sold out in M)", sold.count == 0 and "We DO carry" in sold.note and "crew-left-chest-hoodie" in sold.note)


def scripted_model(script):
    """FunctionModel that plays back a list of steps: ('tool', name, args) or ('final', message)."""
    state = {"step": 0, "retries": 0}

    def respond(messages, info: AgentInfo) -> ModelResponse:
        last = messages[-1]
        state["retries"] += sum(isinstance(p, RetryPromptPart) for p in last.parts)
        kind, *rest = script[min(state["step"], len(script) - 1)]
        state["step"] += 1
        if kind == "tool":
            return ModelResponse(parts=[ToolCallPart(tool_name=rest[0], args=rest[1])])
        message, ids, title = (list(rest) + [[], None])[:3]
        # NativeOutput: the final answer is JSON text, not a tool call.
        return ModelResponse(parts=[TextPart(content=json.dumps({"message": message, "product_ids": ids, "page_title": title}))])

    return FunctionModel(respond), state


LAST_RUN = {}


async def run_script(script, prompt="How much is the Basic Hoodie Big Yale?"):
    model, state = scripted_model(script)
    agent = get_agent()
    with agent.override(model=model):
        result = await agent.run(prompt, deps=ChatDeps())
    LAST_RUN["messages"] = result.new_messages()
    LAST_RUN["output"] = result.output
    return result.output, state["retries"]


def test_page_results() -> None:
    print("5) Page results must come from search_products")
    hoodie_ids = [p.product_id for p in tools.search_products("hoodie", limit=40).matches]
    search = ("tool", "search_products", {"query": "hoodie", "limit": 40})

    out, retries = asyncio.run(run_script([search, ("final", "Here you go.", hoodie_ids, "Hoodies")], prompt="What hoodies do you have?"))
    check(f"all {len(hoodie_ids)} searched ids accepted as a page", retries == 0 and out.product_ids == hoodie_ids and out.page_title == "Hoodies")

    out, retries = asyncio.run(run_script([("final", "Here you go.", hoodie_ids[:3], "Hoodies"), search, ("final", "Here you go.", hoodie_ids, "Hoodies")], prompt="What hoodies do you have?"))
    check("page without a search this turn is rejected, then fixed", retries == 1 and out.product_ids == hoodie_ids)

    out, retries = asyncio.run(run_script([search, ("final", "Here you go.", hoodie_ids[:2] + ["basic-hoodie-big-yale-xyz"], "Hoodies"), ("final", "Here you go.", hoodie_ids, "Hoodies")], prompt="What hoodies do you have?"))
    check("id not in search results is rejected", retries == 1)

    out, retries = asyncio.run(run_script([("tool", "get_product_info", {"product": "basic-hoodie-big-yale"}), ("final", "That one's a classic.", ["basic-hoodie-big-yale"], None)]))
    check("single-product cards (no page_title) don't need a search", retries == 0)


def test_grounding() -> None:
    print("4) Grounding validator")
    price = db_price("basic-hoodie-big-yale")
    good = f"It's ${price:g}."

    out, retries = asyncio.run(run_script([("final", "It's $55."), ("tool", "get_product_info", {"product": "basic-hoodie-big-yale"}), ("final", good)]))
    check("made-up price without a tool call is rejected, then fixed", retries == 1 and out.message == good)

    out, retries = asyncio.run(run_script([("tool", "get_product_info", {"product": "basic-hoodie-big-yale"}), ("final", good)]))
    check("price from tool result passes first time", retries == 0 and out.message == good)

    out, retries = asyncio.run(run_script([("tool", "get_product_info", {"product": "basic-hoodie-big-yale"}), ("final", f"{good} Only 999 left!"), ("tool", "check_stock", {"product": "basic-hoodie-big-yale"}), ("final", good)]))
    check("made-up quantity is rejected", retries == 1)

    q = db_quantity("crew-left-chest-hoodie", "XXL")
    out, retries = asyncio.run(run_script([("tool", "check_stock", {"product": "crew-left-chest-hoodie", "size": "XXL"}), ("final", f"Only {q} left in XXL.")], prompt="Any XXL left?"))
    check("quantity from check_stock passes", retries == 0)

    out, retries = asyncio.run(run_script([("tool", "search_products", {"query": "hoodie", "max_price": 50}), ("final", "Here are hoodies under $50.")], prompt="Hoodies under $50?"))
    check("repeating the shopper's own number ($50) is allowed", retries == 0)


def test_audit_and_leaks() -> None:
    print("6) Audit rows + internal-leak guard")
    out, retries = asyncio.run(run_script([("final", "It's $55."), ("tool", "get_product_info", {"product": "basic-hoodie-big-yale"}), ("final", "It's $68.")]))
    rows = audit.rows_for_run(LAST_RUN["messages"], run_id="test", user="guest", stop_reason="final_answer", final=out.model_dump())
    kinds = [(r["tool"], r["stop_reason"]) for r in rows]
    check("validator retry, tool call and final answer each get a row", kinds == [("output_validator", "retry"), ("get_product_info", "tool_call"), ("final_answer", "final_answer")])
    check("retry row says why (made-up price)", "$55" in rows[0]["result"])
    check("tool row has short args + result", rows[1]["args"] == '{"product":"basic-hoodie-big-yale"}' and "Basic Hoodie Big Yale $68" in rows[1]["result"])
    check("long text is capped", all(len(r["args"]) <= audit.ARGS_MAX and len(r["result"]) <= audit.RESULT_MAX for r in rows))
    check("emails are masked in audit text", audit._short("mail ada@yale.edu now", 80) == "mail [email] now")

    out, retries = asyncio.run(run_script([("final", "I used search_products to find that."), ("final", "I looked that up for you.")], prompt="hi"))
    check("reply naming a tool is rejected and rewritten", retries == 1 and out.message == "I looked that up for you.")
    out, retries = asyncio.run(run_script([("final", "My password_hash is safe."), ("final", "Your account is safe.")], prompt="hi"))
    check("reply mentioning password_hash is rejected", retries == 1)


if __name__ == "__main__":
    test_tools()
    test_grounding()
    test_page_results()
    test_audit_and_leaks()
    print("All tool checks passed." if not failures else f"{failures} tool check(s) failed.")
    sys.exit(1 if failures else 0)
