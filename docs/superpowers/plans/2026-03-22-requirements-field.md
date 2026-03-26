# Requirements Field Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional tag-based requirements field to the search UI that flows through the full pipeline — narrowing the Amazon search query and providing explicit context to the LLM for scoring and ranking.

**Architecture:** Requirements are captured as `string[]` in the SearchBar UI, serialised as repeated `req=` URL params, sent as `requirements: string[]` in the POST body, stored in the `searches` table, passed through the OrchestratorAgent to both the analyst and ranker prompts.

**Tech Stack:** Next.js 14 (React), FastAPI, Pydantic v2, PostgreSQL (local, psycopg3), Ollama LLM

---

## File Map

| File | Change |
|------|--------|
| `frontend/components/SearchBar.tsx` | Add requirements tag input, update Props type |
| `frontend/app/page.tsx` | Read `req` params, pass initialRequirements, update handleSearch |
| `frontend/app/search/preview/page.tsx` | Read `req` params, pass to startSearch, preserve on back nav |
| `frontend/lib/api.ts` | Update `startSearch` signature to include requirements |
| `backend/models.py` | Add `requirements: list[str] = []` to `SearchRequest` |
| `backend/main.py` | Pass requirements to `create_search` and `OrchestratorAgent` |
| `backend/db/postgres_client.py` | Update `create_search` signature |
| `backend/agents/orchestrator.py` | Accept + use requirements in constructor and pipeline phases |
| `backend/agents/analyst_agent.py` | Accept requirements, build dynamic prompt when non-empty |
| `backend/agents/ranker_agent.py` | Accept requirements, append requirements block to prompt |
| `backend/tests/test_requirements.py` | New test file covering backend logic |

---

## Task 1: Database Migration

**Files:**
- Apply SQL in local PostgreSQL database

- [ ] **Step 1: Apply the migration**

Open local PostgreSQL database and run:
```sql
ALTER TABLE searches
  ADD COLUMN IF NOT EXISTS requirements JSONB NOT NULL DEFAULT '[]'::jsonb;
```

- [ ] **Step 2: Verify**

Run `psql amazon_purchase -c "\\d searches"` and confirm the `requirements` column exists with default `'[]'`.

- [ ] **Step 3: Commit note**

This step is manual (no file change), so no git commit needed here. Move to Task 2.

---

## Task 2: Backend Models + DB Client

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/db/postgres_client.py`
- Create: `backend/tests/test_requirements.py`

- [ ] **Step 1: Write failing tests for create_search signature**

Create `backend/tests/test_requirements.py`:

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


def test_create_search_passes_requirements_to_db():
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "abc123", "query": "desk", "max_results": 10, "requirements": ["60 inch"]}
    ]
    with patch("db.postgres_client.get_client", return_value=mock_client):
        result = create_search("desk", 10, ["60 inch"])
    insert_call = mock_client.table.return_value.insert.call_args[0][0]
    assert insert_call["requirements"] == ["60 inch"]
    assert result["id"] == "abc123"


def test_create_search_requirements_defaults_to_empty():
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "abc123", "query": "desk", "max_results": 10, "requirements": []}
    ]
    with patch("db.postgres_client.get_client", return_value=mock_client):
        result = create_search("desk", 10)
    insert_call = mock_client.table.return_value.insert.call_args[0][0]
    assert insert_call["requirements"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/backend
.venv/bin/pytest tests/test_requirements.py -v
```

Expected: FAIL — `requirements` not yet on `SearchRequest`, `create_search` doesn't accept it.

- [ ] **Step 3: Update `models.py` — add requirements to SearchRequest**

In `backend/models.py`, change:
```python
class SearchRequest(BaseModel):
    query: str
    max_results: int = 10
```
To:
```python
class SearchRequest(BaseModel):
    query: str
    max_results: int = 10
    requirements: list[str] = []
```

- [ ] **Step 4: Update `db/postgres_client.py` — create_search signature**

In `backend/db/postgres_client.py`, change:
```python
def create_search(query: str, max_results: int) -> dict:
    client = get_client()
    result = client.table("searches").insert({
        "query": query,
        "max_results": max_results,
        "status": "pending",
    }).execute()
    return result.data[0]
```
To:
```python
def create_search(query: str, max_results: int, requirements: list[str] | None = None) -> dict:
    client = get_client()
    result = client.table("searches").insert({
        "query": query,
        "max_results": max_results,
        "requirements": requirements or [],
        "status": "pending",
    }).execute()
    return result.data[0]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/backend
.venv/bin/pytest tests/test_requirements.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Run full test suite to verify no regressions**

```bash
.venv/bin/pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase
git add backend/models.py backend/db/postgres_client.py backend/tests/test_requirements.py
git commit -m "feat: add requirements field to SearchRequest model and create_search db function"
```

---

## Task 3: OrchestratorAgent — Thread Requirements Through Pipeline

**Files:**
- Modify: `backend/agents/orchestrator.py`
- Modify: `backend/tests/test_requirements.py`

- [ ] **Step 1: Write failing tests for orchestrator requirements**

Append to `backend/tests/test_requirements.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_requirements.py::test_orchestrator_stores_requirements -v
```

Expected: FAIL — `OrchestratorAgent.__init__` only accepts `(search_id, query)`.

- [ ] **Step 3: Update `orchestrator.py` — constructor and pipeline**

In `backend/agents/orchestrator.py`, change the `__init__` signature from:
```python
def __init__(self, search_id: str, query: str):
    self.search_id = search_id
    self.query = query
```
To:
```python
def __init__(self, search_id: str, query: str, requirements: list[str] | None = None):
    self.search_id = search_id
    self.query = query
    self.requirements = requirements or []
```

In Phase 1 of `run()`, change:
```python
products = await self.scraper.fetch_batch(self.query, offset=offset)
```
To:
```python
search_query = self.query
if self.requirements:
    search_query = f"{self.query} {' '.join(self.requirements)}"
products = await self.scraper.fetch_batch(search_query, offset=offset)
```

In Phase 3, change:
```python
analysis = await self.analyst.analyze(product["title"], reviews)
```
To:
```python
analysis = await self.analyst.analyze(product["title"], reviews, self.requirements)
```

In Phase 4, change:
```python
ranked = await self.ranker.rank(confirmed_products, analyses)
```
To:
```python
ranked = await self.ranker.rank(confirmed_products, analyses, self.requirements)
```

- [ ] **Step 4: Run orchestrator tests**

```bash
.venv/bin/pytest tests/test_requirements.py -v
```

Expected: All 7 tests PASS (4 from Task 2 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add backend/agents/orchestrator.py backend/tests/test_requirements.py
git commit -m "feat: thread requirements through OrchestratorAgent pipeline"
```

---

## Task 4: Analyst Agent — Requirements-Aware Prompt

**Files:**
- Modify: `backend/agents/analyst_agent.py`
- Modify: `backend/tests/test_requirements.py`

- [ ] **Step 1: Write failing tests for analyst requirements**

Append to `backend/tests/test_requirements.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
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

    # Base prompt uses REVIEW_ANALYSIS_PROMPT.format() — check no requirements block
    assert "user requirements" not in captured_prompt["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_requirements.py::test_analyst_uses_requirements_in_prompt -v
```

Expected: FAIL — `analyze` doesn't accept `requirements` param.

- [ ] **Step 3: Update `analyst_agent.py`**

Change the `analyze` method signature and body:

```python
async def analyze(
    self, product_title: str, reviews: list[dict], requirements: list[str] | None = None
) -> dict:
    """
    Returns analysis dict: summary, pros, cons, sentiment.
    When requirements are provided, the LLM is asked to note whether the product meets them.
    """
    if not reviews:
        return {
            "summary": "No reviews available.",
            "pros": [],
            "cons": [],
            "sentiment": "mixed",
        }

    reviews_text = "\n\n".join([
        f"Rating: {r.get('rating', '?')}/5\n{r.get('title', '')}\n{r.get('body', '')}"
        for r in reviews[:20]
    ])

    if requirements:
        req_block = "\n".join(f"- {r}" for r in requirements)
        prompt = (
            f"You are a product review analyst.\n\n"
            f"Analyze the following Amazon product reviews and return a JSON object with:\n"
            f'- "summary": a 2-3 sentence overview of what customers think\n'
            f'- "pros": a list of 3-5 key positive points (strings)\n'
            f'- "cons": a list of 2-4 key negative points (strings)\n'
            f'- "sentiment": overall sentiment, one of "positive", "mixed", or "negative"\n\n'
            f"Note whether the product meets these user requirements in your summary:\n"
            f"{req_block}\n\n"
            f"Product: {product_title}\n\n"
            f"Reviews:\n{reviews_text}\n\n"
            f"Return only valid JSON, no extra text."
        )
    else:
        prompt = REVIEW_ANALYSIS_PROMPT.format(
            title=product_title,
            reviews_text=reviews_text,
        )

    result = await chat_json([{"role": "user", "content": prompt}])
    return {
        "summary": result.get("summary", ""),
        "pros": result.get("pros", []),
        "cons": result.get("cons", []),
        "sentiment": result.get("sentiment", "mixed"),
    }
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_requirements.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/analyst_agent.py backend/tests/test_requirements.py
git commit -m "feat: add requirements context to analyst agent prompt"
```

---

## Task 5: Ranker Agent — Requirements-Aware Scoring

**Files:**
- Modify: `backend/agents/ranker_agent.py`
- Modify: `backend/tests/test_requirements.py`

- [ ] **Step 1: Write failing tests for ranker requirements**

Append to `backend/tests/test_requirements.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_requirements.py::test_ranker_appends_requirements_to_prompt -v
```

Expected: FAIL — `rank` doesn't accept `requirements` param.

- [ ] **Step 3: Update `ranker_agent.py`**

Change the `rank` method signature from:
```python
async def rank(self, products: list[dict], analyses: dict[str, dict]) -> list[dict]:
```
To:
```python
async def rank(
    self, products: list[dict], analyses: dict[str, dict], requirements: list[str] | None = None
) -> list[dict]:
```

Change the `chat_json` call from:
```python
result = await chat_json([{
    "role": "user",
    "content": RANKING_PROMPT.format(products_text=products_text)
}])
```
To:
```python
if requirements:
    req_block = "\n".join(f"- {r}" for r in requirements)
    content = (
        RANKING_PROMPT.format(products_text=products_text)
        + f"\n\nAdditional user requirements — products meeting more of these should score higher:\n{req_block}"
    )
else:
    content = RANKING_PROMPT.format(products_text=products_text)

result = await chat_json([{"role": "user", "content": content}])
```

- [ ] **Step 4: Run all tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: All tests PASS (including existing test_analyze_url.py tests).

- [ ] **Step 5: Commit**

```bash
git add backend/agents/ranker_agent.py backend/tests/test_requirements.py
git commit -m "feat: add requirements context to ranker agent scoring prompt"
```

---

## Task 6: Wire Requirements Through API Endpoint (`main.py`)

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/tests/test_requirements.py`

- [ ] **Step 1: Write failing test for endpoint wiring**

Append to `backend/tests/test_requirements.py`:

```python
import httpx
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_search_endpoint_passes_requirements_to_orchestrator():
    """Verify that POST /api/search forwards requirements to OrchestratorAgent."""
    created_with = {}

    def fake_create_search(query, max_results, requirements=None):
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

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/backend
.venv/bin/pytest tests/test_requirements.py::test_search_endpoint_passes_requirements_to_orchestrator -v
```

Expected: FAIL — endpoint doesn't pass requirements yet.

- [ ] **Step 3: Update `/api/search` endpoint in `main.py`**

Change the two wiring lines in `start_search`:
```python
search = db.create_search(request.query, request.max_results, request.requirements)
search_id = str(search["id"])

orchestrator = OrchestratorAgent(search_id, request.query, request.requirements)
```

(Only `db.create_search` and `OrchestratorAgent` calls change — add `request.requirements` as third arg to each.)

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_requirements.py
git commit -m "feat: pass requirements from API endpoint to db and orchestrator"
```

---

## Task 7: Frontend — Update `startSearch` API Client

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Update `startSearch` function**

In `frontend/lib/api.ts`, change:
```ts
export async function startSearch(query: string, maxResults = 10): Promise<{ search_id: string }> {
  const res = await fetch(`${API_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, max_results: maxResults }),
  });
  if (!res.ok) throw new Error("Failed to start search");
  return res.json();
}
```
To:
```ts
export async function startSearch(
  query: string,
  requirements: string[] = [],
  maxResults = 10
): Promise<{ search_id: string }> {
  const res = await fetch(`${API_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, requirements, max_results: maxResults }),
  });
  if (!res.ok) throw new Error("Failed to start search");
  return res.json();
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add requirements param to startSearch API client"
```

---

## Task 8: Preview Page — Read and Forward Requirements

**Files:**
- Modify: `frontend/app/search/preview/page.tsx`

- [ ] **Step 1: Update `PreviewContent` to read, use, and preserve requirements**

In `frontend/app/search/preview/page.tsx`, inside `PreviewContent`:

**Add requirements extraction** after `const q = ...`:
```ts
const requirements = searchParams.getAll("req");
```

**Update `handleNo`** — change:
```ts
const handleNo = () => {
  router.push(`/?q=${encodeURIComponent(q)}`);
};
```
To:
```ts
const handleNo = () => {
  const reqParams = requirements.map(r => `req=${encodeURIComponent(r)}`).join("&");
  router.push(`/?q=${encodeURIComponent(q)}${reqParams ? "&" + reqParams : ""}`);
};
```

**Update `handleConfirm`** — change:
```ts
const { search_id } = await startSearch(q);
```
To:
```ts
const { search_id } = await startSearch(q, requirements);
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/search/preview/page.tsx
git commit -m "feat: read and forward req params in preview page"
```

---

## Task 9: SearchBar Component — Requirements Tag Input

**Files:**
- Modify: `frontend/components/SearchBar.tsx`

- [ ] **Step 1: Rewrite SearchBar with requirements tags**

Replace the full contents of `frontend/components/SearchBar.tsx` with:

```tsx
// frontend/components/SearchBar.tsx
"use client";
import { useState, useEffect, KeyboardEvent } from "react";
import { Search, X } from "lucide-react";

type Props = {
  onSearch: (query: string, requirements: string[]) => void;
  isLoading?: boolean;
  initialValue?: string;
  initialRequirements?: string[];
};

export function SearchBar({ onSearch, isLoading, initialValue, initialRequirements }: Props) {
  const [query, setQuery] = useState(initialValue ?? "");
  const [requirements, setRequirements] = useState<string[]>(initialRequirements ?? []);
  const [reqInput, setReqInput] = useState("");

  useEffect(() => {
    setQuery(initialValue ?? "");
  }, [initialValue]);

  useEffect(() => {
    setRequirements(initialRequirements ?? []);
  }, [initialRequirements]);

  const addTag = (value: string) => {
    const trimmed = value.trim().slice(0, 100);
    if (!trimmed) return;
    setRequirements(prev => {
      if (prev.includes(trimmed) || prev.length >= 10) return prev;
      return [...prev, trimmed];
    });
  };

  const handleReqKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addTag(reqInput);
      setReqInput("");
    } else if (e.key === ",") {
      e.preventDefault();
      reqInput.split(",").forEach(addTag);
      setReqInput("");
    }
  };

  const removeTag = (tag: string) => {
    setRequirements(prev => prev.filter(t => t !== tag));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim(), requirements);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      {/* Main search row */}
      <div className="bg-[#0f0f1a] border border-[#1f1f38] rounded-[14px] p-2.5 flex gap-2.5 shadow-[0_0_0_1px_rgba(249,115,22,0.12),_0_8px_32px_rgba(0,0,0,0.6)]">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for a product on Amazon..."
          className="flex-1 bg-transparent border-none outline-none text-[#ebebf5] placeholder-[#2e2e50] text-[15px] px-2"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className="bg-gradient-to-br from-[#f97316] to-[#ea580c] shadow-[0_4px_16px_rgba(249,115,22,0.35)] rounded-[10px] px-5 py-2.5 text-white font-bold flex items-center gap-2 disabled:opacity-40 transition-opacity"
        >
          <Search size={16} />
          {isLoading ? "Searching..." : "Search"}
        </button>
      </div>

      {/* Requirements row */}
      <div className="bg-[#0f0f1a] border border-[#1f1f38] rounded-[14px] p-3">
        <p className="text-[10px] font-bold text-[#4a4a70] uppercase tracking-widest mb-2">
          Requirements <span className="font-normal normal-case tracking-normal">(optional)</span>
        </p>

        {/* Tags */}
        {requirements.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {requirements.map(tag => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 bg-[#1e1e3a] border border-[#818cf8]/30 text-[#818cf8] text-[12px] rounded-full px-2.5 py-0.5"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="text-[#818cf8]/60 hover:text-[#818cf8] transition-colors"
                >
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Tag input */}
        <input
          type="text"
          value={reqInput}
          onChange={(e) => setReqInput(e.target.value)}
          onKeyDown={handleReqKeyDown}
          placeholder="Type a requirement and press Enter..."
          className="w-full bg-transparent border-none outline-none text-[#ebebf5] placeholder-[#2e2e50] text-[13px]"
          disabled={isLoading}
        />
        <p className="text-[10px] text-[#2e2e50] mt-1.5">
          Press Enter or , to add · click × to remove
        </p>
      </div>
    </form>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/frontend
npx tsc --noEmit
```

Expected: No errors (SearchBar now exports updated Props, but page.tsx still uses old `onSearch: (query: string) => void` — tsc will report a mismatch here; that's expected and will be fixed in Task 10).

- [ ] **Step 3: Commit SearchBar only**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase
git add frontend/components/SearchBar.tsx
git commit -m "feat: add requirements tag input UI to SearchBar component"
```

---

## Task 10: Main Page — Read Requirements and Pass to SearchBar

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Update `HomeContent` to read requirements from URL**

In `frontend/app/page.tsx`, inside `HomeContent`:

**Add requirements extraction** after `const initialQuery = ...`:
```ts
const initialRequirements = searchParams.getAll("req");
```

**Update `handleSearch`** — change:
```ts
const handleSearch = (query: string) => {
  const trimmed = query.trim();
  const asinMatch = trimmed.match(AMAZON_ASIN_RE);
  if (asinMatch) {
    const asin = asinMatch[4];
    router.push(`/search/url-analysis?asin=${asin}&url=${encodeURIComponent(trimmed)}`);
    return;
  }
  if (AMAZON_URL_RE.test(trimmed)) {
    router.push(`/search/url-analysis?url=${encodeURIComponent(trimmed)}`);
    return;
  }
  router.push(`/search/preview?q=${encodeURIComponent(query)}`);
};
```
To:
```ts
const handleSearch = (query: string, requirements: string[]) => {
  const trimmed = query.trim();
  const asinMatch = trimmed.match(AMAZON_ASIN_RE);
  if (asinMatch) {
    const asin = asinMatch[4];
    router.push(`/search/url-analysis?asin=${asin}&url=${encodeURIComponent(trimmed)}`);
    return;
  }
  if (AMAZON_URL_RE.test(trimmed)) {
    router.push(`/search/url-analysis?url=${encodeURIComponent(trimmed)}`);
    return;
  }
  const reqParams = requirements.map(r => `req=${encodeURIComponent(r)}`).join("&");
  router.push(`/search/preview?q=${encodeURIComponent(query)}${reqParams ? "&" + reqParams : ""}`);
};
```

**Update `<SearchBar>`** — add `initialRequirements`:
```tsx
<SearchBar
  onSearch={handleSearch}
  isLoading={false}
  initialValue={initialQuery}
  initialRequirements={initialRequirements}
/>
```

- [ ] **Step 2: Verify TypeScript compiles cleanly**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: read req params and wire requirements through main page to SearchBar"
```

---

## Task 11: Manual End-to-End Smoke Test

- [ ] **Step 1: Start backend**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/backend
.venv/bin/uvicorn main:app --reload
```

- [ ] **Step 2: Start frontend**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/frontend
npm run dev
```

- [ ] **Step 3: Test the flow**

1. Open `http://localhost:3000`
2. Type "standing desk" in search, add requirements "60 inch width" and "under $300"
3. Click Search → preview page URL should include `&req=60+inch+width&req=under+%24300`
4. Click "← Back" → home page search box should re-populate both the query and tags
5. Click Search → Confirm → verify search starts
6. Check `searches` table in psql — `requirements` column should contain `["60 inch width", "under $300"]`
7. After analysis completes, verify results include products ranked with requirements context

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -p
git commit -m "fix: address smoke test issues"
```

---

## Summary of All Commits

1. `feat: add requirements field to SearchRequest model and create_search db function`
2. `feat: thread requirements through OrchestratorAgent pipeline`
3. `feat: add requirements context to analyst agent prompt`
4. `feat: add requirements context to ranker agent scoring prompt`
5. `feat: pass requirements from API endpoint to db and orchestrator`
6. `feat: add requirements param to startSearch API client`
7. `feat: read and forward req params in preview page`
8. `feat: add requirements tag input UI to SearchBar component`
9. `feat: read req params and wire requirements through main page to SearchBar`
