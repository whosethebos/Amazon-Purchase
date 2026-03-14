# backend/main.py
import asyncio
import json
import re
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from models import SearchRequest, ConfirmationRequest, AnalyzeUrlRequest
from agents.orchestrator import OrchestratorAgent
import db.supabase_client as db
from scraper.amazon import scrape_current_price, scrape_product_details
from config import settings
from llm.analyze import run_llm_analysis

app = FastAPI(title="Amazon Research Tool")

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
    search = db.create_search(request.query, request.max_results)
    search_id = str(search["id"])

    orchestrator = OrchestratorAgent(search_id, request.query)
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
    search = db.get_search(search_id)
    if not search:
        raise HTTPException(404, "Search not found")

    products = db.get_confirmed_products(search_id)
    result = []
    for product in products:
        analysis = db.get_analysis_by_product(product["id"])
        result.append({**product, "analysis": analysis})

    result.sort(key=lambda x: (x.get("analysis") or {}).get("rank") or 99)
    return {"search": search, "products": result}


@app.get("/api/preview-images")
async def get_preview_images(q: str):
    """Fetch up to 4 web image URLs for a query via DuckDuckGo (best-effort)."""
    try:
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        async with httpx.AsyncClient(timeout=5.0, headers=hdrs) as client:
            # Step 1: get vqd token
            r1 = await client.get(
                "https://duckduckgo.com/",
                params={"q": q, "iax": "images", "ia": "images"},
            )
            match = re.search(r"vqd=([^&'\"\s]+)", r1.text)
            if not match:
                return {"images": []}
            vqd = match.group(1)
            # Step 2: fetch image results
            r2 = await client.get(
                "https://duckduckgo.com/i.js",
                params={"q": q, "o": "json", "vqd": vqd, "f": ",,,,,", "p": "1"},
                headers={**hdrs, "Referer": "https://duckduckgo.com/"},
            )
            data = r2.json()
            images = [item["image"] for item in data.get("results", [])[:4]]
            return {"images": images}
    except Exception:
        return {"images": []}


# --- Search history ---

@app.get("/api/searches")
async def list_searches():
    """List all past searches for the home page history panel."""
    searches = db.list_searches()
    result = []
    for s in searches:
        products = db.get_confirmed_products(str(s["id"]))
        result.append({**s, "product_count": len(products)})
    return result


@app.delete("/api/searches/{search_id}")
async def delete_search(search_id: str):
    """Delete a search and all its associated data (cascade)."""
    db.delete_search(search_id)
    return {"ok": True}


# --- Watchlist ---

@app.get("/api/watchlist")
async def get_watchlist():
    """Get all watchlist items with current and previous price."""
    items = db.get_watchlist()
    result = []
    for item in items:
        product = item.get("products", {})
        price_history = db.get_price_history(str(product["id"])) if product else []
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
    item = db.add_to_watchlist(str(product_id))
    return item


@app.delete("/api/watchlist/{watchlist_id}")
async def remove_from_watchlist(watchlist_id: str):
    """Remove a product from the watchlist."""
    db.delete_watchlist_item(watchlist_id)
    return {"ok": True}


@app.post("/api/watchlist/{watchlist_id}/refresh")
async def refresh_watchlist_item(watchlist_id: str):
    """On-demand price refresh — re-scrapes the product page for current price."""
    items = db.get_watchlist()
    item = next((i for i in items if str(i["id"]) == watchlist_id), None)
    if not item:
        raise HTTPException(404, "Watchlist item not found")

    product = item.get("products", {})
    price_data = await scrape_current_price(product["url"])
    if price_data:
        db.insert_price_history(str(product["id"]), price_data["price"], price_data["currency"])
        db.update_watchlist_checked(watchlist_id)

    return {"price": price_data}


@app.post("/api/analyze-url")
async def analyze_url(req: AnalyzeUrlRequest):
    """Scrape and LLM-analyze a single Amazon product URL. 60-second best-effort timeout."""
    try:
        async with asyncio.timeout(60):
            asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", req.url)
            if not asin_match:
                return JSONResponse(
                    status_code=422,
                    content={"error": "Could not extract ASIN from URL"},
                )
            asin = asin_match.group(1)

            product_data = await scrape_product_details(req.url)
            reviews = product_data["reviews"]
            analysis = await run_llm_analysis(product_data["title"], reviews)

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
            content={"error": "Analysis timed out after 60 seconds"},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
