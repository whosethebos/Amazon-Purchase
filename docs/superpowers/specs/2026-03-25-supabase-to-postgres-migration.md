# Supabase → Local PostgreSQL Migration — Design Spec

**Date:** 2026-03-25
**Status:** Approved

---

## Overview

Replace the Supabase client library with a direct local PostgreSQL connection using psycopg3 (async). The database schema is unchanged — all 6 tables, types, and constraints are already standard PostgreSQL. The migration is purely a driver swap: remove the Supabase SDK, add psycopg3 + connection pool, rewrite the thin DB client module with raw SQL.

---

## Motivation

The project is a local single-user tool. Supabase adds an external cloud dependency (URL + API key) that is unnecessary when PostgreSQL is available locally. A direct connection eliminates that dependency, removes credentials from config, and simplifies the setup for local development.

---

## Scope

### Files changed

| File | Change |
|------|--------|
| `backend/requirements.txt` | Replace `supabase>=2.7.0` → `psycopg[binary]>=3.1`, `psycopg-pool>=3.2` |
| `backend/config.py` | Replace `supabase_url` + `supabase_key` → single `database_url` |
| `backend/.env` | Replace `SUPABASE_URL` + `SUPABASE_KEY` → `DATABASE_URL` |
| `backend/.env.example` | Same as `.env` |
| `backend/db/supabase_client.py` | Rename → `postgres_client.py`; rewrite all functions as async psycopg3 raw SQL |
| `backend/db/pool.py` | New file — `AsyncConnectionPool` singleton, `get_pool()` accessor |
| `backend/db/__init__.py` | Update exports if needed |
| `backend/main.py` | Add FastAPI `lifespan` for pool open/close; update import to `postgres_client` |
| `backend/agents/orchestrator.py` | Update `import db.supabase_client as db` → `import db.postgres_client as db`; update any Supabase docstring references |
| `backend/db/schema.sql` | Add missing `requirements` column to `searches` table; update header comment |
| `backend/tests/test_requirements.py` | Update import path (`db.supabase_client` → `db.postgres_client`) and all patch targets |
| `backend/tests/test_analyze_url.py` | Update any patch targets referencing `db.supabase_client` |
| `README.md` | Update tech stack, prerequisites, setup instructions, config table |
| `docs/plans/2026-03-10-amazon-research-tool-design.md` | Update database references |
| `docs/plans/2026-03-10-amazon-research-tool-implementation.md` | Update tech stack, requirements, config, .env snippets |
| `docs/skills/amazon-scraper.md` | Update `supabase_client.py` → `postgres_client.py`, schema comment |
| `docs/superpowers/plans/2026-03-22-requirements-field.md` | Update file references and SQL instructions |
| `docs/superpowers/plans/2026-03-14-url-analysis.md` | Update Supabase mention |
| `docs/superpowers/specs/2026-03-22-requirements-field-design.md` | Update file reference and SQL instructions |
| `docs/superpowers/specs/2026-03-13-url-analysis-design.md` | Update Supabase mention |

### Files NOT changed

- All frontend files — no database knowledge in the frontend
- `backend/models.py` — Pydantic models unchanged
- `backend/scraper/` — no DB interaction
- `backend/llm/` — no DB interaction
- `backend/agents/analyst_agent.py`, `ranker_agent.py` — no direct DB calls

---

## Architecture

### Connection pool (`backend/db/pool.py`)

A module-level `AsyncConnectionPool` is created once and shared across all requests. The pool is opened in FastAPI's `lifespan` startup handler and closed on shutdown. All DB functions acquire a connection from the pool using `async with pool.connection()`.

`open=False` is passed to the constructor so the pool is not opened at import time (which would fail in an async context). `await _pool.open()` is called explicitly in the lifespan startup.

`row_factory=dict_row` is set at the pool level so every connection and cursor automatically returns plain dicts — no need to set it per-function.

```python
# pool.py (outline)
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from config import settings

_pool: AsyncConnectionPool | None = None

async def open_pool():
    global _pool
    # open=False: defer opening until we explicitly call await _pool.open()
    _pool = AsyncConnectionPool(
        settings.database_url,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await _pool.open()

async def close_pool():
    if _pool:
        await _pool.close()

def get_pool() -> AsyncConnectionPool:
    return _pool
```

### Lifespan in `main.py`

```python
from contextlib import asynccontextmanager
from db.pool import open_pool, close_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pool()
    yield
    await close_pool()

app = FastAPI(title="Amazon Research Tool", lifespan=lifespan)
```

### DB client (`backend/db/postgres_client.py`)

All functions become `async def`. Each uses `async with get_pool().connection() as conn`. The `dict_row` factory is set pool-wide (see above), so all cursors return dicts automatically.

psycopg3 `connection()` context manager auto-commits on clean exit and auto-rolls back on exception — matching the Supabase client's implicit per-operation commit behaviour.

Correct cursor usage — `execute()` returns a cursor; `fetchone()` is a separate awaited call on that cursor:

```python
# After (psycopg3) — correct form
async def create_search(query, max_results, requirements=None):
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "INSERT INTO searches (query, max_results, requirements, status) "
            "VALUES (%s, %s, %s, 'pending') RETURNING *",
            (query, max_results, Json(requirements or []))
        )
        return await cur.fetchone()
```

### JSONB columns

All JSONB columns (`pros`, `cons`, `requirements`) **must** be wrapped with `psycopg.types.json.Json(...)` when passing Python lists/dicts as parameters. psycopg3 does not automatically serialize Python lists to JSONB — without `Json(...)`, it would attempt to bind the value as a PostgreSQL array, causing a type error. Every function that writes to a JSONB column must use `Json(value)`.

Example: `insert_analysis(analysis)` passes `pros` and `cons` as lists — these must be wrapped before insertion.

### UUID columns

All primary keys are `UUID`. psycopg3 returns `uuid.UUID` objects (Python's `uuid` module type) rather than strings. The Supabase client returned UUID strings. `main.py` already calls `str(search["id"])` in several places, but callers must be checked for any path that passes a UUID value to JSON serialization or string comparison without an explicit `str()` cast. The safest approach is to cast all `id` fields to `str` at the point they are read from the DB, inside `postgres_client.py`, or to register a UUID dumper that returns strings.

### Non-trivial translations

#### `await` at call sites

All DB functions change from sync to `async def`. Every call in `orchestrator.py` and `main.py` must add `await`. For example, `db.update_search_status(...)` → `await db.update_search_status(...)`. Without `await`, Python silently returns a coroutine object instead of executing the query. This applies to all ~20 call sites across both files.

#### Bulk insert (`insert_products`, `insert_reviews`)

psycopg3's `execute()` handles one row. For list inserts, use `executemany()`:

```python
async def insert_products(products: list[dict]) -> list[dict]:
    async with get_pool().connection() as conn:
        rows = []
        for p in products:
            cur = await conn.execute(
                "INSERT INTO products (...) VALUES (...) RETURNING *", (...)
            )
            rows.append(await cur.fetchone())
        return rows
```

Or use `executemany()` for fire-and-forget bulk inserts (e.g. `insert_reviews` which returns nothing).

#### `confirm_products` — multi-ID update

`.in_("id", product_ids)` translates to `WHERE id = ANY(%s::uuid[])`:

```python
async def confirm_products(product_ids: list[str]) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE products SET confirmed = TRUE WHERE id = ANY(%s::uuid[])",
            (product_ids,)
        )
```

#### `add_to_watchlist` — upsert

The `watchlist` table has `UNIQUE(product_id)`. The Supabase `upsert` becomes:

```python
async def add_to_watchlist(product_id: str) -> dict:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "INSERT INTO watchlist (product_id) VALUES (%s) "
            "ON CONFLICT (product_id) DO UPDATE SET added_at = watchlist.added_at "
            "RETURNING *",
            (product_id,)
        )
        return await cur.fetchone()
```

#### `update_analysis_rank` — new function (replacing raw `get_client()` in orchestrator)

`orchestrator.py` Phase 4 currently calls `db.get_client()` and uses the Supabase fluent API directly to update `score` and `rank` on the analysis table. This inline call must be replaced with a new function in `postgres_client.py`:

```python
async def update_analysis_rank(product_id: str, score: int | None, rank: int | None) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE analysis SET score = %s, rank = %s WHERE product_id = %s",
            (score, rank, product_id)
        )
```

`orchestrator.py` Phase 4 then becomes:
```python
for item in ranked:
    await db.update_analysis_rank(item["id"], item.get("score"), item.get("rank"))
```

#### `find_or_create_product_by_asin` — SELECT + conditional INSERT

This function is imported directly in `main.py` (`from db.supabase_client import find_or_create_product_by_asin`). The import line must be updated to `from db.postgres_client import find_or_create_product_by_asin`. The function itself does a SELECT-then-INSERT pattern within a single connection (no JSONB columns written — products have no JSONB fields):

```python
async def find_or_create_product_by_asin(product: dict) -> dict:
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM products WHERE asin = %s LIMIT 1",
            (product["asin"],)
        )
        existing = await cur.fetchone()
        if existing:
            return existing
        cur = await conn.execute(
            "INSERT INTO products (..., confirmed) VALUES (..., TRUE) RETURNING *",
            (...)
        )
        return await cur.fetchone()
```

Both operations run within the same connection/transaction (auto-committed on clean exit).

#### `update_analysis_rank` — guard for `if existing:`

The current orchestrator Phase 4 guards the update with `if existing:` (checking `get_analysis_by_product` first). This guard is safe to drop: `insert_analysis` always runs unconditionally in Phase 3 for every confirmed product before Phase 4 executes. The replacement loop can call `update_analysis_rank` directly without the pre-check, simplifying the code.

#### Watchlist join

The one non-trivial read translation is `select("*, products(*)")`. This becomes a LEFT JOIN:

```sql
SELECT w.*, row_to_json(p) AS products
FROM watchlist w
LEFT JOIN products p ON p.id = w.product_id
ORDER BY w.added_at DESC
```

`main.py` already destructures `item.get("products", {})` so the shape is preserved.

---

## Configuration

```python
# config.py (after)
class Settings(BaseSettings):
    ollama_model: str = "qwen3:14b"
    ollama_base_url: str = "http://localhost:11434"
    database_url: str = "postgresql://localhost/amazon_purchase"
    amazon_domain: str = "amazon.in"
    amazon_batch_size: int = 5
    max_confirmation_iterations: int = 3
    max_reviews_per_product: int = 20
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
```

```
# .env.example (after)
DATABASE_URL=postgresql://user:password@localhost:5432/amazon_purchase
OLLAMA_MODEL=qwen3:14b
OLLAMA_BASE_URL=http://localhost:11434
AMAZON_BATCH_SIZE=5
MAX_CONFIRMATION_ITERATIONS=3
MAX_REVIEWS_PER_PRODUCT=20
FRONTEND_URL=http://localhost:3000
```

`python-dotenv` is retained in `requirements.txt` — pydantic-settings uses it to load the `.env` file.

---

## Schema change

Add the `requirements` column that was introduced in the `feat/requirements-field` branch but missing from `schema.sql`:

```sql
-- searches table, with requirements column included
CREATE TABLE searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    max_results INT DEFAULT 10,
    requirements JSONB DEFAULT '[]',
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

The header comment changes from "Run this in your Supabase project's SQL editor" to "Run this against your local PostgreSQL database to create the schema."

---

## What doesn't change

- All 6 table definitions, column types, constraints, and indexes (except the `requirements` addition)
- All function signatures in the DB client module (callers in `main.py` are unchanged)
- All Pydantic models, scrapers, LLM code, and frontend code
- Agent logic — only the import line in `orchestrator.py` changes

---

## Setup after migration

```bash
# Create the database
createdb amazon_purchase

# Apply schema
psql amazon_purchase < backend/db/schema.sql

# Set connection string in .env
DATABASE_URL=postgresql://localhost/amazon_purchase

# Install updated dependencies
pip install -r requirements.txt
```

---

## Key decisions

1. **psycopg3 over asyncpg** — Native async, standard `%s` placeholders, `dict_row` row factory gives identical dict output to the Supabase client. Less boilerplate than asyncpg's `$1` syntax.
2. **Pool-level `row_factory`** — Setting `row_factory=dict_row` at pool construction ensures all connections/cursors return dicts; no per-function setup needed and no leaking of state across pooled connections.
3. **`AsyncConnectionPool` over per-request connections** — Reusing connections across requests avoids connection overhead. Safe for a single-user local tool.
4. **Raw SQL over ORM** — The existing DB layer is already a thin, well-structured module. An ORM would add complexity with no benefit at this scale.
5. **No migration tooling** — Schema is applied fresh via `schema.sql`. No Alembic needed for a local tool where wiping and re-creating the DB is fine.
