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
