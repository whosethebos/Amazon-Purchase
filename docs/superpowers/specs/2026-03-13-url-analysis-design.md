# Amazon Product Enhancement — Rating Sort, 10-Product Grid & URL Direct Analysis

**Date:** 2026-03-13
**Status:** Approved (pending spec review)

---

## Overview

Two connected improvements to the Amazon Research Tool:

1. **Confirmation Grid Upgrade** — Sort 10 candidate products by rating (highest first) and display price more prominently.
2. **Amazon URL Direct Analysis** — If the user pastes an Amazon URL into the search bar, bypass the preview/confirm flow and navigate to a dedicated analysis page showing: product header, rating histogram (5★→1★), AI summary, pros/cons, and 3–5 quoted review snippets.

---

## 1. Confirmation Grid Upgrade

### Backend — `backend/scraper/amazon.py`

In the `search_products` function, after collecting all results and before returning, sort by rating descending. Products with no rating sort to the bottom:

```python
results.sort(key=lambda p: p.get("rating") or 0, reverse=True)
```

This sort happens once in `search_products`. `ScraperAgent.fetch_batch` slices from this sorted list. Because each call to `search_products` independently re-sorts, sort order within each batch is consistent. Note: global order across batches is not guaranteed — iteration 2 re-fetches fresh results and re-sorts independently. This is acceptable; the primary goal is to show the highest-rated products first in each batch presented to the user.

Set `AMAZON_BATCH_SIZE=10` in `.env`. This env var already maps to `config.py`'s `amazon_batch_size` field via pydantic-settings — no new config field is needed. `ScraperAgent.fetch_batch` already reads `settings.amazon_batch_size` and passes it to `search_products` as `max_results`. No change to the `search_products` function signature is required — only the `.env` value changes.

### Frontend — `frontend/components/ConfirmationGrid.tsx`

First, add `currency: string | null` to the `Product` type:

```ts
type Product = {
  id: string;
  title: string;
  price: number | null;
  currency: string | null;   // ← add this
  rating: number | null;
  review_count: number | null;
  image_url: string | null;
};
```

Then replace the current price rendering (which appears inline in the flex row alongside rating/review count) with a dedicated block below the product title:

```tsx
{product.price != null && (
  <p className="text-[#f97316] font-bold text-sm mt-1">
    {product.currency ?? "USD"} {product.price.toFixed(2)}
  </p>
)}
```

Remove the `{product.price && <span ...>${product.price}</span>}` element from the existing flex row. Final order: title → price block → rating row.

---

## 2. Amazon URL Direct Analysis Flow

### URL detection — `frontend/app/page.tsx` (`HomeContent`)

On search submit, before any routing:

```ts
// Matches amazon.com /dp/ and /gp/product/ product URLs only
// Requires https?:// prefix; www. is optional
const AMAZON_ASIN_RE = /^https?:\/\/(www\.)?amazon\.com\/(dp|gp\/product)\/([A-Z0-9]{10})/;

const match = query.trim().match(AMAZON_ASIN_RE);
if (match) {
  const asin = match[3];
  router.push(`/search/url-analysis?asin=${asin}&url=${encodeURIComponent(query.trim())}`);
  return;
}
// else → existing flow
```

**Scope note:** Only `amazon.com` is supported. International Amazon domains (`amazon.in`, `amazon.co.uk`, etc.) are out of scope and will fall through to the normal search flow.

### Backend — `backend/models.py`

Add:

```python
class AnalyzeUrlRequest(BaseModel):
    url: str
```

### Backend — new function `scrape_product_details` in `backend/scraper/amazon.py`

This function opens one browser (following the same `async with async_playwright()` pattern used throughout the existing scraper), one page object, and performs two sequential `page.goto()` calls on that same page:

1. **Navigate to the product page** (`url`): extract title, price, currency, overall rating, review count, image URL.
2. **Navigate to the reviews page** (`https://www.amazon.com/product-reviews/{asin}`, using the ASIN already extracted): extract the rating histogram and up to 20 individual reviews.

The same `page` object is reused for both navigations. Close the browser in a `finally` block.

```python
async def scrape_product_details(url: str) -> dict:
    """
    Returns:
    {
      "asin": str,
      "title": str,
      "price": float | None,
      "currency": str | None,
      "rating": float | None,
      "review_count": int | None,
      "image_url": str | None,
      "histogram": {"5": float, "4": float, "3": float, "2": float, "1": float},  # percentages 0-100
      "reviews": [{"stars": int, "author": str, "title": str, "body": str}, ...]  # up to 20
    }
    """
```

**Product page selectors (on the product `/dp/` page, navigation 1):**

```python
# Title
title_el = await page.query_selector("#productTitle")
title = (await title_el.inner_text()).strip() if title_el else ""

# Price (primary offer price)
price_el = await page.query_selector(".a-offscreen")  # first occurrence is the main price
price = None
if price_el:
    raw = (await price_el.inner_text()).strip().replace(",", "")
    try:
        price = float("".join(c for c in raw if c.isdigit() or c == "."))
    except ValueError:
        price = None
currency = "USD"  # amazon.com only

# Overall rating (e.g. "4.3 out of 5 stars")
rating_el = await page.query_selector("[data-hook='rating-out-of-text'], #acrPopover span.a-icon-alt")
rating = None
if rating_el:
    raw = await rating_el.inner_text()
    try:
        rating = float(raw.split()[0])
    except (ValueError, IndexError):
        rating = None

# Review count
review_el = await page.query_selector("#acrCustomerReviewText")
review_count = None
if review_el:
    raw = (await review_el.inner_text()).replace(",", "").split()[0]
    try:
        review_count = int(raw)
    except ValueError:
        review_count = None

# Main product image
img_el = await page.query_selector("#landingImage, [data-hook='main-image-container'] img")
image_url = None
if img_el:
    image_url = await img_el.get_attribute("src")
```

If any selector is not found, use `None` for that field — never raise.

**Histogram selectors (on `/product-reviews/{asin}` page):**

Amazon renders the histogram as percentages (e.g., "62%"), not raw counts. The histogram response stores these as floats (0–100). Update the histogram response contract accordingly (see TypeScript types below).

```python
# Navigate to: https://www.amazon.com/product-reviews/{asin}
rows = await page.query_selector_all("#histogramTable tr")
# rows[0] = 5★, rows[1] = 4★, ..., rows[4] = 1★
# In each row, the percentage is in the last <td> which contains an <a> with text like "62%"
# Use inner_text() on the last <td> element in each row, then strip "%" and convert to float
# Example: "62%" → 62.0

stars_order = [5, 4, 3, 2, 1]
histogram = {"5": 0.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0}
for i, row in enumerate(rows[:5]):
    tds = await row.query_selector_all("td")
    if tds:
        text = await tds[-1].inner_text()
        pct_str = text.strip().replace("%", "")
        try:
            histogram[str(stars_order[i])] = float(pct_str)
        except ValueError:
            pass
```

Fall back to `{"5": 0.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0}` if `#histogramTable` is not found or the page doesn't load.

**Review selectors (on same `/product-reviews/{asin}` page):**
```python
reviews_els = await page.query_selector_all("[data-hook='review']")
# Per review:
# stars: parse int from [data-hook='review-star-rating'] aria-label (e.g. "5.0 out of 5 stars" → 5)
# author: .a-profile-name text
# title: [data-hook='review-title'] span:not(.a-icon-alt) text  ← same selector as existing scrape_product_reviews
# body: [data-hook='review-body'] span text
```
Collect up to 20 reviews. If any field is missing, use empty string / 0 — never raise.

**ASIN extraction (for building the reviews URL):**
```python
asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
asin = asin_match.group(1) if asin_match else None
```

**Currency:** Always `"USD"` (only `amazon.com` is supported).

### Backend — new endpoint in `backend/main.py`

Add this import at the **top of `main.py`** alongside existing imports (not inside a function):

```python
from llm.ollama_client import chat_json
```

`from fastapi.responses import JSONResponse` is also required as a top-level import.

```python
from fastapi.responses import JSONResponse

@app.post("/api/analyze-url")
async def analyze_url(req: AnalyzeUrlRequest):
    """Scrape and LLM-analyze a single Amazon product URL. 60-second timeout."""
    try:
        async with asyncio.timeout(60):
            # Step 1: Extract ASIN
            asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", req.url)
            if not asin_match:
                return JSONResponse(status_code=422, content={"error": "Could not extract ASIN from URL"})
            asin = asin_match.group(1)

            # Step 2: Scrape product + histogram + reviews
            product_data = await scrape_product_details(req.url)

            # Step 3: LLM analysis
            reviews = product_data["reviews"]
            analysis = await run_llm_analysis(product_data["title"], reviews)

            # Step 4: Validate and clamp featured_review_indices
            valid_indices = [i for i in analysis.get("featured_review_indices", []) if 0 <= i < len(reviews)]
            if not valid_indices and reviews:
                valid_indices = [0]
            analysis["featured_review_indices"] = valid_indices

            return {
                "product": {k: product_data[k] for k in ("asin", "title", "price", "currency", "rating", "review_count", "image_url")},
                "histogram": product_data["histogram"],
                "analysis": analysis,
                "reviews": reviews,
            }
    except asyncio.TimeoutError:
        return JSONResponse(status_code=500, content={"error": "Analysis timed out after 60 seconds"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
```

**LLM helper `run_llm_analysis(title, reviews) -> dict`:**

```python
import json
from llm.ollama_client import chat_json

FALLBACK = {"summary": "", "pros": [], "cons": [], "featured_review_indices": []}

async def run_llm_analysis(title: str, reviews: list[dict]) -> dict:
    formatted = "\n\n".join(
        f"[{i}] {r['stars']}★ — {r['title']}\n{r['body']}"
        for i, r in enumerate(reviews)
    )
    prompt = f"""You are analyzing customer reviews for an Amazon product.

Product: {title}

Reviews (indexed 0 to {len(reviews) - 1}):
{formatted or "(no reviews available)"}

Respond ONLY with valid JSON in this exact shape:
{{
  "summary": "<2-3 sentence overview>",
  "pros": ["<specific pro>", ...],
  "cons": ["<specific con>", ...],
  "featured_review_indices": [<3-5 indices from 0 to {len(reviews) - 1} — pick substantive reviews covering both praise and criticism; return [] if no reviews>]
}}

Rules:
- pros and cons: 3-5 items each, grounded in the review text
- featured_review_indices: valid 0-based indices only
- Return only the JSON object, no other text"""

    try:
        return await chat_json([{"role": "user", "content": prompt}])
    except Exception:
        return FALLBACK
```

`chat_json` uses `httpx.AsyncClient(timeout=120.0)` internally. The 60-second `asyncio.timeout` on the outer endpoint will interrupt the coroutine at the next asyncio cancellation checkpoint. Because `httpx` is a fully async library, `asyncio.TimeoutError` will propagate correctly and the `TimeoutError` handler in the endpoint will fire. Accept this as best-effort: the backend responds with a timeout error; the httpx connection may briefly continue in the background before the event loop collects it.

**All error responses** use `JSONResponse(status_code=..., content={"error": "..."})` — never `HTTPException`, which would produce FastAPI's `{"detail": ...}` envelope.

### Frontend — TypeScript types in `frontend/lib/types.ts` (create if not present)

```ts
export interface ProductInfo {
  asin: string;
  title: string;
  price: number | null;
  currency: string | null;
  rating: number | null;
  review_count: number | null;
  image_url: string | null;
}

/** Percentage values (0–100) for each star level, scraped from Amazon's review histogram. */
export interface Histogram {
  "1": number;
  "2": number;
  "3": number;
  "4": number;
  "5": number;
}

export interface ReviewAnalysis {
  summary: string;
  pros: string[];
  cons: string[];
  featured_review_indices: number[];
}

export interface Review {
  stars: number;
  author: string;
  title: string;
  body: string;
}

export interface AnalyzeUrlResponse {
  product: ProductInfo;
  histogram: Histogram;
  analysis: ReviewAnalysis;
  reviews: Review[];
}
```

### Frontend — API helper in `frontend/lib/api.ts`

```ts
import type { AnalyzeUrlResponse } from "./types";

export async function analyzeUrl(url: string, signal?: AbortSignal): Promise<AnalyzeUrlResponse> {
  const res = await fetch(`${API_URL}/api/analyze-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Unknown error" }));
    throw new Error(err.error ?? "Request failed");
  }
  return res.json();
}
```

### Frontend — new page `frontend/app/search/url-analysis/page.tsx`

**Directory structure note:** Create this file at `frontend/app/search/url-analysis/page.tsx`. This directory must be a **sibling** of `frontend/app/search/[id]/`, not nested inside it. Next.js App Router gives static segments priority over dynamic segments at the same level, so `/search/url-analysis` will route correctly to this page rather than being captured by `[id]`.

Export a Suspense shell as the default export:

```tsx
export default function UrlAnalysisPage() {
  return (
    <Suspense fallback={null}>
      <UrlAnalysisContent />
    </Suspense>
  );
}
```

`UrlAnalysisContent` behavior:
- Reads `asin` and `url` from `useSearchParams()`. Both are `string | null`.
- **If `url` is null:** reconstruct as `https://www.amazon.com/dp/${asin}` and use that. If `asin` is also null, set error state immediately with message "Invalid product URL" and do not fetch.
- On mount, calls `analyzeUrl(resolvedUrl, abortController.signal)` where `resolvedUrl: string`. Cleanup: call `abortController.abort()` on unmount.
- Loading state: centered spinner + "Analyzing product…" text (no skeleton, just a spinner).
- Error state: red error message + `<Link href="/">← Try again</Link>`.
- Success: render four sections (A–D below).

**Section A — Product header**

Left: product image (`<img>` 120×120 `object-contain`, fall back to placeholder div if `image_url` is null).
Right column:
- Title (`text-lg font-semibold text-[#ebebf5]`)
- Price: `{product.price != null ? <span className="text-[#f97316] font-bold text-xl">{product.currency ?? "USD"} {product.price.toFixed(2)}</span> : null}`
- Overall rating + review count (`text-[#9898b8] text-sm`)
- CamelCamelCamel link: `https://camelcamelcamel.com/product/{asin}` (`text-[#818cf8] text-xs underline`)

**Section B — Rating Breakdown**

Heading: `"Rating Breakdown"` (`text-[#ebebf5] font-semibold mb-3`)

For star levels `[5, 4, 3, 2, 1]`:
```tsx
// histogram values are already percentages (0-100 floats) — use directly as bar width
// For each star level:
const pct = histogram[`${star}` as keyof Histogram]; // e.g. 62.0
const barWidth = pct.toFixed(1) + "%";
const barClass = star >= 4 ? "bg-emerald-400" : star === 3 ? "bg-yellow-400" : "bg-red-400";
```

Row layout: `{star}★` label (w-8) + bar container (flex-1, h-2, bg-[#1a1a2e]) with filled div (`style={{ width: barWidth }}` + `barClass`) + percentage label (`{pct.toFixed(0)}%`, w-12 text-right `text-[#9898b8] text-xs`).

**Section C — AI Analysis**

Heading: `"AI Analysis"`

- Summary: `<p className="text-[#9898b8] text-sm">{analysis.summary}</p>`
- Pros heading: `"Pros"` (emerald)
- Pros list: each item prefixed with `✓` in `text-emerald-400`
- Cons heading: `"Cons"` (red)
- Cons list: each item prefixed with `✗` in `text-red-400`

**Section D — Featured Reviews**

Heading: `"Featured Reviews"`

Render `analysis.featured_review_indices.map(idx => reviews[idx]).filter(Boolean)`.

Each review is rendered by a `ReviewCard` sub-component defined in the same file:

```tsx
function ReviewCard({ review }: { review: Review }) {
  const [expanded, setExpanded] = useState(false);
  const TRUNCATE = 300;
  const isLong = review.body.length > TRUNCATE;
  const displayed = expanded ? review.body : review.body.slice(0, TRUNCATE);

  return (
    <div className="rounded-lg bg-[#1a1a2e] border border-[#2a2a45] p-4 mb-3">
      {/* Star row: filled ★ for review.stars, empty ☆ for the rest, orange color */}
      <div className="text-[#f97316] text-sm mb-1">
        {"★".repeat(review.stars)}{"☆".repeat(5 - review.stars)}
      </div>
      <p className="text-[#ebebf5] font-semibold text-sm">{review.author} — {review.title}</p>
      <p className="text-[#9898b8] text-sm mt-1">
        {displayed}{isLong && !expanded ? "…" : ""}
      </p>
      {isLong && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-[#818cf8] text-xs mt-1 underline"
        >
          {expanded ? "show less" : "show more"}
        </button>
      )}
    </div>
  );
}
```

**Navigation:** `<Link href="/" className="text-[#818cf8] text-sm">← New Search</Link>` at top-left of page.

No `StepIndicator` — this is a standalone flow.

---

## Styling

All new UI follows the existing Refined Dark palette:
- Backgrounds: `#07070d` / `#0f0f1a`
- Cards: `bg-[#1a1a2e] border border-[#2a2a45]`
- Accent orange: `#f97316`
- Accent indigo: `#818cf8`
- Text primary: `#ebebf5`, secondary: `#9898b8`

---

## Out of Scope

- No SSE/streaming for URL analysis.
- No saving URL analysis results to the watchlist database.
- Only `amazon.com` URLs are supported. Other Amazon domains fall through to the normal search flow.
- Non-product Amazon URLs (category pages, search results pages) are not supported.
