# Requirements Field — Design Spec

**Date:** 2026-03-22
**Status:** Approved

## Overview

Add an optional tag-based requirements field to the main search page. Users can specify product criteria (e.g. dimensions, brand preferences, price range) before searching. These requirements flow through the full pipeline: they narrow the Amazon product discovery query and are passed as explicit context to the LLM so it scores and ranks products against them.

---

## UI Design

### SearchBar Component

A requirements section is added directly below the existing search input, always visible. It consists of:

- A small `REQUIREMENTS (optional)` label in the existing `text-[10px] font-bold text-[#4a4a70] uppercase tracking-widest` style
- A row of dismissible tag chips (indigo, matching `#818cf8`) for active requirements
- A text input with placeholder `"Type a requirement and press Enter..."`
- A hint line: `Press Enter or , to add · click × to remove`

**Interaction:**
- User types a requirement → presses `Enter` → input is trimmed; if non-empty it becomes a tag chip
- User presses `,` → input is split on commas, each non-empty trimmed part becomes a separate tag chip, input is cleared
- Clicking a chip's × removes it
- Tags are stored as `string[]` in local component state inside `SearchBar`
- Maximum 10 tags; attempting to add more is silently ignored
- Empty or whitespace-only input is discarded without adding a tag
- Duplicate tags (exact string match) are silently deduplicated — adding a tag already present is a no-op
- Per-tag character maximum: 100 characters (excess silently truncated)

**Styling:** The requirements box uses the same `bg-[#0f0f1a] border border-[#1f1f38] rounded-[14px] p-3` treatment as the existing search bar.

**SearchBar props:**
```ts
type Props = {
  onSearch: (query: string, requirements: string[]) => void;
  isLoading?: boolean;
  initialValue?: string;
  initialRequirements?: string[];  // NEW — seeds tags on mount
};
```

`initialRequirements` uses the same `useEffect` seed pattern as `initialValue`:
```ts
useEffect(() => {
  setRequirements(initialRequirements ?? []);
}, [initialRequirements]);
```

### Main Page (`page.tsx`)

Reads both `q` and `req` from `useSearchParams` on mount:
```ts
const initialQuery = searchParams.get("q") ?? "";
const initialRequirements = searchParams.getAll("req");
```

Passes both to `SearchBar`:
```tsx
<SearchBar
  onSearch={handleSearch}
  isLoading={false}
  initialValue={initialQuery}
  initialRequirements={initialRequirements}
/>
```

`handleSearch` receives `(query: string, requirements: string[])`. For keyword searches, requirements are passed to the preview page as repeated `req` params:
```
/search/preview?q=adjustable+table&req=60-inch+width&req=under+%24500&req=solid+wood
```

Using repeated params avoids comma-collision — requirements can contain commas without mis-splitting.

For Amazon URL searches (direct to `/search/url-analysis`), requirements are not forwarded.

### Preview Page (`search/preview/page.tsx`)

Reads requirements with `searchParams.getAll('req')` → `string[]`. Passes them to `startSearch(query, requirements)`.

On back navigation (`handleNo`), reconstructs the full URL with req params preserved:
```ts
const reqParams = requirements.map(r => `req=${encodeURIComponent(r)}`).join('&');
router.push(`/?q=${encodeURIComponent(q)}${reqParams ? '&' + reqParams : ''}`);
```

This allows the home page to re-seed `SearchBar` tags from the URL on mount.

---

## Backend Design

### `lib/api.ts` — `startSearch`

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

When `requirements` is `[]`, the field is still sent in the body as `[]` (not omitted). The backend's default handles both correctly.

### `models.py`

```python
class SearchRequest(BaseModel):
    query: str
    max_results: int = 10
    requirements: list[str] = []   # NEW — optional, backward-compatible
```

No server-side length/content validation is added (single-user local tool; frontend enforces limits).

### `main.py` — `/api/search` endpoint

Call order is unchanged — `create_search` is called first to obtain `search_id`, then the orchestrator is instantiated:

```python
search = db.create_search(request.query, request.max_results, request.requirements)
search_id = str(search["id"])

orchestrator = OrchestratorAgent(search_id, request.query, request.requirements)
```

### `db/postgres_client.py` — `create_search`

Updated signature and body:
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

`SearchHistoryItem` Pydantic model is **not** updated — requirements are stored but not returned in the history list response. If requirements need to be surfaced in history in the future, `SearchHistoryItem` will need a `requirements: list[str]` field added at that time.

### Database Migration

```sql
ALTER TABLE searches
  ADD COLUMN IF NOT EXISTS requirements JSONB NOT NULL DEFAULT '[]'::jsonb;
```

Apply against your local PostgreSQL database. Existing rows get `[]` automatically via the default. Existing rows get `[]` automatically via the default.

### `agents/orchestrator.py` — `OrchestratorAgent`

Constructor:
```python
def __init__(self, search_id: str, query: str, requirements: list[str] | None = None):
    self.search_id = search_id
    self.query = query
    self.requirements = requirements or []
    # ... rest unchanged
```

**Phase 1 — Amazon search query:** Requirements are appended verbatim as keywords. This is intentional — requirements are treated as a raw keyword append to improve product discovery, not as structured filters. The naive concatenation is accepted as sufficient for this use case:
```python
search_query = self.query
if self.requirements:
    search_query = f"{self.query} {' '.join(self.requirements)}"
products = await self.scraper.fetch_batch(search_query, offset=offset)
```

**Phase 3 — LLM analysis:**
```python
analysis = await self.analyst.analyze(product["title"], reviews, self.requirements)
```

**Phase 4 — Ranking:**
```python
ranked = await self.ranker.rank(confirmed_products, analyses, self.requirements)
```

### `agents/analyst_agent.py` — `ReviewAnalystAgent.analyze`

Updated signature:
```python
async def analyze(
    self, product_title: str, reviews: list[dict], requirements: list[str] | None = None
) -> dict:
```

Return type is **unchanged**: `{summary, pros, cons, sentiment}`. No `score` field is added here — score comes from `RankerAgent` in Phase 4 (0-100 scale, existing behavior).

**Prompt construction:** When `requirements` is non-empty, the prompt is built dynamically using f-string/concatenation rather than the module-level constant — this avoids placeholder pollution:

```python
if requirements:
    req_block = "\n".join(f"- {r}" for r in requirements)
    prompt = (
        f"You are a product review analyst.\n\n"
        f"Analyze the following Amazon product reviews and return a JSON object with:\n"
        f'- "summary": a 2-3 sentence overview...\n'
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
```

When `requirements` is empty, `REVIEW_ANALYSIS_PROMPT.format()` is used unchanged — the prompt is identical to the current behavior.

### `agents/ranker_agent.py` — `RankerAgent.rank`

Updated signature:
```python
async def rank(
    self, products: list[dict], analyses: dict[str, dict], requirements: list[str] | None = None
) -> list[dict]:
```

Same dynamic construction strategy — when requirements are present, build the prompt with an extra block appended after the scoring criteria; otherwise use `RANKING_PROMPT.format()` unchanged:

```python
if requirements:
    req_block = "\n".join(f"- {r}" for r in requirements)
    content = (
        RANKING_PROMPT.format(products_text=products_text)
        + f"\n\nAdditional user requirements — products meeting more of these should score higher:\n{req_block}"
    )
else:
    content = RANKING_PROMPT.format(products_text=products_text)
```

Ranking output uses the existing 0-100 scale.

---

## Data Flow Summary

```
User types query + adds requirement tags (max 10, max 100 chars each)
        ↓
SearchBar.onSearch(query, requirements)
        ↓
page.tsx handleSearch → router.push(/search/preview?q=...&req=...&req=...)
        ↓
PreviewPage: searchParams.getAll('req') → startSearch(query, requirements)
Back nav: reconstructs /?q=...&req=... so tags are preserved on home page
        ↓
POST /api/search  { query, requirements: [...], max_results }
        ↓
create_search(query, max_results, requirements) → search_id
OrchestratorAgent(search_id, query, requirements)
  ├─ Phase 1: Amazon search with "{query} {requirements joined}"
  ├─ Phase 3: analyst.analyze(title, reviews, requirements)
  │           → returns {summary, pros, cons, sentiment}  [score NOT here]
  └─ Phase 4: ranker.rank(products, analyses, requirements)
              → returns products with score (0-100) and rank
        ↓
Results ranked with requirements context
```

---

## What Is Not Changing

- The URL analysis flow (`/search/url-analysis`) does not use requirements.
- The watchlist, search history display, and results page UI are unchanged.
- No changes to the confirmation grid or SSE stream.
- `SearchHistoryItem` Pydantic model is unchanged (requirements not surfaced in history yet).

---

## Future Work

- Display active requirements as tags on the results page (Option C — deferred).
- Pre-populate requirements when re-running a search from history (requires adding `requirements: list[str]` to `SearchHistoryItem` at that time).
