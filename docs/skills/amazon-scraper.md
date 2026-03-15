# Amazon Scraper Skill

Reference for developing and modifying the Amazon Product Research Tool.

## Project Structure

```
Amazon-Purchase/
├── backend/
│   ├── main.py                  # FastAPI app + all API routes
│   ├── config.py                # All settings (model, batch sizes, DB URLs)
│   ├── models.py                # Pydantic request/response schemas
│   ├── agents/
│   │   ├── orchestrator.py      # Main pipeline — coordinates all agents
│   │   ├── scraper_agent.py     # Fetches product batches from Amazon
│   │   ├── confirmation_agent.py # Tracks confirmation iteration loop
│   │   ├── analyst_agent.py     # LLM review analysis (pros/cons/summary)
│   │   └── ranker_agent.py      # LLM product scoring (0-100)
│   ├── scraper/
│   │   └── amazon.py            # All Playwright page interactions
│   ├── llm/
│   │   ├── ollama_client.py     # Ollama HTTP wrapper (model-agnostic)
│   │   └── analyze.py           # run_llm_analysis helper (isolated for testability)
│   ├── tests/
│   │   └── test_analyze_url.py  # Unit tests for pure logic
│   └── db/
│       ├── schema.sql           # Run this in Supabase SQL editor
│       └── supabase_client.py   # All DB read/write helpers
└── frontend/
    ├── app/page.tsx             # Home: search + watchlist + history
    ├── app/search/preview/      # Step 1: preview images before searching Amazon
    ├── app/search/[id]/confirm/ # Step 2: product confirmation grid
    ├── app/search/[id]/results/ # Step 3: ranked results
    ├── app/search/url-analysis/ # Direct URL/ASIN analysis page
    ├── components/              # All UI components
    └── lib/
        ├── api.ts               # All fetch helpers
        ├── types.ts             # TypeScript interfaces (AnalyzeUrlResponse, etc.)
        ├── useSSE.ts            # SSE hook for streaming backend events
        └── config.ts            # API URL config
```

## Common Commands

```bash
# Start backend
cd backend && uv run uvicorn main:app --reload

# Start frontend
cd frontend && npm run dev

# Run backend tests
cd backend && uv run pytest tests/ -v

# Install a new Python package
cd backend && uv add <pkg>

# Pull a different Ollama model
ollama pull <model-name>
```

## API Routes

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/search` | Start a new keyword search, returns `search_id` |
| GET | `/api/search/{id}/stream` | SSE stream of pipeline progress events |
| POST | `/api/search/{id}/confirm` | Submit selected product IDs to continue |
| GET | `/api/search/{id}/results` | Get final ranked results |
| GET | `/api/preview-images` | Preview images for a query (Google Images via Playwright) |
| POST | `/api/analyze-url` | Scrape + LLM-analyze a single Amazon product URL |
| GET | `/api/watchlist` | Get all watchlist items |
| POST | `/api/watchlist` | Add a product to watchlist |
| DELETE | `/api/watchlist/{id}` | Remove from watchlist |
| POST | `/api/watchlist/{id}/refresh` | Refresh price for a watchlist item |
| GET | `/api/search-history` | Get past searches |
| DELETE | `/api/search/{id}` | Delete a search from history |

## URL Detection (Frontend)

The home page search bar detects Amazon URLs and routes accordingly:

```ts
// Full product URL on any Amazon domain — ASIN is capture group 4
const AMAZON_ASIN_RE = /^https?:\/\/(www\.)?amazon\.\w+(\.\w+)?\/(dp|gp\/product)\/([A-Z0-9]{10})/;

// Any Amazon URL or short link (amzn.in, amzn.to)
const AMAZON_URL_RE = /^https?:\/\/(www\.)?amazon\.|^https?:\/\/amzn\./i;
```

- ASIN match → `/search/url-analysis?asin=...&url=...`
- Generic Amazon URL → `/search/url-analysis?url=...` (backend resolves short links)
- Anything else → `/search/preview?q=...` (normal keyword search flow)

## Supported Amazon Domains

`scrape_product_details` works with amazon.com, amazon.in, amazon.co.uk, amazon.de, amazon.fr, amazon.es, amazon.it. Currency is derived from the URL domain automatically. Short links (`amzn.in`, `amzn.to`) are resolved server-side via httpx GET before ASIN extraction.

## How to Change Things

**Change LLM model:**
Edit `backend/.env` → `OLLAMA_MODEL=llama3.2`
All agents share the same model via `config.settings.ollama_model`.

**Change ranking criteria (value/quality/reliability):**
Edit `RANKING_PROMPT` in `backend/agents/ranker_agent.py`.

**Change review analysis output:**
Edit `REVIEW_ANALYSIS_PROMPT` in `backend/agents/analyst_agent.py`.

**Change batch size (products per confirmation screen):**
Edit `backend/.env` → `AMAZON_BATCH_SIZE=10`

**Change max confirmation attempts before asking for more detail:**
Edit `backend/.env` → `MAX_CONFIRMATION_ITERATIONS=3`

**Change analyze-url timeout:**
Edit `asyncio.timeout(180)` in `POST /api/analyze-url` in `backend/main.py`.

**Add a new agent step:**
1. Create `backend/agents/your_agent.py` with a class `YourAgent`
2. Import and instantiate it in `backend/agents/orchestrator.py`
3. Add a new phase in `OrchestratorAgent.run()` and yield SSE status events

**Add a new scraped field (e.g. product category):**
1. Add selector in `backend/scraper/amazon.py` → `search_products()`
2. Add column to `backend/db/schema.sql` + run migration in Supabase
3. Add field to `ProductBase` in `backend/models.py`
4. Display in `frontend/components/ProductCard.tsx`

**Add a new API route:**
Add it to `backend/main.py` following the existing patterns.

## SSE Event Reference

| Event | Sent when | Key data fields |
|-------|-----------|-----------------|
| `status` | Any progress update | `message`, `status` |
| `batch_ready` | Product batch fetched | `batch`, `iteration`, `max_iterations`, `needs_more_detail` |
| `analysis_done` | One product analyzed | `product_id`, `analysis` |
| `need_more_detail` | Max iterations reached | `message` |
| `complete` | Pipeline finished | `search_id` |
| `error` | Something failed | `message` |

## Amazon Scraper Notes

### `search_products(query, max_results=10)`
Scrapes Amazon.com keyword search results. Returns products sorted by rating descending. Batch size controlled by `AMAZON_BATCH_SIZE` in `.env`.

### `scrape_product_details(url)`
Scrapes a single product page for full analysis. Handles international domains. Uses a priority-order selector cascade for price to avoid picking up MRP/crossed-out prices. Histogram is extracted from `.a-meter-bar` `style="width:X%"` attributes. Reviews are scraped from the product page itself after scrolling (the separate `/product-reviews/` page requires sign-in on amazon.in).

### `scrape_preview_images(query, max_images=4)`
Google Images search via headless Playwright. Returns up to 4 image URLs filtered by width >= 100px.

### `scrape_current_price(product_url)`
Lightweight price-only scrape for watchlist refresh.

## Database Tables

| Table | Purpose |
|-------|---------|
| `searches` | One row per search session |
| `products` | Scraped products (linked to search) |
| `reviews` | Individual reviews per product |
| `analysis` | LLM analysis output (pros, cons, score, rank) |
| `watchlist` | User's saved products |
| `price_history` | Price snapshots for watchlist refresh |
