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
│   │   └── ollama_client.py     # Ollama HTTP wrapper (model-agnostic)
│   └── db/
│       ├── schema.sql           # Run this in Supabase SQL editor
│       └── supabase_client.py   # All DB read/write helpers
└── frontend/
    ├── app/page.tsx             # Home: search + watchlist + history
    ├── app/search/[id]/confirm/ # Phase 1: product confirmation grid
    ├── app/search/[id]/results/ # Phase 2: ranked results
    ├── components/              # All UI components
    └── lib/                     # api.ts, useSSE.ts, config.ts
```

## Common Commands

```bash
# Start backend
cd backend && uv run uvicorn main:app --reload

# Start frontend
cd frontend && bun run dev

# Install a new Python package
cd backend && uv add <pkg>

# Pull a different Ollama model
ollama pull <model-name>
```

## How to Change Things

**Change LLM model:**
Edit `backend/.env` → `OLLAMA_MODEL=llama3.2`
All agents share the same model via `config.settings.ollama_model`.

**Change ranking criteria (value/quality/reliability):**
Edit `RANKING_PROMPT` in `backend/agents/ranker_agent.py`.

**Change review analysis output:**
Edit `REVIEW_ANALYSIS_PROMPT` in `backend/agents/analyst_agent.py`.

**Change batch size (products per confirmation screen):**
Edit `backend/.env` → `AMAZON_BATCH_SIZE=5`

**Change max confirmation attempts before asking for more detail:**
Edit `backend/.env` → `MAX_CONFIRMATION_ITERATIONS=3`

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

## Database Tables

| Table | Purpose |
|-------|---------|
| `searches` | One row per search session |
| `products` | Scraped products (linked to search) |
| `reviews` | Individual reviews per product |
| `analysis` | LLM analysis output (pros, cons, score, rank) |
| `watchlist` | User's saved products |
| `price_history` | Price snapshots for watchlist refresh |
