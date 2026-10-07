"""Read-only catalogue and inventory tools the agent can call.

- search_products: find products by keywords / budget / size
- get_product_info: description, price, colors for one product
- check_stock: exact quantities for one product, optionally one size

Every price and quantity the agent states must come from these results
(agent.py rejects replies that quote numbers the tools didn't return).
"""

import json
import sqlite3
from typing import List, Optional, Tuple, Union

from db import SIZE_ORDER, get_connection, load_inventory
from models import (
    LOW_STOCK_THRESHOLD,
    ProductInfo,
    ProductNotFound,
    ProductSummary,
    SearchResults,
    SimilarItem,
    SizeStockStatus,
    StockCheck,
    StockStatus,
)

SEARCH_FIELDS = "lower(name || ' ' || garment_type || ' ' || description || ' ' || colors || ' ' || search_tags)"
MAX_SEARCH_RESULTS = 40
# Shopper words -> the wording the catalogue uses.
SYNONYMS = {"tee": "t-shirt", "tshirt": "t-shirt", "hoody": "hoodie", "sweater": "sweat", "1/4": "quarter"}
STOP_WORDS = {"a", "an", "the", "and", "or", "for", "with", "in", "of", "do", "you", "have", "any", "some", "me", "show"}

SIZE_ALIASES = {
    "XS": "XS", "XSMALL": "XS", "EXTRASMALL": "XS",
    "S": "S", "SM": "S", "SMALL": "S",
    "M": "M", "MED": "M", "MEDIUM": "M",
    "L": "L", "LG": "L", "LARGE": "L",
    "XL": "XL", "XLARGE": "XL", "EXTRALARGE": "XL",
    "XXL": "XXL", "2XL": "XXL", "XXLARGE": "XXL", "2XLARGE": "XXL", "EXTRAEXTRALARGE": "XXL",
}


# ---------- helpers ----------

def _keywords(query: str) -> List[str]:
    words = []
    for raw in query.lower().replace(",", " ").split():
        word = raw.strip("?!.'\"")
        if not word or word in STOP_WORDS:
            continue
        # "hoodies" -> "hoodie", "tees" -> "tee"; LIKE matching handles the rest.
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        words.append(SYNONYMS.get(word, word))
    return words


def normalize_size(size: str) -> Optional[str]:
    key = "".join(ch for ch in size.upper() if ch.isalnum())
    return SIZE_ALIASES.get(key)


def stock_status(quantity: int) -> StockStatus:
    if quantity <= 0:
        return "sold_out"
    return "low_stock" if quantity <= LOW_STOCK_THRESHOLD else "in_stock"


def _summary(row: sqlite3.Row, sizes: List[dict]) -> ProductSummary:
    return ProductSummary(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        price=row["price"],
        colors=json.loads(row["colors"]),
        sizes_in_stock=[s["size"] for s in sizes if s["quantity"] > 0],
    )


def _resolve(conn: sqlite3.Connection, product: str) -> Tuple[Optional[sqlite3.Row], List[sqlite3.Row]]:
    """Find one product by id or name. Returns (match, candidates if ambiguous / not found)."""
    ref = product.strip()
    row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (ref.lower(),)).fetchone()
    if row:
        return row, []
    row = conn.execute("SELECT * FROM catalogue WHERE lower(name) = ?", (ref.lower(),)).fetchone()
    if row:
        return row, []
    words = _keywords(ref.replace("-", " "))
    if not words:
        return None, []
    clauses = " AND ".join(f"{SEARCH_FIELDS} LIKE ?" for _ in words)
    rows = conn.execute(f"SELECT * FROM catalogue WHERE {clauses} ORDER BY name LIMIT 6", [f"%{w}%" for w in words]).fetchall()
    if len(rows) == 1:
        return rows[0], []
    return None, rows


def _not_found(conn: sqlite3.Connection, product: str, candidates: List[sqlite3.Row]) -> ProductNotFound:
    inventory = load_inventory(conn, [r["product_id"] for r in candidates])
    if candidates:
        error = f"'{product}' matches several products. Pick one product_id from suggestions or ask the shopper."
    else:
        error = f"No product matches '{product}'. Use search_products to find it; don't guess."
    return ProductNotFound(
        error=error,
        query=product,
        suggestions=[_summary(r, inventory[r["product_id"]]) for r in candidates],
    )


# Garment "families" so a sold-out hoodie suggests other hoodies, not tees.
FAMILIES = [
    ("quarter-zip", ("quarter-zip", "1/4 zip", "quarter zip")),
    ("jacket", ("jacket", "fleece")),
    ("hoodie", ("hood",)),
    ("crewneck", ("crew", "mockneck", "sweatshirt")),
    ("long-sleeve", ("long-sleeve", "long sleeve")),
    ("t-shirt", ("t-shirt", "tee")),
]
MAX_SIMILAR = 3


def garment_family(garment_type: str) -> str:
    text = garment_type.lower()
    for family, needles in FAMILIES:
        if any(n in text for n in needles):
            return family
    return text


def size_position(size: str) -> Optional[float]:
    """Where a size sits on the XS..XXL scale; sizes we don't make land just past the ends."""
    wanted = normalize_size(size)
    if wanted:
        return SIZE_ORDER.index(wanted)
    key = "".join(ch for ch in size.upper() if ch.isalnum())
    if key.endswith("L") and (key.count("X") >= 3 or key[:1] in "3456"):
        return len(SIZE_ORDER)  # 3XL, XXXL... -> nearest is XXL
    if key.endswith("S") and (key.count("X") >= 2 or key[:1] in "2345"):
        return -1  # XXS, 2XS... -> nearest is XS
    return None


def closest_sizes(requested: str, sizes: List[dict]) -> List[SizeStockStatus]:
    """Up to 2 in-stock sizes nearest the requested one; ties go to the bigger size."""
    target = size_position(requested)
    in_stock = [s for s in sizes if s["quantity"] > 0 and s["size"] in SIZE_ORDER and s["size"] != normalize_size(requested)]
    if target is None:
        ranked = in_stock  # unknown size: just list what's available, smallest first
    else:
        ranked = sorted(in_stock, key=lambda s: (abs(SIZE_ORDER.index(s["size"]) - target), -SIZE_ORDER.index(s["size"])))
    return [SizeStockStatus(size=s["size"], quantity=s["quantity"], status=stock_status(s["quantity"])) for s in ranked[:2]]


def similar_in_size(conn: sqlite3.Connection, product: sqlite3.Row, size: Optional[str]) -> List[SimilarItem]:
    """Same-family products with `size` in stock (any size if None), most alike first."""
    family = garment_family(product["garment_type"])
    colors = set(json.loads(product["colors"]))
    tags = {t.lower() for t in json.loads(product["search_tags"])}
    rows = conn.execute("SELECT * FROM catalogue WHERE product_id != ?", (product["product_id"],)).fetchall()
    candidates = [r for r in rows if garment_family(r["garment_type"]) == family]
    inventory = load_inventory(conn, [r["product_id"] for r in candidates])

    scored = []
    for r in candidates:
        by_size = {s["size"]: s["quantity"] for s in inventory[r["product_id"]]}
        qty = by_size.get(size, 0) if size else sum(by_size.values())
        if qty <= 0:
            continue
        shared = len(colors & set(json.loads(r["colors"]))) * 2 + len(tags & {t.lower() for t in json.loads(r["search_tags"])})
        scored.append((-shared, abs(r["price"] - product["price"]), r["name"], r, qty))
    scored.sort(key=lambda x: x[:3])
    return [
        SimilarItem(
            product_id=r["product_id"], name=r["name"], garment_type=r["garment_type"],
            price=r["price"], colors=json.loads(r["colors"]), quantity=qty,
        )
        for *_, r, qty in scored[:MAX_SIMILAR]
    ]


def _fallback_text(closest: List[SizeStockStatus], similar: List[SimilarItem], size_label: str) -> str:
    parts = []
    if closest:
        parts.append("Closest sizes in stock: " + ", ".join(f"{c.size} ({c.quantity} left)" for c in closest) + ".")
    if similar:
        parts.append(f"Similar items with {size_label} in stock: " + ", ".join(f"{s.name} (${s.price:g}, {s.quantity} left)" for s in similar) + ".")
    if not parts:
        return "No close alternatives in stock right now."
    return " ".join(parts) + " Offer ONE of these so the shopper has a next step."


# ---------- tools ----------

def search_products(
    query: str = "",
    max_price: Optional[float] = None,
    size: Optional[str] = None,
    limit: int = 8,
) -> SearchResults:
    """Search the Campus Customs catalogue. Use this to find product_ids.

    Args:
        query: Keywords such as "navy hoodie", "bulldog crewneck", "Harvard Yale", "pink". Every
            keyword must match the product's name, type, description, colors, or tags. Leave empty
            to browse everything.
        max_price: Only return products at or below this price in USD.
        size: Only return products with this size in stock (XS, S, M, L, XL, XXL, or words like "medium").
        limit: Maximum number of results (1-40). Use 40 when the shopper is browsing a whole
            category ("what hoodies do you have?") so every match can go on the page.
    """
    sql = "SELECT * FROM catalogue"
    clauses, params = [], []
    for word in _keywords(query):
        clauses.append(f"{SEARCH_FIELDS} LIKE ?")
        params.append(f"%{word}%")
    if max_price is not None:
        clauses.append("price <= ?")
        params.append(max_price)
    if size:
        clauses.append("product_id IN (SELECT product_id FROM inventory WHERE size = ? AND quantity > 0)")
        params.append(normalize_size(size) or size.strip().upper())
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY price, name LIMIT ?"
    params.append(max(1, min(limit, MAX_SEARCH_RESULTS)))

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        inventory = load_inventory(conn, [r["product_id"] for r in rows])
    matches = [_summary(r, inventory[r["product_id"]]) for r in rows]

    filters = ", ".join(f for f in (f"under ${max_price:g}" if max_price is not None else "", f"size {size}" if size else "") if f)
    described = f"'{query}'" + (f" ({filters})" if filters else "")
    if matches:
        note = f"{len(matches)} product(s) match {described}."
    elif (size or max_price is not None) and query.strip():
        # The filters emptied the results. Say which products exist so the model doesn't
        # claim "we don't carry it" when it's really "sold out in that size".
        unfiltered = search_products(query, limit=5).matches
        if unfiltered:
            ids = ", ".join(m.product_id for m in unfiltered)
            reason = f"in size {size}" if size else f"under ${max_price:g}"
            note = (
                f"We DO carry products matching '{query}' ({ids}), but none are available {reason}. "
                "Don't say we don't carry it. Use check_stock / get_product_info on those ids and tell the shopper "
                "what's sold out or over budget, then offer what is available."
            )
        else:
            note = f"Nothing in the catalogue matches '{query}', even without filters. Don't repeat this search."
    else:
        note = (
            f"Nothing in the catalogue matches {described}. This is a final answer: don't repeat this search "
            "or small variations of it. Tell the shopper we don't carry it, and at most try ONE broader search "
            "(fewer keywords) to suggest an alternative."
        )
    return SearchResults(query=query, count=len(matches), matches=matches, note=note)


def get_product_info(product: str) -> Union[ProductInfo, ProductNotFound]:
    """Look up one product's description, exact price, colors, and which sizes are in stock.

    Call this for "how much is…", "tell me about…", "what color…" questions.

    Args:
        product: The product_id from search_products (preferred), or the product's name.
    """
    with get_connection() as conn:
        row, candidates = _resolve(conn, product)
        if row is None:
            return _not_found(conn, product, candidates)
        sizes = load_inventory(conn, [row["product_id"]])[row["product_id"]]
    return ProductInfo(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        description=row["description"],
        price=row["price"],
        colors=json.loads(row["colors"]),
        sizes_in_stock=[s["size"] for s in sizes if s["quantity"] > 0],
        sold_out_sizes=[s["size"] for s in sizes if s["quantity"] <= 0],
        total_in_stock=sum(s["quantity"] for s in sizes),
    )


def check_stock(product: str, size: Optional[str] = None) -> Union[StockCheck, ProductNotFound]:
    """Check live inventory for one product: exact quantity per size, and the requested size if given.

    Call this for any "is it in stock", "do you have it in M", "how many are left" question.
    If the shopper names a size, pass it so that exact size is checked.

    Args:
        product: The product_id from search_products (preferred), or the product's name.
        size: Optional size to check: XS, S, M, L, XL, XXL (words like "medium" or "2XL" are fine).
    """
    with get_connection() as conn:
        row, candidates = _resolve(conn, product)
        if row is None:
            return _not_found(conn, product, candidates)
        sizes = load_inventory(conn, [row["product_id"]])[row["product_id"]]

    by_size = {s["size"]: s["quantity"] for s in sizes}
    result = StockCheck(
        product_id=row["product_id"],
        name=row["name"],
        price=row["price"],
        stock_by_size=[SizeStockStatus(size=s["size"], quantity=s["quantity"], status=stock_status(s["quantity"])) for s in sizes],
        sizes_in_stock=[s["size"] for s in sizes if s["quantity"] > 0],
        sold_out_sizes=[s["size"] for s in sizes if s["quantity"] <= 0],
        total_in_stock=sum(by_size.values()),
        note="",
    )

    if size:
        wanted = normalize_size(size)
        result.requested_size = wanted or size.strip()
        if wanted is None or wanted not in by_size:
            # Not a size we make: suggest the nearest real sizes (no "similar items": the size doesn't exist anywhere).
            result.requested_size_offered = False
            offered = ", ".join(s for s in SIZE_ORDER if s in by_size)
            result.closest_sizes_in_stock = closest_sizes(size, sizes)
            result.note = f"{row['name']} doesn't come in size '{size}'. Sizes offered: {offered}. " + _fallback_text(
                result.closest_sizes_in_stock, [], size
            )
        else:
            qty = by_size[wanted]
            result.requested_size_offered = True
            result.requested_quantity = qty
            result.requested_status = stock_status(qty)
            if qty <= 0:
                # Out-of-stock fallback: nearest size of this item + similar items that have this size.
                result.closest_sizes_in_stock = closest_sizes(wanted, sizes)
                with get_connection() as conn:
                    result.similar_in_stock = similar_in_size(conn, row, wanted)
                result.note = f"Size {wanted} is SOLD OUT. " + _fallback_text(
                    result.closest_sizes_in_stock, result.similar_in_stock, wanted
                )
            elif qty <= LOW_STOCK_THRESHOLD:
                result.note = f"Size {wanted}: only {qty} left (low stock)."
            else:
                result.note = f"Size {wanted}: {qty} in stock."
    elif result.total_in_stock == 0:
        with get_connection() as conn:
            result.similar_in_stock = similar_in_size(conn, row, None)
        result.note = "Sold out in every size. " + _fallback_text([], result.similar_in_stock, "any size")
    else:
        result.note = f"{result.total_in_stock} in stock across sizes {', '.join(result.sizes_in_stock)}."
    return result
