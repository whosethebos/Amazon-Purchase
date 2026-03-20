# Score & Similar Products — Design Spec

**Date:** 2026-03-21
**Status:** Approved

## Overview

Two new features for the URL analysis page:
1. An overall product score (out of 10) shown prominently at the top of the analysis
2. A lazy-loaded "Similar Products" section at the bottom linking directly to Amazon

---

## Feature 1: Product Score (out of 10)

### Backend — `backend/llm/analyze.py`

- Change `run_llm_analysis` signature to accept `histogram` and `review_count`:
  ```python
  async def run_llm_analysis(
      title: str,
      reviews: list[dict],
      histogram: dict,
      review_count: int | None,
  ) -> dict:
  ```
- Include histogram distribution and review count in the prompt so the LLM can score based on them
- Extend the LLM JSON output shape:
  ```json
  {
    "summary": "...",
    "pros": [...],
    "cons": [...],
    "featured_review_indices": [...],
    "score": 7
  }
  ```
- Prompt wording must explicitly say: *"Return `score` as a plain integer (not a float, not a string) between 1 and 10 inclusive"*
- Criteria for scoring:
  - Value for the price (sentiment in reviews about price/quality ratio)
  - Volume and trustworthiness of reviews (review_count)
  - Star distribution quality (histogram percentages)
  - Overall pros/cons balance
- `_LLM_FALLBACK` gains `"score": None`. To prevent mutation hazards, `run_llm_analysis` must return `dict(_LLM_FALLBACK)` (a shallow copy), not the dict directly

### Backend — `backend/main.py`

- Update the `run_llm_analysis` call to pass `histogram=product_data["histogram"]` and `review_count=product_data["review_count"]`
- After the call returns, apply score validation in order:
  1. `raw = analysis.get("score")`
  2. If `raw is None`, skip to step 6 (already null)
  3. If `isinstance(raw, bool)`: `raw = None` (bool is a subclass of int in Python; reject it explicitly)
  4. Else if `isinstance(raw, float)`: `raw = round(raw)` (round to nearest int before range check)
  5. Else if `isinstance(raw, str)`: try `raw = int(raw)`, on ValueError set `raw = None`
  6. If `raw` is not None and not an int in range 1–10: `raw = None`
  7. `analysis["score"] = raw`

### Frontend Types — `frontend/lib/types.ts`

- `asin: string` already exists on `ProductInfo` — no change needed
- Add `score: number | null` to `ReviewAnalysis`

### Frontend UI — `frontend/app/search/url-analysis/page.tsx`

- A new `ScoreCard` component renders between the back link and Section A (Product Header)
- Score display:
  - Large number (e.g. "7/10")
  - Color-coded by value:
    - 1–3: red (`text-red-400`)
    - 4–6: yellow (`text-yellow-400`)
    - 7–10: green (`text-emerald-400`)
  - Label beneath the number:
    - 7–10: "Good buy"
    - 4–6: "Mixed bag"
    - 1–3: "Avoid"
  - Any out-of-range non-null value (e.g. `0`) is treated as null and the card is hidden — the frontend can assume the backend always validates to 1–10 or null
- Card hidden entirely if `score` is null
- Card uses `bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-5` to match the page style

---

## Feature 2: Similar Products (lazy-loaded)

### Backend — `backend/main.py`

- Add `search_products` to the existing import from `scraper.amazon`
- New endpoint: `GET /api/similar-products`
  - Query params: `asin: str`, `title: str` — both required (FastAPI raises 422 if missing, which is acceptable — the frontend always provides them)
  - If `title.strip()` is empty, return `{"products": []}` immediately without making an Amazon request
  - Build search query: `" ".join(title.split()[:6])` — takes the first 6 whitespace-delimited tokens (or all tokens if fewer than 6)
  - Call `search_products(query, max_results=8)` — 8 results requested to give headroom after filtering. The source product may not appear in results at all, so fewer than 4 results being returned is an accepted edge case (the frontend handles any list length ≥ 0)
  - Filter out any result whose `asin` matches the `asin` query param
  - Return the first 4 remaining results (or all of them if fewer than 4 remain)
  - Response shape:
    ```json
    {
      "products": [
        {
          "asin": "...",
          "title": "...",
          "price": 29.99,
          "currency": "USD",
          "rating": 4.3,
          "review_count": 1500,
          "image_url": "https://...",
          "url": "https://www.amazon.com/dp/..."
        }
      ]
    }
    ```
  - Entire handler wrapped in `try/except` — return `{"products": []}` on any exception (never 500s to the client)

### Frontend Types — `frontend/lib/types.ts`

- New interface:
  ```ts
  export interface SimilarProduct {
    asin: string;
    title: string;
    price: number | null;
    currency: string | null;
    rating: number | null;
    review_count: number | null;
    image_url: string | null;
    url: string;
  }
  ```

### Frontend API — `frontend/lib/api.ts`

- New function `fetchSimilarProducts(asin: string, title: string): Promise<SimilarProduct[]>`
- URL: `GET /api/similar-products?asin=<encodeURIComponent(asin)>&title=<encodeURIComponent(title)>`
- Returns `[]` on any error

### Frontend UI — `frontend/app/search/url-analysis/page.tsx`

- New state: `similarProducts: SimilarProduct[] | null` (null = loading, [] = empty/failed)
- A `useEffect` with dependency array `[data]` calls `fetchSimilarProducts` when `data` becomes non-null. Uses `data.product.asin` and `data.product.title`. The effect guards with `if (!data) return` at the top. In the current implementation `data` is write-once (set by `analyzeUrl().then(setData)` and never reset), so the effect fires exactly once. **Known limitation:** no AbortController is used for the `fetchSimilarProducts` call — this is acceptable because `data` cannot be reset in the current implementation. If `data` is ever made resettable in future, an AbortController must be added
- Section renders at the bottom (below Featured Reviews):
  - **Loading** (`similarProducts === null`): 4 skeleton cards using `animate-pulse` + grey backgrounds
  - **Loaded with results**: responsive grid of product cards, each card:
    - Product image (or grey placeholder if `image_url` is null)
    - Title truncated to 2 lines (`line-clamp-2`)
    - Price + currency
    - Star rating + review count
    - Entire card is `<a href={url} target="_blank" rel="noopener noreferrer">`
  - **Empty/failed** (`similarProducts.length === 0`): section hidden entirely
- Card styling: `bg-[#0f0f1a] border border-[#2a2a45] rounded-xl` with `hover:border-[#818cf8] transition-colors`

---

## Data Flow

```
User lands on /search/url-analysis?url=...
  │
  ├─► POST /api/analyze-url  (existing, ~30–60s)
  │     └─► Returns product + histogram + analysis (with score) + reviews
  │           └─► Page renders:
  │                 [Back link]
  │                 ScoreCard             ← new, between back link and Section A
  │                 Section A: ProductHeader
  │                 Section B: RatingBreakdown
  │                 Section C: AIAnalysis
  │                 Section D: FeaturedReviews
  │                 Section E: SimilarProducts (skeleton)   ← new
  │                       │
  │                       └─► GET /api/similar-products?asin=...&title=...  (~15–25s)
  │                             └─► Section E: skeleton → cards (or hidden if empty)
```

---

## Files Changed

| File | Change |
|------|--------|
| `backend/llm/analyze.py` | Add `histogram` + `review_count` params; add `score` to prompt; return copy of fallback dict |
| `backend/main.py` | Pass new params to `run_llm_analysis`; add score validation (round then range-check); add `search_products` import; add `GET /api/similar-products` |
| `frontend/lib/types.ts` | Add `score: number | null` to `ReviewAnalysis`; add `SimilarProduct` interface (`asin` already on `ProductInfo`) |
| `frontend/lib/api.ts` | Add `fetchSimilarProducts()` with `encodeURIComponent` on both params |
| `frontend/app/search/url-analysis/page.tsx` | Add `ScoreCard` between back link and Section A; add `similarProducts` state + `useEffect([data])`; add Section E with skeleton + product cards |
