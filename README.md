# Amazon Research Tool

An AI-powered product research tool that searches Amazon, analyzes customer reviews, and ranks products using a local LLM. Paste a product keyword or an Amazon URL to get structured insights — pros, cons, score, and featured reviews — without ads or sponsored results.

---

## Features

- **Keyword search** — type any product query and get a curated list of Amazon results
- **URL analysis** — paste an Amazon product URL (including short links like `amzn.in`) for instant single-product analysis
- **AI review analysis** — a local Ollama LLM reads customer reviews and returns a structured summary with pros, cons, and a 0–100 score
- **Rating histogram** — visual breakdown of 1★ through 5★ distribution from the product page
- **Watchlist** — save products and track their price over time with one-click refresh
- **Search history** — revisit any past search and its ranked results
- **Real-time progress** — live SSE feed shows every step as the agent scrapes and analyzes

---

## Screenshots

> Add screenshots to `docs/screenshots/` and update the paths below.

| Home — search + watchlist | Preview confirmation |
|---|---|
| ![Home page](docs/screenshots/home.png) | ![Preview page](docs/screenshots/preview.png) |

| Product confirmation grid | Ranked results |
|---|---|
| ![Confirm page](docs/screenshots/confirm.png) | ![Results page](docs/screenshots/results.png) |

| URL analysis — single product |
|---|
| ![URL analysis page](docs/screenshots/url-analysis.png) |

---

## Architecture

```
Amazon-Purchase/
├── backend/                  # FastAPI + Playwright + Ollama
│   ├── main.py               # REST + SSE API endpoints
│   ├── config.py             # Settings (domain, LLM model, batch size…)
│   ├── models.py             # Pydantic request/response models
│   ├── agents/
│   │   └── orchestrator.py   # Multi-step search workflow (search → confirm → analyze → rank)
│   ├── scraper/
│   │   └── amazon.py         # Playwright scrapers for search, product details, images
│   ├── llm/
│   │   └── analyze.py        # Ollama LLM call for review analysis
│   └── db/
│       └── supabase_client.py # Supabase persistence (searches, products, watchlist, price history)
│
└── frontend/                 # Next.js 15 + Tailwind CSS
    ├── app/
    │   ├── page.tsx                        # Home — search bar, watchlist, history
    │   ├── search/preview/page.tsx         # Step 1 — confirm query with Bing image preview
    │   ├── search/[id]/confirm/page.tsx    # Step 2 — pick products from batch, live SSE feed
    │   ├── search/[id]/results/page.tsx    # Step 3 — ranked results with analysis
    │   └── search/url-analysis/page.tsx   # Direct URL analysis (histogram + AI)
    ├── components/
    │   ├── ProductCard.tsx    # Ranked product card with pros/cons/score
    │   ├── ProgressFeed.tsx   # Live SSE event log
    │   └── SearchHistory.tsx  # Past searches list
    └── lib/
        ├── api.ts             # Typed fetch wrappers for all backend endpoints
        ├── useSSE.ts          # SSE hook for streaming agent progress
        └── types.ts           # Shared TypeScript types
```

### Data flow

```
User types query
  → Preview page fetches Bing image thumbnails (confirmation step)
  → POST /api/search — orchestrator starts in background
  → GET /api/search/{id}/stream — SSE stream drives UI
      orchestrator: search Amazon → batch_ready event
  → User confirms products → POST /api/search/{id}/confirm
      orchestrator: scrape reviews → LLM analysis → rank
  → GET /api/search/{id}/results — final ranked list
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, Tailwind CSS, TypeScript |
| Backend | FastAPI, Python 3.13, asyncio |
| Scraping | Playwright (headless Chromium) |
| AI / LLM | Ollama (local) — default model: `qwen3:14b` |
| Database | Supabase (PostgreSQL) |
| Streaming | Server-Sent Events (SSE) |

---

## Prerequisites

- **Node.js** 18+
- **Python** 3.13+
- **Playwright** — Chromium browser (installed automatically)
- **Ollama** running locally with a supported model
- **Supabase** project (free tier works)

---

## Setup

### 1. Clone

```bash
git clone https://github.com/your-username/Amazon-Purchase.git
cd Amazon-Purchase
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Edit .env — set SUPABASE_URL, SUPABASE_KEY, OLLAMA_MODEL
```

Start the backend:

```bash
uvicorn main:app --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Configuration

All settings live in `backend/config.py` and can be overridden via environment variables in `backend/.env`:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `qwen3:14b` | Local LLM model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `SUPABASE_URL` | — | Your Supabase project URL |
| `SUPABASE_KEY` | — | Your Supabase anon/service key |
| `AMAZON_DOMAIN` | `amazon.in` | Amazon domain to search (`amazon.com`, `amazon.co.uk`, …) |
| `AMAZON_BATCH_SIZE` | `5` | Products shown per confirmation round |
| `MAX_REVIEWS_PER_PRODUCT` | `20` | Reviews scraped per product |
| `FRONTEND_URL` | `http://localhost:3000` | CORS allowed origin |

---

## How It Works

1. **Search** — Playwright opens Amazon, scrapes the first N results (titles, prices, ratings, images)
2. **Confirm** — up to `AMAZON_BATCH_SIZE` products are shown; you pick the ones that match your intent
3. **Analyze** — for each confirmed product, Playwright scrapes the reviews page; the LLM synthesizes a structured analysis (summary, pros, cons, score 0–100, rank)
4. **Results** — products are sorted by LLM-assigned rank and displayed with their analysis

For direct URL input, steps 1–2 are skipped: the product page and reviews are scraped immediately, and analysis runs in one pass.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/search` | Start a new search, returns `search_id` |
| `GET` | `/api/search/{id}/stream` | SSE stream of agent progress events |
| `POST` | `/api/search/{id}/confirm` | Submit selected product IDs |
| `GET` | `/api/search/{id}/results` | Fetch final ranked results |
| `GET` | `/api/searches` | List all past searches |
| `DELETE` | `/api/searches/{id}` | Delete a search and its data |
| `GET` | `/api/preview-images?q=` | Fetch Bing image thumbnails for query |
| `POST` | `/api/analyze-url` | Scrape + analyze a single Amazon URL |
| `GET` | `/api/watchlist` | Get watchlist with current prices |
| `POST` | `/api/watchlist` | Add product to watchlist |
| `DELETE` | `/api/watchlist/{id}` | Remove from watchlist |
| `POST` | `/api/watchlist/{id}/refresh` | Re-scrape current price |

---

## Notes

- This tool is intended for **personal, local use** only. It uses Playwright to scrape Amazon pages, which may conflict with Amazon's terms of service. Use responsibly.
- Scraping is intentionally slow (2-second pauses) to avoid bot detection.
- The LLM analysis quality depends on your chosen Ollama model and available VRAM. `qwen3:14b` works well on 16 GB RAM.
