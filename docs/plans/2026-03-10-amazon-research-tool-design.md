# Amazon Product Research Tool — Design Document

**Date:** 2026-03-10
**Status:** Approved

---

## Overview

A full-stack Amazon product research tool that uses AI agents to search, scrape, analyze, and rank products based on reviews and criteria. Users interact via a web UI to search for products, confirm matches, view ranked results with LLM-generated review summaries, and maintain a watchlist with price tracking.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js (App Router) + TypeScript |
| Backend | Python 3.11 + FastAPI |
| Agents | Google ADK (multi-agent orchestration) |
| LLM | Ollama — `qwen3:14b` (local, model-agnostic via config) |
| Scraping | Playwright (Python) |
| Database | Supabase (PostgreSQL) |
| Realtime | Server-Sent Events (SSE) |

---

## Architecture

```
[Next.js UI]
    │  POST /api/search  │  SSE stream
    ▼                    ▲
[FastAPI Backend]
    │ triggers
    ▼
[Google ADK Orchestrator Agent]
    ├── ScraperAgent         (Playwright → Amazon)
    ├── ConfirmationAgent    (batches products for user review)
    ├── ReviewAnalystAgent   (qwen3:14b → pros/cons/summary)
    └── RankerAgent          (qwen3:14b → 0-100 score)
              │
              ▼
       [Supabase DB]
```

---

## Agent Pipeline

### 1. OrchestratorAgent
- Entry point for all searches
- Coordinates all specialist agents in sequence
- Emits SSE events at each stage for live UI updates

### 2. ScraperAgent
- Uses Playwright to search Amazon for the user's query
- Fetches product batches (3–5 at a time): title, price, image URL, ASIN, product URL
- On confirmation rejection: fetches next batch
- On confirmed products: scrapes full product page + reviews

### 3. ConfirmationAgent
- Manages the iterative product confirmation loop
- Presents each batch to the user via SSE → UI shows image grid
- Tracks iteration count (max 3)
- After 3 failed iterations: requests more detail or reference image from user
- Passes confirmed products to ReviewAnalystAgent

### 4. ReviewAnalystAgent
- For each confirmed product: sends scraped reviews to Ollama (`qwen3:14b`)
- Prompt: extract structured JSON with `summary`, `pros[]`, `cons[]`, `sentiment`
- Output stored in `analysis` table

### 5. RankerAgent
- Receives all analyzed products
- Prompt: score each product 0–100 on value, quality, reliability
- Returns ranked list, stored in `analysis.score` and `analysis.rank`

---

## Folder Structure

```
Amazon-Purchase/
├── frontend/                       # Next.js + TypeScript
│   ├── src/app/
│   │   ├── page.tsx                # Home: search bar, watchlist, history
│   │   ├── search/[id]/
│   │   │   ├── confirm/page.tsx    # Phase 1: product image confirmation
│   │   │   └── results/page.tsx   # Phase 2: ranked results
│   ├── src/components/
│   │   ├── SearchBar.tsx
│   │   ├── ProductCard.tsx         # Opens Amazon URL in new tab
│   │   ├── ConfirmationGrid.tsx    # Image grid with select/reject
│   │   ├── ProgressFeed.tsx        # SSE live status updates
│   │   ├── ReviewSummary.tsx
│   │   ├── WatchlistCard.tsx       # Shows price + history
│   │   └── SearchHistory.tsx
│   └── src/lib/
│       ├── api.ts                  # API calls
│       └── useSSE.ts               # SSE hook
│
├── backend/                        # Python + FastAPI
│   ├── main.py                     # App entrypoint, API routes
│   ├── agents/
│   │   ├── orchestrator.py         # Google ADK orchestrator
│   │   ├── scraper_agent.py        # Playwright-based scraping
│   │   ├── confirmation_agent.py   # Batch confirmation logic
│   │   ├── analyst_agent.py        # Review analysis via Ollama
│   │   └── ranker_agent.py         # Product scoring via Ollama
│   ├── scraper/
│   │   └── amazon.py               # Low-level Playwright page interactions
│   ├── llm/
│   │   └── ollama_client.py        # Ollama HTTP client (model set via config)
│   ├── db/
│   │   └── supabase_client.py      # Supabase CRUD helpers
│   ├── models.py                   # Pydantic schemas
│   └── config.py                   # OLLAMA_MODEL, DB_URL, etc.
│
└── docs/plans/
    └── 2026-03-10-amazon-research-tool-design.md
```

---

## Database Schema (Supabase)

```sql
-- One row per user search session
CREATE TABLE searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    max_results INT DEFAULT 10,
    status TEXT DEFAULT 'pending',  -- pending | confirming | analyzing | done | failed
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- One row per scraped Amazon product
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

-- Individual scraped reviews
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

-- LLM analysis output per product
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

-- User's watchlist
CREATE TABLE watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ
);

-- Price history for watchlist items (on-demand refresh)
CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL,
    currency TEXT DEFAULT 'USD',
    checked_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## API Routes (FastAPI)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/search` | Start new search, returns search_id |
| GET | `/api/search/{id}/stream` | SSE stream of agent progress |
| POST | `/api/search/{id}/confirm` | Submit product confirmation choices |
| GET | `/api/search/{id}/results` | Fetch final ranked results |
| GET | `/api/searches` | List all past searches |
| DELETE | `/api/searches/{id}` | Delete search + its products |
| GET | `/api/watchlist` | Get all watchlist items |
| POST | `/api/watchlist` | Add product to watchlist |
| DELETE | `/api/watchlist/{id}` | Remove from watchlist |
| POST | `/api/watchlist/{id}/refresh` | Trigger on-demand price refresh |

---

## UI Pages

### Home (`/`)
- Search bar (top)
- Watchlist section: shows saved products with current price, price change indicator (↑/↓/=), [View] and [Delete] buttons
- Search History section: past searches with [View Results] and [Delete] buttons

### Confirmation (`/search/[id]/confirm`)
- Live progress feed (SSE) showing agent status
- Product batch grid (3–5 items): image, title, price, star rating
- Select/deselect individual products
- Buttons: [Select All] [Next Batch] [Confirm Selected]
- After 3 failed batches: prompt for more details or reference image

### Results (`/search/[id]/results`)
- Ranked list of confirmed + analyzed products
- Each card: rank badge, image, title, price, star rating, score badge
- Review summary: pros/cons lists, overall summary
- [+ Add to Watchlist] button
- [View on Amazon ↗] button — opens Amazon URL in new tab

---

## Configuration (`backend/config.py`)

```python
OLLAMA_MODEL = "qwen3:14b"       # Swap model here
OLLAMA_BASE_URL = "http://localhost:11434"
SUPABASE_URL = "..."
SUPABASE_KEY = "..."
AMAZON_BATCH_SIZE = 5            # Products per confirmation batch
MAX_CONFIRMATION_ITERATIONS = 3  # Before asking for more detail
MAX_REVIEWS_PER_PRODUCT = 20     # Reviews to scrape per product
```

---

## Key Design Decisions

1. **Playwright over HTTP scraping** — Amazon blocks raw HTTP requests; Playwright mimics real browser behavior
2. **SSE over WebSockets** — One-directional server→client streaming is sufficient; simpler setup
3. **On-demand watchlist refresh** — Avoids running background jobs; user triggers refresh on home page load
4. **Model-agnostic LLM client** — `OLLAMA_MODEL` in config means switching models requires one line change
5. **Clean agent separation** — Each agent has one responsibility; easy to modify scraping, analysis, or ranking independently

---

## Skill

A custom `amazon-scraper` skill will be created to capture patterns for this project (scraping logic, agent prompts, Supabase schema helpers) for reuse and reference during development.

---

## Verification

End-to-end test:
1. `cd backend && uvicorn main:app --reload`
2. `cd frontend && npm run dev`
3. Open `http://localhost:3000`
4. Search for "wireless headphones"
5. Confirm products match expectations (batch 1)
6. Observe SSE progress as reviews are analyzed
7. View ranked results with scores and summaries
8. Add top product to watchlist
9. Return to home — verify watchlist shows product
10. Click "View on Amazon" — verify correct Amazon URL opens
11. Delete search from history — verify it disappears
