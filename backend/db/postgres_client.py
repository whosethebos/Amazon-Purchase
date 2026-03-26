# backend/db/postgres_client.py
import json
from datetime import datetime, timezone
from psycopg.types.json import Json
from db.pool import get_pool


def _row(d: dict | None) -> dict | None:
    """Cast UUID id fields to str for JSON compatibility."""
    if d is None:
        return None
    return {k: str(v) if k.endswith("_id") or k == "id" else v for k, v in d.items()}


def _rows(rows: list[dict]) -> list[dict]:
    return [_row(r) for r in rows]


# --- Searches ---

async def create_search(query: str, max_results: int, requirements: list[str] | None = None) -> dict:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "INSERT INTO searches (query, max_results, requirements, status) "
            "VALUES (%s, %s, %s, 'pending') RETURNING *",
            (query, max_results, Json(requirements or []))
        )
        return _row(await cur.fetchone())


async def update_search_status(search_id: str, status: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE searches SET status = %s WHERE id = %s",
            (status, search_id)
        )


async def get_search(search_id: str) -> dict | None:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM searches WHERE id = %s",
            (search_id,)
        )
        return _row(await cur.fetchone())


async def list_searches() -> list[dict]:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM searches ORDER BY created_at DESC"
        )
        return _rows(await cur.fetchall())


async def delete_search(search_id: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute("DELETE FROM searches WHERE id = %s", (search_id,))


# --- Products ---

async def insert_products(products: list[dict]) -> list[dict]:
    async with get_pool().connection() as conn:
        rows = []
        for p in products:
            cur = await conn.execute(
                "INSERT INTO products "
                "(search_id, asin, title, price, currency, rating, review_count, url, image_url, confirmed) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (
                    p.get("search_id"), p["asin"], p.get("title"), p.get("price"),
                    p.get("currency", "USD"), p.get("rating"), p.get("review_count"),
                    p["url"], p.get("image_url"), p.get("confirmed", False)
                )
            )
            rows.append(_row(await cur.fetchone()))
        return rows


async def confirm_products(product_ids: list[str]) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE products SET confirmed = TRUE WHERE id = ANY(%s::uuid[])",
            (product_ids,)
        )


async def get_products_by_search(search_id: str) -> list[dict]:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM products WHERE search_id = %s",
            (search_id,)
        )
        return _rows(await cur.fetchall())


async def get_confirmed_products(search_id: str) -> list[dict]:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM products WHERE search_id = %s AND confirmed = TRUE",
            (search_id,)
        )
        return _rows(await cur.fetchall())


async def get_product(product_id: str) -> dict | None:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM products WHERE id = %s",
            (product_id,)
        )
        return _row(await cur.fetchone())


async def find_or_create_product_by_asin(product: dict) -> dict:
    """Find an existing product by ASIN or create a new standalone one (no search_id)."""
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM products WHERE asin = %s LIMIT 1",
            (product["asin"],)
        )
        existing = await cur.fetchone()
        if existing:
            return _row(existing)
        cur = await conn.execute(
            "INSERT INTO products "
            "(asin, title, price, currency, rating, review_count, url, image_url, confirmed) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE) RETURNING *",
            (
                product["asin"], product.get("title"), product.get("price"),
                product.get("currency", "USD"), product.get("rating"),
                product.get("review_count"), product["url"], product.get("image_url")
            )
        )
        return _row(await cur.fetchone())


# --- Reviews ---

async def insert_reviews(reviews: list[dict]) -> None:
    async with get_pool().connection() as conn:
        await conn.executemany(
            "INSERT INTO reviews "
            "(product_id, reviewer, rating, title, body, helpful_votes, verified_purchase) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    r["product_id"], r.get("reviewer"), r.get("rating"),
                    r.get("title"), r.get("body"),
                    r.get("helpful_votes", 0), r.get("verified_purchase", False)
                )
                for r in reviews
            ]
        )


async def get_reviews_by_product(product_id: str) -> list[dict]:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM reviews WHERE product_id = %s",
            (product_id,)
        )
        return _rows(await cur.fetchall())


# --- Analysis ---

async def insert_analysis(analysis: dict) -> dict:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "INSERT INTO analysis "
            "(product_id, summary, pros, cons, sentiment, score, rank) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (
                analysis["product_id"], analysis.get("summary"),
                Json(analysis.get("pros", [])), Json(analysis.get("cons", [])),
                analysis.get("sentiment"), analysis.get("score"), analysis.get("rank")
            )
        )
        return _row(await cur.fetchone())


async def get_analysis_by_product(product_id: str) -> dict | None:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM analysis WHERE product_id = %s",
            (product_id,)
        )
        return _row(await cur.fetchone())


async def update_analysis_rank(product_id: str, score: int | None, rank: int | None) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE analysis SET score = %s, rank = %s WHERE product_id = %s",
            (score, rank, product_id)
        )


# --- Watchlist ---

async def add_to_watchlist(product_id: str) -> dict:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "INSERT INTO watchlist (product_id) VALUES (%s) "
            "ON CONFLICT (product_id) DO UPDATE SET added_at = watchlist.added_at "
            "RETURNING *",
            (product_id,)
        )
        return _row(await cur.fetchone())


async def get_watchlist() -> list[dict]:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT w.id, w.product_id, w.added_at, w.last_checked_at, "
            "row_to_json(p)::text AS products_json "
            "FROM watchlist w "
            "LEFT JOIN products p ON p.id = w.product_id "
            "ORDER BY w.added_at DESC"
        )
        rows = await cur.fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["id"] = str(item["id"])
        item["product_id"] = str(item["product_id"])
        products_json = item.pop("products_json", None)
        item["products"] = json.loads(products_json) if products_json else {}
        if item["products"] and "id" in item["products"]:
            item["products"]["id"] = str(item["products"]["id"])
        result.append(item)
    return result


async def delete_watchlist_item(watchlist_id: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute("DELETE FROM watchlist WHERE id = %s", (watchlist_id,))


async def update_watchlist_checked(watchlist_id: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE watchlist SET last_checked_at = %s WHERE id = %s",
            (datetime.now(timezone.utc), watchlist_id)
        )


# --- Price history ---

async def insert_price_history(product_id: str, price: float, currency: str = "USD") -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO price_history (product_id, price, currency) VALUES (%s, %s, %s)",
            (product_id, price, currency)
        )


async def get_price_history(product_id: str) -> list[dict]:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM price_history WHERE product_id = %s "
            "ORDER BY checked_at DESC LIMIT 30",
            (product_id,)
        )
        return _rows(await cur.fetchall())
