# Supabase → Local PostgreSQL Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Supabase client library with direct local PostgreSQL connections using psycopg3 async, updating all code, config, tests, and documentation.

**Architecture:** A single `AsyncConnectionPool` (psycopg3) is created at FastAPI startup via a `lifespan` handler and stored in `backend/db/pool.py`. All DB functions in `backend/db/postgres_client.py` (renamed from `supabase_client.py`) are rewritten as `async def` using raw SQL with `%s` placeholders. The `dict_row` row factory is set at pool level so all results are plain dicts — same shape as Supabase returned.

**Tech Stack:** Python 3.13, psycopg[binary]>=3.1, psycopg-pool>=3.2, FastAPI lifespan, PostgreSQL (local)

---

## File Map

| File | Action |
|------|--------|
| `backend/requirements.txt` | Modify — swap `supabase` for psycopg packages |
| `backend/config.py` | Modify — replace Supabase vars with `database_url` |
| `backend/.env` | Modify — replace Supabase vars with `DATABASE_URL` |
| `backend/.env.example` | Modify — same as `.env` |
| `backend/db/pool.py` | Create — `AsyncConnectionPool` singleton |
| `backend/db/postgres_client.py` | Create — async raw SQL rewrites of all DB functions |
| `backend/db/supabase_client.py` | Delete — replaced by `postgres_client.py` |
| `backend/db/schema.sql` | Modify — add `requirements` column; update header comment |
| `backend/main.py` | Modify — add `lifespan`; update imports |
| `backend/agents/orchestrator.py` | Modify — add `await` to all DB calls; replace Phase 4 raw `get_client()` call |
| `backend/tests/test_requirements.py` | Modify — update import paths, patch targets, make DB tests async |
| `backend/tests/test_analyze_url.py` | Modify — update any patch targets referencing `supabase_client` |
| `README.md` | Modify — database section, tech stack, prerequisites, setup, config table |
| `docs/plans/2026-03-10-amazon-research-tool-design.md` | Modify — replace Supabase references |
| `docs/plans/2026-03-10-amazon-research-tool-implementation.md` | Modify — replace Supabase references in tech stack/code snippets |
| `docs/skills/amazon-scraper.md` | Modify — update file reference and schema comment |
| `docs/superpowers/plans/2026-03-22-requirements-field.md` | Modify — update file refs and SQL instructions |
| `docs/superpowers/plans/2026-03-14-url-analysis.md` | Modify — update Supabase mention |
| `docs/superpowers/specs/2026-03-22-requirements-field-design.md` | Modify — update file ref and SQL instructions |
| `docs/superpowers/specs/2026-03-13-url-analysis-design.md` | Modify — update Supabase mention |

---

## Task 1: Update Dependencies and Config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`
- Modify: `backend/.env`
- Modify: `backend/.env.example`

- [ ] **Step 1: Update requirements.txt**

In `backend/requirements.txt`, replace:
```
supabase>=2.7.0
```
with:
```
psycopg[binary]>=3.1
psycopg-pool>=3.2
```

Full file after change:
```txt
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
playwright>=1.50.0
httpx>=0.27.0
psycopg[binary]>=3.1
psycopg-pool>=3.2
pydantic>=2.9.0
pydantic-settings>=2.4.0
python-dotenv>=1.0.1
pytest>=8.0
pytest-asyncio>=0.24
```

- [ ] **Step 2: Install updated dependencies**

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: psycopg and psycopg-pool install successfully; no errors.

- [ ] **Step 3: Update config.py**

Replace `backend/config.py` with:
```python
# backend/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama
    ollama_model: str = "qwen3:14b"
    ollama_base_url: str = "http://localhost:11434"

    # Database
    database_url: str = "postgresql://localhost/amazon_purchase"

    # Scraping
    amazon_domain: str = "amazon.in"
    amazon_batch_size: int = 5
    max_confirmation_iterations: int = 3
    max_reviews_per_product: int = 20

    # App
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 4: Update .env.example**

Replace `backend/.env.example` with:
```
DATABASE_URL=postgresql://user:password@localhost:5432/amazon_purchase
OLLAMA_MODEL=qwen3:14b
OLLAMA_BASE_URL=http://localhost:11434
AMAZON_BATCH_SIZE=5
MAX_CONFIRMATION_ITERATIONS=3
MAX_REVIEWS_PER_PRODUCT=20
FRONTEND_URL=http://localhost:3000
```

- [ ] **Step 5: Update .env**

In `backend/.env`, replace:
```
SUPABASE_URL=https://ruuwmozhegkngomzsklu.supabase.co
SUPABASE_KEY=sb_publishable_9MdcJPB-dHHIV6lD_42nHA_mNiqQw-X
```
with your local Postgres connection string:
```
DATABASE_URL=postgresql://localhost/amazon_purchase
```
(Adjust user/password/port if your local Postgres requires credentials.)

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/config.py backend/.env.example
git commit -m "chore: swap supabase dependency for psycopg3, update config"
```

Note: Do NOT stage `backend/.env` — it contains local credentials and is gitignored.

---

## Task 2: Update Database Schema

**Files:**
- Modify: `backend/db/schema.sql`

- [ ] **Step 1: Update schema.sql**

Replace `backend/db/schema.sql` with:
```sql
-- backend/db/schema.sql
-- Run this against your local PostgreSQL database to create the schema:
--   psql amazon_purchase < backend/db/schema.sql

CREATE TABLE searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    max_results INT DEFAULT 10,
    requirements JSONB DEFAULT '[]',
    status TEXT DEFAULT 'pending',  -- pending | scraping | confirming | analyzing | ranking | done | failed
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id UUID REFERENCES searches(id) ON DELETE CASCADE,
    asin TEXT NOT NULL,
    title TEXT,
    price DECIMAL,
    currency TEXT DEFAULT 'USD',
    rating DECIMAL,
    review_count INT,
    url TEXT NOT NULL,
    image_url TEXT,
    confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    reviewer TEXT,
    rating INT,
    title TEXT,
    body TEXT,
    helpful_votes INT DEFAULT 0,
    verified_purchase BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    summary TEXT,
    pros JSONB DEFAULT '[]',
    cons JSONB DEFAULT '[]',
    sentiment TEXT,
    score INT,   -- 0-100
    rank INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ,
    UNIQUE(product_id)
);

CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL,
    currency TEXT DEFAULT 'USD',
    checked_at TIMESTAMPTZ DEFAULT NOW()
);
```

- [ ] **Step 2: Create the local database and apply schema**

```bash
createdb amazon_purchase
psql amazon_purchase < backend/db/schema.sql
```

Expected: All 6 tables created without errors.

- [ ] **Step 3: Commit**

```bash
git add backend/db/schema.sql
git commit -m "chore: add requirements column to searches schema, update header comment"
```

---

## Task 3: Create Connection Pool Module

**Files:**
- Create: `backend/db/pool.py`

- [ ] **Step 1: Create pool.py**

Create `backend/db/pool.py`:
```python
# backend/db/pool.py
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from config import settings

_pool: AsyncConnectionPool | None = None


async def open_pool() -> None:
    global _pool
    # open=False defers pool opening until we explicitly call await _pool.open()
    # This avoids opening a connection at import time, which fails in an async context.
    _pool = AsyncConnectionPool(
        settings.database_url,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await _pool.open()


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call open_pool() first.")
    return _pool
```

- [ ] **Step 2: Verify import works**

```bash
cd backend
python -c "from db.pool import open_pool, close_pool, get_pool; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/db/pool.py
git commit -m "feat: add async psycopg3 connection pool module"
```

---

## Task 4: Write postgres_client.py

**Files:**
- Create: `backend/db/postgres_client.py`

This is the core of the migration. All functions are rewritten as `async def` using raw SQL. Key points:
- `async with get_pool().connection() as conn:` — acquires a connection; auto-commits on clean exit, auto-rolls back on exception
- `await conn.execute(sql, params)` returns a cursor; call `await cur.fetchone()` or `await cur.fetchall()` separately
- JSONB columns (`pros`, `cons`, `requirements`) **must** use `Json(value)` from `psycopg.types.json`
- UUID values come back as Python `uuid.UUID` objects — cast with `str()` where string IDs are needed
- Bulk inserts use a loop of `execute()` calls within one connection (each call is its own statement but shares the transaction)

- [ ] **Step 1: Create postgres_client.py**

Create `backend/db/postgres_client.py`:
```python
# backend/db/postgres_client.py
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
    import json
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
```

- [ ] **Step 2: Verify import works**

```bash
cd backend
python -c "import db.postgres_client; print('OK')"
```

Expected: `OK` (no import errors — the pool isn't needed just to import the module)

- [ ] **Step 3: Commit**

```bash
git add backend/db/postgres_client.py
git commit -m "feat: implement async psycopg3 postgres_client with raw SQL"
```

---

## Task 5: Update main.py

**Files:**
- Modify: `backend/main.py`

Changes needed:
1. Add `lifespan` context manager for pool open/close
2. Replace `import db.supabase_client as db` → `import db.postgres_client as db`
3. Replace `from db.supabase_client import find_or_create_product_by_asin` → `from db.postgres_client import find_or_create_product_by_asin`
4. Pass `lifespan=lifespan` to `FastAPI()`
5. Add `await` to all DB calls (they are now async)

- [ ] **Step 1: Update main.py**

At the top of `backend/main.py`, make these changes:

**Imports — replace:**
```python
import db.supabase_client as db
from db.supabase_client import find_or_create_product_by_asin
```
**with:**
```python
import db.postgres_client as db
from db.postgres_client import find_or_create_product_by_asin
from contextlib import asynccontextmanager
from db.pool import open_pool, close_pool
```

**Add lifespan before `app = FastAPI(...)` — add:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pool()
    yield
    await close_pool()
```

**Update FastAPI constructor:**
```python
app = FastAPI(title="Amazon Research Tool", lifespan=lifespan)
```

**Add `await` to every DB call in all route handlers.** These are all the locations to update:

In `start_search`:
```python
search = await db.create_search(request.query, request.max_results, request.requirements)
```

In `get_results`:
```python
search = await db.get_search(search_id)
products = await db.get_confirmed_products(search_id)
analysis = await db.get_analysis_by_product(product["id"])
```

In `list_searches`:
```python
searches = await db.list_searches()
products = await db.get_confirmed_products(str(s["id"]))
```

In `delete_search`:
```python
await db.delete_search(search_id)
```

In `get_watchlist`:
```python
items = await db.get_watchlist()
price_history = await db.get_price_history(str(product["id"])) if product else []
```

In `add_to_watchlist`:
```python
item = await db.add_to_watchlist(str(product_id))
```

In `add_to_watchlist_from_url`:
```python
product_record = await find_or_create_product_by_asin({...})
item = await db.add_to_watchlist(str(product_record["id"]))
```

In `remove_from_watchlist`:
```python
await db.delete_watchlist_item(watchlist_id)
```

In `refresh_watchlist_item`:
```python
items = await db.get_watchlist()
db.insert_price_history(...)  →  await db.insert_price_history(...)
db.update_watchlist_checked(...)  →  await db.update_watchlist_checked(...)
```

- [ ] **Step 2: Commit**

```bash
git add backend/main.py
git commit -m "feat: update main.py to use postgres_client with lifespan pool"
```

---

## Task 6: Update orchestrator.py

**Files:**
- Modify: `backend/agents/orchestrator.py`

Changes needed:
1. Replace `import db.supabase_client as db` → `import db.postgres_client as db`
2. Add `await` to every DB call
3. Replace the raw `get_client()` block in Phase 4 with `await db.update_analysis_rank(...)`

- [ ] **Step 1: Update the import line**

In `backend/agents/orchestrator.py`, replace:
```python
import db.supabase_client as db
```
with:
```python
import db.postgres_client as db
```

- [ ] **Step 2: Add await to all DB calls**

Find every `db.` call in `orchestrator.py` and add `await`:

```python
# Line ~50
await db.update_search_status(self.search_id, "scraping")

# Line ~62
await db.update_search_status(self.search_id, "failed")

# Line ~66
saved = await db.insert_products([...])

# Line ~72
await db.update_search_status(self.search_id, "confirming")

# Line ~89
await db.update_search_status(self.search_id, "failed")

# Line ~97
await db.confirm_products(self._confirmed_product_ids)

# Line ~105
await db.update_search_status(self.search_id, "analyzing")

# Line ~108
confirmed_products = await db.get_confirmed_products(self.search_id)

# Line ~113
await db.insert_reviews([{**r, "product_id": product["id"]} for r in reviews])

# Line ~121
reviews = await db.get_reviews_by_product(product["id"])

# Line ~124
await db.insert_analysis({**analysis, "product_id": product["id"]})

# Line ~144
await db.update_search_status(self.search_id, "done")
```

- [ ] **Step 3: Replace Phase 4 raw Supabase block**

Find this block in Phase 4 (around line 134–142):
```python
client = db.get_client()
for item in ranked:
    existing = db.get_analysis_by_product(item["id"])
    if existing:
        client.table("analysis").update({
            "score": item.get("score"),
            "rank": item.get("rank"),
        }).eq("product_id", item["id"]).execute()
```

Replace with:
```python
for item in ranked:
    await db.update_analysis_rank(item["id"], item.get("score"), item.get("rank"))
```

(The `if existing:` guard is safe to drop — `insert_analysis` always runs for every confirmed product in Phase 3 before Phase 4 executes.)

- [ ] **Step 4: Commit**

```bash
git add backend/agents/orchestrator.py
git commit -m "feat: update orchestrator to use postgres_client with await"
```

---

## Task 7: Update Tests

**Files:**
- Modify: `backend/tests/test_requirements.py`

The two DB-mocking tests (`test_create_search_passes_requirements_to_db` and `test_create_search_requirements_defaults_to_empty`) need to be rewritten:
- `create_search` is now `async def` → tests need `@pytest.mark.asyncio`
- Patch target is `db.postgres_client.get_pool` instead of `db.supabase_client.get_client`
- The mock must simulate the psycopg3 async connection context manager

The API integration test patches `main.db.create_search` — this patch target string needs no change (it still goes through `main.db`), but `fake_create_search` must become `async def`.

- [ ] **Step 1: Update test_requirements.py**

Replace `backend/tests/test_requirements.py` with:
```python
# backend/tests/test_requirements.py
"""Tests for requirements field plumbing: models, db client, and API endpoint."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from models import SearchRequest
from db.postgres_client import create_search


def test_search_request_accepts_requirements():
    req = SearchRequest(query="desk", requirements=["60 inch", "under $300"])
    assert req.requirements == ["60 inch", "under $300"]


def test_search_request_requirements_defaults_to_empty():
    req = SearchRequest(query="desk")
    assert req.requirements == []


def _make_mock_pool(fetchone_return: dict):
    """Build a mock pool that simulates async with pool.connection() as conn."""
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=fetchone_return)

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.connection = MagicMock(return_value=mock_cm)
    return mock_pool, mock_conn


@pytest.mark.asyncio
async def test_create_search_passes_requirements_to_db():
    expected_row = {"id": "abc123", "query": "desk", "max_results": 10, "requirements": ["60 inch"]}
    mock_pool, mock_conn = _make_mock_pool(expected_row)

    with patch("db.postgres_client.get_pool", return_value=mock_pool):
        result = await create_search("desk", 10, ["60 inch"])

    sql, params = mock_conn.execute.call_args[0]
    assert "INSERT INTO searches" in sql
    assert result["id"] == "abc123"


@pytest.mark.asyncio
async def test_create_search_requirements_defaults_to_empty():
    expected_row = {"id": "abc123", "query": "desk", "max_results": 10, "requirements": []}
    mock_pool, mock_conn = _make_mock_pool(expected_row)

    with patch("db.postgres_client.get_pool", return_value=mock_pool):
        result = await create_search("desk", 10)

    sql, params = mock_conn.execute.call_args[0]
    assert "INSERT INTO searches" in sql
    assert result["requirements"] == []


from agents.orchestrator import OrchestratorAgent


def test_orchestrator_stores_requirements():
    orch = OrchestratorAgent("sid1", "desk", ["60 inch", "solid wood"])
    assert orch.requirements == ["60 inch", "solid wood"]


def test_orchestrator_requirements_defaults_to_empty():
    orch = OrchestratorAgent("sid1", "desk")
    assert orch.requirements == []


def test_orchestrator_requirements_none_becomes_empty():
    orch = OrchestratorAgent("sid1", "desk", None)
    assert orch.requirements == []


from agents.analyst_agent import ReviewAnalystAgent


@pytest.mark.asyncio
async def test_analyst_uses_requirements_in_prompt():
    agent = ReviewAnalystAgent()
    reviews = [{"rating": 5, "title": "Great", "body": "Love it"}]
    captured_prompt = {}

    async def fake_chat_json(messages):
        captured_prompt["content"] = messages[0]["content"]
        return {"summary": "ok", "pros": [], "cons": [], "sentiment": "positive"}

    with patch("agents.analyst_agent.chat_json", new=fake_chat_json):
        await agent.analyze("Standing Desk", reviews, ["60 inch width", "solid wood"])

    assert "60 inch width" in captured_prompt["content"]
    assert "solid wood" in captured_prompt["content"]


@pytest.mark.asyncio
async def test_analyst_no_requirements_uses_base_prompt():
    agent = ReviewAnalystAgent()
    reviews = [{"rating": 5, "title": "Great", "body": "Love it"}]
    captured_prompt = {}

    async def fake_chat_json(messages):
        captured_prompt["content"] = messages[0]["content"]
        return {"summary": "ok", "pros": [], "cons": [], "sentiment": "positive"}

    with patch("agents.analyst_agent.chat_json", new=fake_chat_json):
        await agent.analyze("Standing Desk", reviews)

    assert "user requirements" not in captured_prompt["content"]


from agents.ranker_agent import RankerAgent


@pytest.mark.asyncio
async def test_ranker_appends_requirements_to_prompt():
    agent = RankerAgent()
    products = [{"asin": "B001", "title": "Desk", "price": 200, "rating": 4.5, "review_count": 100}]
    analyses = {"B001": {"summary": "Good desk", "pros": ["sturdy"], "cons": []}}
    captured_prompt = {}

    async def fake_chat_json(messages):
        captured_prompt["content"] = messages[0]["content"]
        return {"rankings": [{"asin": "B001", "score": 80, "rank": 1}]}

    with patch("agents.ranker_agent.chat_json", new=fake_chat_json):
        await agent.rank(products, analyses, ["60 inch width"])

    assert "60 inch width" in captured_prompt["content"]
    assert "user requirements" in captured_prompt["content"]


@pytest.mark.asyncio
async def test_ranker_no_requirements_uses_base_prompt():
    agent = RankerAgent()
    products = [{"asin": "B001", "title": "Desk", "price": 200, "rating": 4.5, "review_count": 100}]
    analyses = {"B001": {"summary": "Good desk", "pros": ["sturdy"], "cons": []}}
    captured_prompt = {}

    async def fake_chat_json(messages):
        captured_prompt["content"] = messages[0]["content"]
        return {"rankings": [{"asin": "B001", "score": 80, "rank": 1}]}

    with patch("agents.ranker_agent.chat_json", new=fake_chat_json):
        await agent.rank(products, analyses)

    assert "user requirements" not in captured_prompt["content"]


from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_search_endpoint_passes_requirements_to_orchestrator():
    """Verify that POST /api/search forwards requirements to OrchestratorAgent."""
    created_with = {}

    async def fake_create_search(query, max_results, requirements=None):
        created_with["requirements"] = requirements
        return {"id": "11111111-1111-1111-1111-111111111111", "query": query}

    captured_orchestrator = {}

    class FakeOrchestrator:
        def __init__(self, search_id, query, requirements=None):
            captured_orchestrator["requirements"] = requirements

        async def run(self):
            return
            yield  # make it a generator

    with (
        patch("main.db.create_search", side_effect=fake_create_search),
        patch("main.OrchestratorAgent", FakeOrchestrator),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/search",
                json={"query": "desk", "requirements": ["60 inch", "solid wood"]},
            )

    assert resp.status_code == 200
    assert created_with["requirements"] == ["60 inch", "solid wood"]
    assert captured_orchestrator["requirements"] == ["60 inch", "solid wood"]
```

- [ ] **Step 2: Run tests**

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: All tests pass. The two rewritten DB tests now mock psycopg3's connection pool instead of the Supabase client.

If the API integration test (`test_search_endpoint_passes_requirements_to_orchestrator`) fails with a startup error, check that the pool is not actually connecting during test — `main.db.create_search` is patched before the request, so the pool is opened but no real query runs. If you see a pool connection error, add a pool mock fixture or set `DATABASE_URL` to a test value.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_requirements.py
git commit -m "test: update requirements tests for psycopg3 async mock pattern"
```

---

## Task 8: Delete supabase_client.py

**Files:**
- Delete: `backend/db/supabase_client.py`

- [ ] **Step 1: Verify no remaining imports**

```bash
grep -r "supabase_client" backend/ --include="*.py"
```

Expected: No output. If any files still import `supabase_client`, fix them before deleting.

- [ ] **Step 2: Delete the file**

```bash
git rm backend/db/supabase_client.py
```

- [ ] **Step 3: Run tests to confirm nothing broke**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: delete supabase_client.py (replaced by postgres_client.py)"
```

---

## Task 9: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update tech stack table**

Find this row in the Tech Stack table:
```
| Database | Supabase (PostgreSQL) |
```
Replace with:
```
| Database | PostgreSQL (local, via psycopg3) |
```

- [ ] **Step 2: Update prerequisites section**

Find:
```
- **Supabase** project (free tier works)
```
Replace with:
```
- **PostgreSQL** running locally (`createdb amazon_purchase`)
```

- [ ] **Step 3: Update setup instructions**

Find:
```
cp .env.example .env
# Edit .env — set SUPABASE_URL, SUPABASE_KEY, OLLAMA_MODEL
```
Replace with:
```
cp .env.example .env
# Edit .env — set DATABASE_URL for your local Postgres, and OLLAMA_MODEL

# Create the database and apply schema
createdb amazon_purchase
psql amazon_purchase < db/schema.sql
```

- [ ] **Step 4: Update architecture diagram**

In the `db/` section of the Architecture tree, replace:
```
└── supabase_client.py # Supabase persistence (searches, products, watchlist, price history)
```
with:
```
├── pool.py            # AsyncConnectionPool singleton (opened at startup)
└── postgres_client.py # PostgreSQL persistence (searches, products, watchlist, price history)
```

- [ ] **Step 5: Update config table**

Find these two rows:
```
| `SUPABASE_URL` | — | Your Supabase project URL |
| `SUPABASE_KEY` | — | Your Supabase anon/service key |
```
Replace with:
```
| `DATABASE_URL` | `postgresql://localhost/amazon_purchase` | Local PostgreSQL connection string |
```

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: update README for local PostgreSQL (remove Supabase)"
```

---

## Task 10: Update Docs Files

**Files:**
- Modify: `docs/plans/2026-03-10-amazon-research-tool-design.md`
- Modify: `docs/plans/2026-03-10-amazon-research-tool-implementation.md`
- Modify: `docs/skills/amazon-scraper.md`
- Modify: `docs/superpowers/plans/2026-03-22-requirements-field.md`
- Modify: `docs/superpowers/plans/2026-03-14-url-analysis.md`
- Modify: `docs/superpowers/specs/2026-03-22-requirements-field-design.md`
- Modify: `docs/superpowers/specs/2026-03-13-url-analysis-design.md`

- [ ] **Step 1: Update docs/plans/2026-03-10-amazon-research-tool-design.md**

Make these replacements:

| Find | Replace |
|------|---------|
| `\| Database \| Supabase (PostgreSQL) \|` | `\| Database \| PostgreSQL (local, via psycopg3) \|` |
| `[Supabase DB]` (in ASCII architecture diagram) | `[PostgreSQL DB]` |
| `## Database Schema (Supabase)` | `## Database Schema (PostgreSQL)` |
| `supabase_client.py      # Supabase CRUD helpers` | `postgres_client.py   # PostgreSQL CRUD helpers` |
| `SUPABASE_URL = "..."` | `DATABASE_URL = "postgresql://localhost/amazon_purchase"` |
| `SUPABASE_KEY = "..."` | *(remove this line)* |
| `A custom \`amazon-scraper\` skill will be created to capture patterns for this project (scraping logic, agent prompts, Supabase schema helpers)` | `A custom \`amazon-scraper\` skill will be created to capture patterns for this project (scraping logic, agent prompts, PostgreSQL schema helpers)` |

- [ ] **Step 2: Update docs/plans/2026-03-10-amazon-research-tool-implementation.md**

Make these replacements (there may be multiple occurrences):

| Find | Replace |
|------|---------|
| `supabase==2.7.0` | `psycopg[binary]>=3.1\npsycopg-pool>=3.2` |
| `Supabase` (in tech stack line) | `PostgreSQL (local, psycopg3)` |
| `supabase_url: str` | `database_url: str` |
| `supabase_key: str` | *(remove this line)* |
| `SUPABASE_URL=https://your-project.supabase.co` | `DATABASE_URL=postgresql://user:password@localhost:5432/amazon_purchase` |
| `SUPABASE_KEY=your-anon-key` | *(remove this line)* |

- [ ] **Step 3: Update docs/skills/amazon-scraper.md**

Make these replacements:

| Find | Replace |
|------|---------|
| `└── supabase_client.py     # All DB read/write helpers` | `├── pool.py              # AsyncConnectionPool singleton\n│       └── postgres_client.py   # All DB read/write helpers` |
| `└── schema.sql           # Run this in Supabase SQL editor` | `└── schema.sql           # Run against local PostgreSQL: psql amazon_purchase < backend/db/schema.sql` |

- [ ] **Step 4: Update docs/superpowers/plans/2026-03-22-requirements-field.md**

Make these replacements:

| Find | Replace |
|------|---------|
| `Supabase (PostgreSQL)` (in tech stack line) | `PostgreSQL (local, psycopg3)` |
| `backend/db/supabase_client.py` (all occurrences) | `backend/db/postgres_client.py` |
| `db.supabase_client` (all occurrences in code snippets) | `db.postgres_client` |
| Any text referring to "Supabase SQL editor" | replace with "local PostgreSQL database" / `psql amazon_purchase` |
| Any text referring to "Supabase Table Editor" | replace with "check via `psql amazon_purchase -c '\d searches'`" |

- [ ] **Step 5: Update docs/superpowers/plans/2026-03-14-url-analysis.md**

Find:
```
without pulling in FastAPI + Supabase, which require environment variables and network access
```
Replace with:
```
without pulling in FastAPI + the database pool, which require environment variables and a running database
```

- [ ] **Step 6: Update docs/superpowers/specs/2026-03-22-requirements-field-design.md**

Make these replacements:

| Find | Replace |
|------|---------|
| `db/supabase_client.py` | `db/postgres_client.py` |
| `Apply in Supabase SQL editor before deploying.` | `Apply against your local PostgreSQL database: `psql amazon_purchase` then run the ALTER TABLE.` |

- [ ] **Step 7: Update docs/superpowers/specs/2026-03-13-url-analysis-design.md**

Find:
```
No saving URL analysis results to Supabase watchlist.
```
Replace with:
```
No saving URL analysis results to the watchlist database.
```

- [ ] **Step 8: Commit all doc updates**

```bash
git add docs/
git commit -m "docs: update all docs to reference local PostgreSQL instead of Supabase"
```

---

## Task 11: Smoke Test End-to-End

- [ ] **Step 1: Start the backend**

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload
```

Expected: Server starts, pool opens without errors. Log should show uvicorn running on port 8000.

- [ ] **Step 2: Test database connectivity**

```bash
curl http://localhost:8000/api/searches
```

Expected: `[]` (empty array — no searches yet)

- [ ] **Step 3: Start the frontend**

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000` and run a quick search to verify the full flow works end-to-end.

- [ ] **Step 4: Run full test suite**

```bash
cd backend
python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 5: Final commit**

```bash
git add -A
git status  # verify nothing unexpected
git commit -m "chore: finalize Supabase → PostgreSQL migration"
```
