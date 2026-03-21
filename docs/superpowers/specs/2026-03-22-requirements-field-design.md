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
- A row of dismissible tag chips (indigo, matching the app's `#818cf8` accent color) for active requirements
- A text input with placeholder `"Type a requirement and press Enter..."`
- A hint line: `Press Enter or , to add · click tag to remove`

**Interaction:**
- User types a requirement → presses `Enter` or `,` → it becomes a tag chip
- Clicking a chip removes it
- Tags are stored as `string[]` in local component state

**Styling:** The requirements box uses the same `bg-[#0f0f1a] border border-[#1f1f38] rounded-[14px] p-3` treatment as the existing search bar, maintaining visual consistency.

**SearchBar props change:**
```ts
type Props = {
  onSearch: (query: string, requirements: string[]) => void;
  isLoading?: boolean;
  initialValue?: string;
};
```

### Main Page (`page.tsx`)

`handleSearch` receives `requirements: string[]` alongside `query`. For keyword searches, requirements are URL-encoded and passed to the preview page:

```
/search/preview?q=adjustable+table&req=60-inch+width,under+$500
```

For Amazon URL searches (direct to `/search/url-analysis`), requirements are passed as a `req` URL param too, but the URL analysis flow doesn't use requirements (it analyzes a specific product, not a discovery query), so they're silently dropped.

### Preview Page (`search/preview/page.tsx`)

Reads the `req` param from the URL, splits on `,` to reconstruct the `string[]`, and passes it to `startSearch(query, requirements)`.

---

## Backend Design

### `models.py`

```python
class SearchRequest(BaseModel):
    query: str
    max_results: int = 10
    requirements: list[str] = []   # NEW — optional, backward-compatible
```

### `main.py` — `/api/search` endpoint

Pass `request.requirements` to both the `OrchestratorAgent` constructor and `db.create_search`.

### `db/supabase_client.py` — `create_search`

Store requirements as a JSON array in a new `requirements` column on the `searches` table (nullable, defaults to `[]`). Supabase accepts JSON natively.

### `agents/orchestrator.py` — `OrchestratorAgent`

Constructor receives `requirements: list[str]`. When building the Amazon search query, append requirements to the query string:

```python
search_query = query
if requirements:
    search_query = f"{query} {' '.join(requirements)}"
```

Store `requirements` on the instance for later use in the LLM step.

### `llm/analyze.py` — `run_llm_analysis`

New optional parameter `requirements: list[str] = []`. When non-empty, inject into the LLM prompt:

```
The user is specifically looking for products that meet these requirements:
- 60-inch width
- under $500
- solid wood

Factor these requirements into your scoring. Products that satisfy more requirements should score higher.
```

This block is appended to the existing system/user prompt before the review text.

---

## Data Flow Summary

```
User types query + adds requirement tags
        ↓
SearchBar.onSearch(query, requirements)
        ↓
page.tsx handleSearch → router.push(/search/preview?q=...&req=...)
        ↓
PreviewPage reads req param → startSearch(query, requirements)
        ↓
POST /api/search  { query, requirements, max_results }
        ↓
OrchestratorAgent(search_id, query, requirements)
  ├─ Amazon search: "{query} {requirements joined}"
  └─ LLM prompt: includes requirements block
        ↓
Results ranked with requirements context
```

---

## What Is Not Changing

- The URL analysis flow (`/search/url-analysis`) does not use requirements — it analyzes a specific product URL, not a discovery query.
- The watchlist, search history display, and results page UI are unchanged.
- No changes to the confirmation grid or SSE stream.

---

## Open Questions / Future Work

- Requirements are not currently displayed on the results page (kept simple per Option B). This can be added later.
- Requirements are not pre-populated when re-running a search from history. Future enhancement.
