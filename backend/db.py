"""SQLite helpers shared by the API routes (main.py) and agent tools (tools.py)."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
PRODUCTS_DIR = DATA_DIR / "products"
# White-background web copies made by clean_images.py; originals are served if they don't exist.
WEB_IMAGES_DIR = DATA_DIR / "products_web"
IMAGES_DIR = WEB_IMAGES_DIR if WEB_IMAGES_DIR.exists() else PRODUCTS_DIR
# Bump when the served images change so browsers don't keep showing cached old copies.
IMAGE_VERSION = "web2" if IMAGES_DIR == WEB_IMAGES_DIR else "orig"

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


def get_connection(readonly: bool = True) -> sqlite3.Connection:
    mode = "ro" if readonly else "rw"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_inventory(conn: sqlite3.Connection, product_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not product_ids:
        return {}
    placeholders = ",".join("?" for _ in product_ids)
    rows = conn.execute(
        f"SELECT product_id, size, quantity FROM inventory WHERE product_id IN ({placeholders})",
        product_ids,
    ).fetchall()
    inventory: Dict[str, List[Dict[str, Any]]] = {pid: [] for pid in product_ids}
    for row in rows:
        inventory[row["product_id"]].append({"size": row["size"], "quantity": row["quantity"]})
    for sizes in inventory.values():
        sizes.sort(key=lambda s: SIZE_ORDER.index(s["size"]) if s["size"] in SIZE_ORDER else len(SIZE_ORDER))
    return inventory


def serialize_product(row: sqlite3.Row, inventory: List[Dict[str, Any]]) -> Dict[str, Any]:
    image_file = Path(row["image_file_path"]).name
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "description": row["description"],
        "colors": json.loads(row["colors"]),
        "search_tags": json.loads(row["search_tags"]),
        "image_file_path": row["image_file_path"],
        "image_url": f"/media/products/{image_file}?v={IMAGE_VERSION}",
        "price": row["price"],
        "inventory": inventory,
        "total_stock": sum(s["quantity"] for s in inventory),
    }


def get_products_by_ids(product_ids: List[str]) -> List[Dict[str, Any]]:
    """Full product dicts for the given ids, in the given order; unknown ids are dropped."""
    if not product_ids:
        return []
    placeholders = ",".join("?" for _ in product_ids)
    with get_connection() as conn:
        rows = conn.execute(f"SELECT * FROM catalogue WHERE product_id IN ({placeholders})", product_ids).fetchall()
        inventory = load_inventory(conn, [r["product_id"] for r in rows])
    by_id = {r["product_id"]: serialize_product(r, inventory[r["product_id"]]) for r in rows}
    return [by_id[pid] for pid in product_ids if pid in by_id]
