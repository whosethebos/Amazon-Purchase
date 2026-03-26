# backend/main.py
import asyncio
import httpx
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from models import SearchRequest, ConfirmationRequest, AnalyzeUrlRequest
from agents.orchestrator import OrchestratorAgent
import db.postgres_client as db
from db.postgres_client import find_or_create_product_by_asin
from db.pool import open_pool, close_pool
from scraper.amazon import scrape_current_price, scrape_product_details, scrape_preview_images, extract_asin, search_products
from config import settings
from llm.analyze import run_llm_analysis


def _validate_score(raw) -> int | None:
    """Coerce LLM-returned score to int 1–10, or None if invalid."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, float):
        raw = round(raw)
    elif isinstance(raw, str):
        try:
            raw = int(raw)
        except ValueError:
            return None
    if isinstance(raw, int) and 1 <= raw <= 10:
        return raw
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pool()
    yield
    await close_pool()


app = FastAPI(title="Amazon Research Tool", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store of active orchestrators and SSE queues keyed by search_id.
# Fine for a local single-user tool. For multi-user, swap for Redis.
_active_orchestrators: dict[str, OrchestratorAgent] = {}
_sse_queues: dict[str, asyncio.Queue] = {}


# --- Search ---

@app.post("/api/search")
async def start_search(request: SearchRequest, background_tasks: BackgroundTasks):
    """Start a new search. Returns search_id immediately."""
    search = await db.create_search(request.query, request.max_results, request.requirements)
    search_id = str(search["id"])

    orchestrator = OrchestratorAgent(search_id, request.query, request.requirements)
    _active_orchestrators[search_id] = orchestrator

    queue: asyncio.Queue = asyncio.Queue()
    _sse_queues[search_id] = queue

    async def run_and_queue():
        async for event in orchestrator.run():
            await queue.put(event)
        await queue.put(None)  # sentinel to close the SSE stream

    background_tasks.add_task(run_and_queue)
    return {"search_id": search_id}


@app.get("/api/search/{search_id}/stream")
async def stream_search(search_id: str):
    """SSE stream of agent progress events for the UI."""
    queue = _sse_queues.get(search_id)
    if not queue:
        raise HTTPException(404, "Search not found or stream already closed")

    async def event_generator():
        while True:
            event = await queue.get()
            if event is None:
                yield 'data: {"event": "done"}\n\n'
                break
            yield f"data: {json.dumps(event)}\n\n"
        _sse_queues.pop(search_id, None)
        _active_orchestrators.pop(search_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/search/{search_id}/confirm")
async def confirm_products(search_id: str, request: ConfirmationRequest):
    """
    Submit product confirmation.
    product_ids=[] means reject all and fetch next batch.
    """
    orchestrator = _active_orchestrators.get(search_id)
    if not orchestrator:
        raise HTTPException(404, "Active search not found")
    await orchestrator.receive_confirmation([str(pid) for pid in request.product_ids])
    return {"ok": True}


@app.get("/api/search/{search_id}/results")
async def get_results(search_id: str):
    """Fetch final ranked results for a completed search."""
    search = await db.get_search(search_id)
    if not search:
        raise HTTPException(404, "Search not found")

    products = await db.get_confirmed_products(search_id)
    result = []
    for product in products:
        analysis = await db.get_analysis_by_product(product["id"])
        result.append({**product, "analysis": analysis})

    result.sort(key=lambda x: (x.get("analysis") or {}).get("rank") or 99)
    return {"search": search, "products": result}


@app.get("/api/preview-images")
async def get_preview_images(q: str):
    """Fetch up to 4 web image URLs for a query via DuckDuckGo (best-effort)."""
    images = await scrape_preview_images(q)
    return {"images": images}


@app.get("/api/similar-products")
async def get_similar_products(asin: str, title: str):
    """Find similar Amazon products by searching with the product title."""
    try:
        if not title.strip():
            return {"products": []}
        query = " ".join(title.split()[:6])
        results = await search_products(query, max_results=8)
        filtered = [p for p in results if p.get("asin") != asin]
        return {"products": filtered[:4]}
    except Exception:
        return {"products": []}


@app.get("/api/searches")
async def list_searches():
    """List all past searches for the home page history panel."""
    searches = await db.list_searches()
    result = []
    for s in searches:
        products = await db.get_confirmed_products(str(s["id"]))
        result.append({**s, "product_count": len(products)})
    return result


@app.delete("/api/searches/{search_id}")
async def delete_search(search_id: str):
    """Delete a search and all its associated data (cascade)."""
    await db.delete_search(search_id)
    return {"ok": True}


# --- Watchlist ---

@app.get("/api/watchlist")
async def get_watchlist():
    """Get all watchlist items with current and previous price."""
    items = await db.get_watchlist()
    result = []
    for item in items:
        product = item.get("products", {})
        price_history = await db.get_price_history(str(product["id"])) if product else []
        current_price = price_history[0]["price"] if price_history else product.get("price")
        previous_price = price_history[1]["price"] if len(price_history) > 1 else None
        result.append({
            "id": item["id"],
            "product": product,
            "added_at": item["added_at"],
            "last_checked_at": item["last_checked_at"],
            "current_price": current_price,
            "previous_price": previous_price,
        })
    return result


@app.post("/api/watchlist")
async def add_to_watchlist(body: dict):
    """Add a product to the watchlist by product_id."""
    product_id = body.get("product_id")
    if not product_id:
        raise HTTPException(400, "product_id required")
    item = await db.add_to_watchlist(str(product_id))
    return item


@app.post("/api/watchlist/from-url")
async def add_to_watchlist_from_url(body: dict):
    """Add a URL-analyzed product to the watchlist, creating the product record if needed."""
    asin = body.get("asin")
    if not asin:
        raise HTTPException(400, "asin required")
    product_record = await find_or_create_product_by_asin({
        "asin": asin,
        "title": body.get("title"),
        "price": body.get("price"),
        "currency": body.get("currency"),
        "rating": body.get("rating"),
        "review_count": body.get("review_count"),
        "image_url": body.get("image_url"),
        "url": body.get("url"),
    })
    item = await db.add_to_watchlist(str(product_record["id"]))
    return item


@app.delete("/api/watchlist/{watchlist_id}")
async def remove_from_watchlist(watchlist_id: str):
    """Remove a product from the watchlist."""
    await db.delete_watchlist_item(watchlist_id)
    return {"ok": True}


@app.post("/api/watchlist/{watchlist_id}/refresh")
async def refresh_watchlist_item(watchlist_id: str):
    """On-demand price refresh — re-scrapes the product page for current price."""
    items = await db.get_watchlist()
    item = next((i for i in items if str(i["id"]) == watchlist_id), None)
    if not item:
        raise HTTPException(404, "Watchlist item not found")

    product = item.get("products", {})
    price_data = await scrape_current_price(product["url"])
    if price_data:
        await db.insert_price_history(str(product["id"]), price_data["price"], price_data["currency"])
        await db.update_watchlist_checked(watchlist_id)

    return {"price": price_data}


@app.post("/api/analyze-url")
async def analyze_url(req: AnalyzeUrlRequest):
    """Scrape and LLM-analyze a single Amazon product URL."""
    try:
        async with asyncio.timeout(180):
            url = req.url
            if not extract_asin(url):
                # Short URL (e.g. amzn.in) — resolve redirect to get full URL
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
                async with httpx.AsyncClient(follow_redirects=True, timeout=10, headers=headers) as client:
                    resp = await client.get(url)
                    url = str(resp.url)
            asin = extract_asin(url)
            if not asin:
                return JSONResponse(
                    status_code=422,
                    content={"error": "Could not extract ASIN from URL"},
                )

            product_data = await scrape_product_details(url)
            reviews = product_data["reviews"]
            analysis = await run_llm_analysis(
                product_data["title"],
                reviews,
                histogram=product_data["histogram"],
                review_count=product_data["review_count"],
            )
            analysis["score"] = _validate_score(analysis.get("score"))

            valid_indices = [
                i for i in analysis.get("featured_review_indices", [])
                if 0 <= i < len(reviews)
            ]
            if not valid_indices and reviews:
                valid_indices = [0]
            analysis["featured_review_indices"] = valid_indices

            return {
                "product": {
                    k: product_data[k]
                    for k in ("asin", "title", "price", "currency", "rating", "review_count", "image_url")
                },
                "histogram": product_data["histogram"],
                "analysis": analysis,
                "reviews": reviews,
            }
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=500,
            content={"error": "Analysis timed out after 180 seconds"},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
