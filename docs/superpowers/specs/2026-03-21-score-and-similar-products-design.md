# Score & Similar Products — Design Spec

**Date:** 2026-03-21
**Status:** Approved

## Overview

Two new features for the URL analysis page:
1. An overall product score (out of 10) shown prominently at the top of the analysis
2. A lazy-loaded "Similar Products" section at the bottom linking directly to Amazon

---

## Feature 1: Product Score (out of 10)

### Backend

- **File:** `backend/llm/analyze.py`
- Extend the existing LLM JSON prompt to include a `score` field:
  ```json
  {
    "summary": "...",
    "pros": [...],
    "cons": [...],
    "featured_review_indices": [...],
    "score": 7
  }
  ```
- Prompt instructs the model to score 1–10 (integer) based on:
  - Value for the price (sentiment in reviews about price/quality ratio)
  - Volume and trustworthiness of reviews (review count)
  - Star distribution quality (histogram weighting)
  - Overall pros/cons balance
- The fallback dict in `_LLM_FALLBACK` gains `"score": null` (null = not available)

### Frontend Types

- **File:** `frontend/lib/types.ts`
- Add `score: number | null` to `ReviewAnalysis`

### Frontend UI

- **File:** `frontend/app/search/url-analysis/page.tsx`
- A new `ScoreCard` component renders above the product header (Section A)
- Score display:
  - Large number (e.g. "7/10")
  - Color-coded:
    - 1–3: red (`text-red-400`)
    - 4–6: yellow (`text-yellow-400`)
    - 7–10: green (`text-emerald-400`)
  - Label beneath score:
    - 7–10: "Good buy"
    - 4–6: "Mixed bag"
    - 1–3: "Avoid"
- Card uses the same `bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-5` styling as the rest of the page
- Hidden entirely if `score` is null

---

## Feature 2: Similar Products (lazy-loaded)

### Backend

- **File:** `backend/main.py`
- New endpoint: `GET /api/similar-products`
  - Query params: `asin` (string), `title` (string)
  - Builds a search query from the first 6 words of `title`
  - Calls existing `search_products(query, max_results=6)`
  - Filters out the product matching `asin` from results
  - Returns up to 4 products
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
  - Returns `{"products": []}` on any error (never 500s to the client)

### Frontend Types

- **File:** `frontend/lib/types.ts`
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

### Frontend API

- **File:** `frontend/lib/api.ts`
- New function `fetchSimilarProducts(asin: string, title: string): Promise<SimilarProduct[]>`
- Calls `GET /api/similar-products?asin=...&title=...`
- Returns `[]` on error

### Frontend UI

- **File:** `frontend/app/search/url-analysis/page.tsx`
- After `data` is set (main analysis done), a `useEffect` triggers `fetchSimilarProducts`
- State: `similarProducts: SimilarProduct[] | null` (null = loading, [] = empty/failed)
- Section renders at the bottom of the page (below Featured Reviews):
  - **Loading state** (`similarProducts === null`): 4 skeleton placeholder cards (grey shimmer)
  - **Loaded with results**: grid of product cards — each card shows:
    - Product image (or grey placeholder if null)
    - Title (truncated to 2 lines)
    - Price + currency
    - Star rating + review count
    - Entire card is an `<a href={url} target="_blank" rel="noopener noreferrer">` link to Amazon
  - **Empty/failed** (`similarProducts.length === 0`): section hidden entirely
- Card styling: same dark theme as the rest of the page; hover state adds a subtle border highlight

---

## Data Flow

```
User lands on /search/url-analysis?url=...
  │
  ├─► POST /api/analyze-url  (existing, ~30–60s)
  │     └─► Returns product + histogram + analysis (with score) + reviews
  │           └─► Page renders: ScoreCard + ProductHeader + RatingBreakdown + AIAnalysis + FeaturedReviews
  │                 └─► Triggers GET /api/similar-products?asin=...&title=...  (~15–25s)
  │                       └─► Similar Products section: skeleton → cards (or hidden if empty)
```

---

## Files Changed

| File | Change |
|------|--------|
| `backend/llm/analyze.py` | Add `score` to LLM prompt and fallback |
| `backend/main.py` | Add `GET /api/similar-products` endpoint |
| `frontend/lib/types.ts` | Add `score` to `ReviewAnalysis`, add `SimilarProduct` interface |
| `frontend/lib/api.ts` | Add `fetchSimilarProducts()` |
| `frontend/app/search/url-analysis/page.tsx` | Add `ScoreCard`, lazy-load similar products section |
