# URL Analysis & Confirmation Grid Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sort Amazon search results by rating, increase batch size to 10, and add a URL-paste flow that scrapes + LLM-analyzes a specific Amazon product directly.

**Architecture:** Backend gains `_extract_asin` and `scrape_product_details` in `scraper/amazon.py`, a `run_llm_analysis` helper in a new `llm/analyze.py` module (for testability), and a `POST /api/analyze-url` endpoint in `main.py`. Frontend gains URL detection on the home page, TypeScript types, and a new `/search/url-analysis` page.

**Tech Stack:** Python 3.13, FastAPI, Playwright, Ollama (`chat_json`), pytest + pytest-asyncio, Next.js 14 App Router, TypeScript, Tailwind CSS.

**Spec:** `docs/superpowers/specs/2026-03-13-url-analysis-design.md`

---

## File Map

**Modified:**
- `backend/requirements.txt` — add `pytest>=8.0`, `pytest-asyncio>=0.24`
- `backend/.env` — bump `AMAZON_BATCH_SIZE` from 5 to 10 (local change, do NOT commit — `.env` is gitignored)
- `backend/scraper/amazon.py` — add `_extract_asin` helper, `_sort_products_by_rating` helper, call sort in `search_products`, add `scrape_product_details`
- `backend/models.py` — add `AnalyzeUrlRequest`
- `backend/main.py` — add imports, import `run_llm_analysis` from `llm.analyze`, add `POST /api/analyze-url` endpoint
- `frontend/lib/api.ts` — add `analyzeUrl` function
- `frontend/components/ConfirmationGrid.tsx` — add `currency` to `Product` type; redesign price display
- `frontend/app/page.tsx` — add URL detection in `handleSearch`

**Created:**
- `backend/pytest.ini` — pytest + asyncio configuration
- `backend/tests/__init__.py` — empty, makes `tests/` a package
- `backend/tests/test_analyze_url.py` — unit tests for pure logic
- `backend/llm/analyze.py` — `run_llm_analysis` helper (isolated from FastAPI for testability)
- `frontend/lib/types.ts` — `AnalyzeUrlResponse` and related interfaces
- `frontend/app/search/url-analysis/page.tsx` — new standalone analysis page

---

## Chunk 1: Backend Changes

### Task 1: Test infrastructure + sort products by rating + bump batch size

**Files:**
- Create: `backend/pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_analyze_url.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/scraper/amazon.py`
- Modify: `backend/.env` (local only, do not commit)

**Context:** The project has no tests yet. We set up pytest before writing any test code. `backend/.env` is in `.gitignore` — do not `git add` it.

- [ ] **Step 1: Add pytest dependencies to `requirements.txt`**

In `backend/requirements.txt`, append two lines:

```
pytest>=8.0
pytest-asyncio>=0.24
```

- [ ] **Step 2: Install the new dependencies**

```bash
cd backend && uv pip install -r requirements.txt
```

Expected: uv installs `pytest` and `pytest-asyncio` (and any other deps in requirements.txt).

- [ ] **Step 3: Create `backend/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
```

The `pythonpath = .` line tells pytest that `backend/` is the source root, so imports like `from scraper.amazon import ...` resolve correctly without a `src/` layout.

This tells `pytest-asyncio` to automatically handle `async def test_*` functions without needing `@pytest.mark.asyncio` on each one.

- [ ] **Step 4: Create `backend/tests/__init__.py`**

Create an empty file at `backend/tests/__init__.py`:

```python
```

(Empty file — just makes `tests/` a Python package so imports work.)

- [ ] **Step 5: Write failing tests for `_sort_products_by_rating` and `_extract_asin`**

Create `backend/tests/test_analyze_url.py`:

```python
# backend/tests/test_analyze_url.py
import pytest
from scraper.amazon import _sort_products_by_rating, _extract_asin


# ── _sort_products_by_rating ────────────────────────────────────────────────────

def test_sort_by_rating_descending():
    products = [
        {"asin": "A1", "rating": 3.2},
        {"asin": "A2", "rating": 4.8},
        {"asin": "A3", "rating": None},
        {"asin": "A4", "rating": 4.1},
    ]
    result = _sort_products_by_rating(products)
    assert [p["asin"] for p in result] == ["A2", "A4", "A1", "A3"]


def test_sort_empty_list():
    assert _sort_products_by_rating([]) == []


def test_sort_all_none_ratings():
    products = [{"asin": "A1", "rating": None}, {"asin": "A2", "rating": None}]
    result = _sort_products_by_rating(products)
    assert len(result) == 2  # order unspecified, just no crash


# ── _extract_asin ───────────────────────────────────────────────────────────────

def test_extract_asin_dp_url():
    assert _extract_asin("https://www.amazon.com/dp/B0XXXXXXXX") == "B0XXXXXXXX"


def test_extract_asin_gp_url():
    assert _extract_asin("https://www.amazon.com/gp/product/B012345678") == "B012345678"


def test_extract_asin_with_title_slug():
    assert _extract_asin(
        "https://www.amazon.com/Some-Product-Name/dp/B0ABCDE123"
    ) == "B0ABCDE123"


def test_extract_asin_no_match():
    assert _extract_asin("https://www.amazon.com/s?k=laptop") is None


def test_extract_asin_no_trailing_slash_required():
    assert _extract_asin("https://www.amazon.com/dp/B0XXXXXXXX/ref=...") == "B0XXXXXXXX"
```

- [ ] **Step 6: Run tests — expect failure because helpers don't exist yet**

```bash
cd backend && uv run pytest tests/test_analyze_url.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name '_sort_products_by_rating' from 'scraper.amazon'`

- [ ] **Step 7: Add `_extract_asin` and `_sort_products_by_rating` helpers to `backend/scraper/amazon.py`**

Insert the two helpers just before `async def search_products` (after line 4, after the existing imports). Currently line 4–5 is:

```python
from config import settings


async def search_products(query: str, max_results: int = 10) -> list[dict]:
```

Change to:

```python
from config import settings
import re as _re


def _extract_asin(url: str) -> str | None:
    """Extract ASIN from an Amazon product URL. Returns None if not found."""
    m = _re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
    return m.group(1) if m else None


def _sort_products_by_rating(products: list[dict]) -> list[dict]:
    """Sort products by rating descending; products with no rating sort last."""
    return sorted(products, key=lambda p: p.get("rating") or 0, reverse=True)


async def search_products(query: str, max_results: int = 10) -> list[dict]:
```

Also update the `return products` statement at the end of `search_products` (currently line 109 — it is the last line of the function before the `finally` block). Replace:

```python
            return products
```

with:

```python
            return _sort_products_by_rating(products)
```

**Note:** There is already an `import re` inside the `for` loop in `search_products` (line 56). Leave that inner import as-is — it's redundant but harmless. The new `import re as _re` at module level provides ASIN extraction.

- [ ] **Step 8: Run tests — expect all to pass**

```bash
cd backend && uv run pytest tests/test_analyze_url.py -v 2>&1
```

Expected: 8 PASSED

- [ ] **Step 9: Update `AMAZON_BATCH_SIZE` in your local `.env` (do NOT commit)**

In `backend/.env`, change:
```
AMAZON_BATCH_SIZE=5
```
to:
```
AMAZON_BATCH_SIZE=10
```

**Do not `git add .env`** — it is gitignored and contains credentials.

- [ ] **Step 10: Commit**

```bash
git add backend/requirements.txt backend/pytest.ini backend/tests/__init__.py backend/tests/test_analyze_url.py backend/scraper/amazon.py
git commit -m "feat: sort search results by rating desc; add test infrastructure; bump batch size to 10"
```

---

### Task 2: Update ConfirmationGrid price display

**Files:**
- Modify: `frontend/components/ConfirmationGrid.tsx`

- [ ] **Step 1: Add `currency` to the `Product` type**

In `frontend/components/ConfirmationGrid.tsx`, find and replace the existing `Product` type:

Old:
```ts
type Product = {
  id: string;
  title: string;
  price: number | null;
  rating: number | null;
  review_count: number | null;
  image_url: string | null;
};
```

New:
```ts
type Product = {
  id: string;
  title: string;
  price: number | null;
  currency: string | null;
  rating: number | null;
  review_count: number | null;
  image_url: string | null;
};
```

- [ ] **Step 2: Redesign price rendering**

Find and replace the div that shows price/rating/review_count inline:

Old:
```tsx
            <div className="mt-1 flex items-center gap-2 text-xs text-[#7878a0]">
              {product.price && <span className="font-semibold text-[#ebebf5] font-mono">${product.price}</span>}
              {product.rating && <span className="text-amber-400">★ {product.rating}</span>}
              {product.review_count && <span>({product.review_count.toLocaleString()})</span>}
            </div>
```

New (price on its own line, rating/review_count in the flex row):
```tsx
            {product.price != null && (
              <p className="text-[#f97316] font-bold text-sm mt-1">
                {product.currency ?? "USD"} {product.price.toFixed(2)}
              </p>
            )}
            <div className="mt-1 flex items-center gap-2 text-xs text-[#7878a0]">
              {product.rating && <span className="text-amber-400">★ {product.rating}</span>}
              {product.review_count && <span>({product.review_count.toLocaleString()})</span>}
            </div>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors from `ConfirmationGrid.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ConfirmationGrid.tsx
git commit -m "feat: display price prominently in orange below product title in confirmation grid"
```

---

### Task 3: Add `scrape_product_details` to `amazon.py`

**Files:**
- Modify: `backend/scraper/amazon.py` (add new function after `scrape_current_price`)

- [ ] **Step 1: Append `scrape_product_details` to `backend/scraper/amazon.py`**

Append after the last line of the file (after `scrape_current_price`'s closing `finally` block at line 201):

```python

async def scrape_product_details(url: str) -> dict:
    """
    Scrape a product detail page + its reviews page for full single-product analysis.

    Uses a single browser session with two sequential page.goto() calls:
    1. Product /dp/ page — title, price, rating, review count, image
    2. /product-reviews/{asin} page — rating histogram + up to 20 reviews

    Returns:
    {
      "asin": str,
      "title": str,
      "price": float | None,
      "currency": str | None,       # always "USD" (only amazon.com supported)
      "rating": float | None,
      "review_count": int | None,
      "image_url": str | None,
      "histogram": {"5": float, "4": float, "3": float, "2": float, "1": float},
      "reviews": [{"stars": int, "author": str, "title": str, "body": str}, ...]
    }
    """
    asin = _extract_asin(url) or ""
    empty_histogram = {"5": 0.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0}

    async with async_playwright() as playwright:
        browser, page = await _get_page(playwright)
        try:
            # ── Navigation 1: product page ──────────────────────────────────────
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Title
            title_el = await page.query_selector("#productTitle")
            title = (await title_el.inner_text()).strip() if title_el else ""

            # Price
            price = None
            price_el = await page.query_selector(".a-offscreen")
            if price_el:
                raw = (await price_el.inner_text()).strip().replace(",", "")
                try:
                    price = float("".join(c for c in raw if c.isdigit() or c == "."))
                except ValueError:
                    pass

            currency = "USD"

            # Rating (e.g. "4.3 out of 5 stars")
            rating = None
            rating_el = await page.query_selector(
                "[data-hook='rating-out-of-text'], #acrPopover span.a-icon-alt"
            )
            if rating_el:
                try:
                    rating = float((await rating_el.inner_text()).split()[0])
                except (ValueError, IndexError):
                    pass

            # Review count
            review_count = None
            rc_el = await page.query_selector("#acrCustomerReviewText")
            if rc_el:
                try:
                    review_count = int(
                        (await rc_el.inner_text()).replace(",", "").split()[0]
                    )
                except (ValueError, IndexError):
                    pass

            # Main image
            image_url = None
            img_el = await page.query_selector(
                "#landingImage, [data-hook='main-image-container'] img"
            )
            if img_el:
                image_url = await img_el.get_attribute("src")

            # ── Navigation 2: reviews page ──────────────────────────────────────
            histogram = dict(empty_histogram)
            reviews: list[dict] = []

            if asin:
                await page.goto(
                    f"https://www.amazon.com/product-reviews/{asin}",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await asyncio.sleep(2)

                # Histogram percentages: #histogramTable rows[0]=5★ ... rows[4]=1★
                stars_order = [5, 4, 3, 2, 1]
                rows = await page.query_selector_all("#histogramTable tr")
                for i, row in enumerate(rows[:5]):
                    tds = await row.query_selector_all("td")
                    if tds:
                        try:
                            text = await tds[-1].inner_text()
                            histogram[str(stars_order[i])] = float(
                                text.strip().replace("%", "").strip()
                            )
                        except (ValueError, IndexError):
                            pass

                # Reviews (up to 20)
                review_els = await page.query_selector_all("[data-hook='review']")
                for el in review_els[:20]:
                    try:
                        stars = 0
                        star_el = await el.query_selector(
                            "[data-hook='review-star-rating'] .a-icon-alt"
                        )
                        if star_el:
                            stars = int(float((await star_el.inner_text()).split()[0]))

                        author_el = await el.query_selector(".a-profile-name")
                        author = (await author_el.inner_text()).strip() if author_el else ""

                        title_el_r = await el.query_selector(
                            "[data-hook='review-title'] span:not(.a-icon-alt)"
                        )
                        review_title = (
                            (await title_el_r.inner_text()).strip() if title_el_r else ""
                        )

                        body_el = await el.query_selector("[data-hook='review-body'] span")
                        body = (await body_el.inner_text()).strip() if body_el else ""

                        reviews.append(
                            {"stars": stars, "author": author, "title": review_title, "body": body}
                        )
                    except Exception:
                        continue

            return {
                "asin": asin,
                "title": title,
                "price": price,
                "currency": currency,
                "rating": rating,
                "review_count": review_count,
                "image_url": image_url,
                "histogram": histogram,
                "reviews": reviews,
            }
        finally:
            await browser.close()
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
cd backend && uv run python -c "from scraper.amazon import scrape_product_details, _extract_asin, _sort_products_by_rating; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/scraper/amazon.py
git commit -m "feat: add scrape_product_details for full product + review page scraping"
```

---

### Task 4: Create `llm/analyze.py` with `run_llm_analysis`

**Files:**
- Create: `backend/llm/analyze.py`
- Modify: `backend/tests/test_analyze_url.py`

**Why a separate file?** Keeping `run_llm_analysis` out of `main.py` lets us import it in unit tests without pulling in FastAPI + the database pool, which require environment variables and a running database. The existing `backend/llm/` directory already contains `ollama_client.py`.

- [ ] **Step 1: Write a failing test for the LLM fallback behavior**

Append to `backend/tests/test_analyze_url.py`:

```python
from unittest.mock import AsyncMock, patch
from llm.analyze import run_llm_analysis, _LLM_FALLBACK


# ── run_llm_analysis ────────────────────────────────────────────────────────────

async def test_run_llm_analysis_fallback_on_exception():
    """When chat_json raises, run_llm_analysis returns the empty fallback."""
    with patch("llm.analyze.chat_json", new=AsyncMock(side_effect=Exception("LLM down"))):
        result = await run_llm_analysis("Test Product", [])
    assert result == _LLM_FALLBACK


async def test_run_llm_analysis_fallback_on_json_decode_error():
    """When chat_json raises JSONDecodeError, run_llm_analysis returns fallback."""
    import json
    with patch("llm.analyze.chat_json", new=AsyncMock(side_effect=json.JSONDecodeError("bad", "", 0))):
        result = await run_llm_analysis("Test Product", [{"stars": 5, "title": "Good", "body": "Nice"}])
    assert result == _LLM_FALLBACK
```

- [ ] **Step 2: Run — expect failure because `llm.analyze` doesn't exist**

```bash
cd backend && uv run pytest tests/test_analyze_url.py -v -k "llm" 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'llm.analyze'`

- [ ] **Step 3: Create `backend/llm/analyze.py`**

```python
# backend/llm/analyze.py
"""LLM analysis helper — isolated from FastAPI for testability."""
from llm.ollama_client import chat_json

_LLM_FALLBACK: dict = {
    "summary": "",
    "pros": [],
    "cons": [],
    "featured_review_indices": [],
}


async def run_llm_analysis(title: str, reviews: list[dict]) -> dict:
    """
    Call Ollama to summarize product reviews and pick representative ones.
    Returns _LLM_FALLBACK on any error.
    """
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
        return _LLM_FALLBACK
```

- [ ] **Step 4: Run the LLM fallback tests — expect both to pass**

```bash
cd backend && uv run pytest tests/test_analyze_url.py -v -k "llm" 2>&1
```

Expected: 2 PASSED

- [ ] **Step 5: Run all backend tests**

```bash
cd backend && uv run pytest tests/test_analyze_url.py -v 2>&1
```

Expected: 10 PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/llm/analyze.py backend/tests/test_analyze_url.py
git commit -m "feat: add run_llm_analysis in llm/analyze.py with fallback handling"
```

---

### Task 5: Add `AnalyzeUrlRequest` model and `POST /api/analyze-url` endpoint

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Add `AnalyzeUrlRequest` to `backend/models.py`**

Append at the end of `backend/models.py` (after the last class, currently `SSEEvent`):

```python
class AnalyzeUrlRequest(BaseModel):
    url: str
```

- [ ] **Step 2: Update imports in `backend/main.py`**

Update the existing imports. Find:

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from models import SearchRequest, ConfirmationRequest
```

Replace with:

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from models import SearchRequest, ConfirmationRequest, AnalyzeUrlRequest
```

Also update the scraper import. Find:

```python
from scraper.amazon import scrape_current_price
```

Replace with:

```python
from scraper.amazon import scrape_current_price, scrape_product_details
```

Also add the new analyzer import alongside the existing agent/db imports:

```python
from llm.analyze import run_llm_analysis
```

(Add this after the `from config import settings` line.)

- [ ] **Step 3: Add the `POST /api/analyze-url` endpoint to `backend/main.py`**

Append after the `get_preview_images` endpoint (after its closing `}`). The new endpoint goes between the preview images endpoint and the `# --- Search history ---` comment:

```python
@app.post("/api/analyze-url")
async def analyze_url(req: AnalyzeUrlRequest):
    """Scrape and LLM-analyze a single Amazon product URL. 60-second best-effort timeout."""
    try:
        async with asyncio.timeout(60):
            asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", req.url)
            if not asin_match:
                return JSONResponse(
                    status_code=422,
                    content={"error": "Could not extract ASIN from URL"},
                )
            asin = asin_match.group(1)

            product_data = await scrape_product_details(req.url)
            reviews = product_data["reviews"]
            analysis = await run_llm_analysis(product_data["title"], reviews)

            valid_indices = [
                i for i in analysis.get("featured_review_indices", [])
                if 0 <= i < len(reviews)
            ]
            if not valid_indices and reviews:
                valid_indices = [0]
            analysis["featured_review_indices"] = valid_indices

            return {
                "product": {
                    k: product_data[k]
                    for k in ("asin", "title", "price", "currency", "rating", "review_count", "image_url")
                },
                "histogram": product_data["histogram"],
                "analysis": analysis,
                "reviews": reviews,
            }
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=500,
            content={"error": "Analysis timed out after 60 seconds"},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
```

- [ ] **Step 4: Verify the backend imports cleanly**

```bash
cd backend && uv run python -c "import main; print('OK')"
```

Expected: `OK` (no import errors)

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/main.py
git commit -m "feat: add POST /api/analyze-url endpoint"
```

---

## Chunk 2: Frontend Changes

### Task 6: Create TypeScript types and `analyzeUrl` API function

**Files:**
- Create: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Create `frontend/lib/types.ts`**

```ts
// frontend/lib/types.ts

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

- [ ] **Step 2: Add import and `analyzeUrl` to `frontend/lib/api.ts`**

At the top of `frontend/lib/api.ts`, add the import after the existing `import { API_URL } from "./config";` line:

```ts
import type { AnalyzeUrlResponse } from "./types";
```

Append at the end of `frontend/lib/api.ts`:

```ts
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

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no new errors from `types.ts` or `api.ts`.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat: add AnalyzeUrlResponse types and analyzeUrl API function"
```

---

### Task 7: Add URL detection to home page

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Replace `handleSearch` with URL-aware version**

In `frontend/app/page.tsx`, find and replace `handleSearch`:

Old:
```ts
  const handleSearch = (query: string) => {
    setBaymaxState("searching");
    router.push(`/search/preview?q=${encodeURIComponent(query)}`);
  };
```

New:
```ts
  const AMAZON_ASIN_RE = /^https?:\/\/(www\.)?amazon\.com\/(dp|gp\/product)\/([A-Z0-9]{10})/;

  const handleSearch = (query: string) => {
    setBaymaxState("searching");
    const match = query.trim().match(AMAZON_ASIN_RE);
    if (match) {
      const asin = match[3];
      router.push(`/search/url-analysis?asin=${asin}&url=${encodeURIComponent(query.trim())}`);
      return;
    }
    router.push(`/search/preview?q=${encodeURIComponent(query)}`);
  };
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors from `page.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: detect Amazon product URLs in search bar and route to analysis page"
```

---

### Task 8: Create the URL analysis page

**Files:**
- Create: `frontend/app/search/url-analysis/page.tsx`

**Critical directory note:** Create this at `frontend/app/search/url-analysis/page.tsx` — a sibling of `frontend/app/search/[id]/`, NOT inside it. Next.js App Router gives static route segments priority over dynamic ones at the same level, so `/search/url-analysis` routes here correctly.

Verify the directory structure before starting:

```bash
ls frontend/app/search/
```

You should see `[id]/` and `preview/` directories. `url-analysis/` will be added at the same level.

- [ ] **Step 1: Create the directory and page file**

```bash
mkdir -p frontend/app/search/url-analysis
```

Create `frontend/app/search/url-analysis/page.tsx`:

```tsx
"use client";
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { analyzeUrl } from "@/lib/api";
import type { AnalyzeUrlResponse, Histogram, Review } from "@/lib/types";

// ─── ReviewCard ────────────────────────────────────────────────────────────────

function ReviewCard({ review }: { review: Review }) {
  const [expanded, setExpanded] = useState(false);
  const TRUNCATE = 300;
  const isLong = review.body.length > TRUNCATE;
  const displayed = expanded ? review.body : review.body.slice(0, TRUNCATE);

  return (
    <div className="rounded-lg bg-[#1a1a2e] border border-[#2a2a45] p-4 mb-3">
      <div className="text-[#f97316] text-sm mb-1">
        {"★".repeat(review.stars)}{"☆".repeat(Math.max(0, 5 - review.stars))}
      </div>
      <p className="text-[#ebebf5] font-semibold text-sm">
        {review.author} — {review.title}
      </p>
      <p className="text-[#9898b8] text-sm mt-1">
        {displayed}{isLong && !expanded ? "…" : ""}
      </p>
      {isLong && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="text-[#818cf8] text-xs mt-1 underline"
        >
          {expanded ? "show less" : "show more"}
        </button>
      )}
    </div>
  );
}

// ─── HistogramBar ──────────────────────────────────────────────────────────────

function HistogramBar({ star, pct }: { star: number; pct: number }) {
  const barClass =
    star >= 4 ? "bg-emerald-400" : star === 3 ? "bg-yellow-400" : "bg-red-400";

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-8 text-[#9898b8] text-xs shrink-0">{star}★</span>
      <div className="flex-1 h-2 bg-[#1a1a2e] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${barClass}`}
          style={{ width: `${pct.toFixed(1)}%` }}
        />
      </div>
      <span className="w-12 text-right text-[#9898b8] text-xs shrink-0">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

// ─── UrlAnalysisContent ────────────────────────────────────────────────────────

function UrlAnalysisContent() {
  const searchParams = useSearchParams();
  const asin = searchParams.get("asin");
  const urlParam = searchParams.get("url");
  const resolvedUrl = urlParam ?? (asin ? `https://www.amazon.com/dp/${asin}` : null);

  const [data, setData] = useState<AnalyzeUrlResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!resolvedUrl) {
      setError("Invalid product URL");
      return;
    }

    const controller = new AbortController();

    analyzeUrl(resolvedUrl, controller.signal)
      .then(setData)
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Analysis failed");
      });

    return () => controller.abort();
  }, [resolvedUrl]);

  // ── Loading ──
  if (!data && !error) {
    return (
      <main className="min-h-screen bg-[#07070d] flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-2 border-[#f97316] border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-[#9898b8] text-sm">Analyzing product…</p>
        </div>
      </main>
    );
  }

  // ── Error ──
  if (error) {
    return (
      <main className="min-h-screen bg-[#07070d] flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-red-400 text-sm">{error}</p>
          <Link href="/" className="text-[#818cf8] text-sm underline">
            ← Try again
          </Link>
        </div>
      </main>
    );
  }

  const { product, histogram, analysis, reviews } = data!;
  const featuredReviews = analysis.featured_review_indices
    .map((idx) => reviews[idx])
    .filter(Boolean) as Review[];

  return (
    <main className="min-h-screen bg-[#07070d]">
      <div className="max-w-2xl mx-auto px-4 py-10 space-y-8">

        {/* Back link */}
        <Link href="/" className="text-[#818cf8] text-sm hover:text-indigo-300 transition-colors">
          ← New Search
        </Link>

        {/* Section A — Product Header */}
        <div className="flex gap-4 items-start bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-5">
          {product.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={product.image_url}
              alt={product.title}
              width={120}
              height={120}
              className="object-contain rounded-lg shrink-0"
            />
          ) : (
            <div className="w-[120px] h-[120px] bg-[#1a1a2e] rounded-lg shrink-0" />
          )}
          <div className="space-y-1 min-w-0">
            <p className="text-lg font-semibold text-[#ebebf5] leading-snug">{product.title}</p>
            {product.price != null && (
              <p className="text-[#f97316] font-bold text-xl">
                {product.currency ?? "USD"} {product.price.toFixed(2)}
              </p>
            )}
            {product.rating != null && (
              <p className="text-[#9898b8] text-sm">
                ★ {product.rating.toFixed(1)}{" "}
                {product.review_count != null && (
                  <span>({product.review_count.toLocaleString()} reviews)</span>
                )}
              </p>
            )}
            {asin && (
              <a
                href={`https://camelcamelcamel.com/product/${asin}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#818cf8] text-xs underline hover:text-indigo-300"
              >
                Price history ↗
              </a>
            )}
          </div>
        </div>

        {/* Section B — Rating Breakdown */}
        <div className="bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-5 space-y-3">
          <h2 className="text-[#ebebf5] font-semibold mb-3">Rating Breakdown</h2>
          {([5, 4, 3, 2, 1] as const).map((star) => (
            <HistogramBar
              key={star}
              star={star}
              pct={histogram[`${star}` as keyof Histogram]}
            />
          ))}
        </div>

        {/* Section C — AI Analysis */}
        <div className="bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-5 space-y-4">
          <h2 className="text-[#ebebf5] font-semibold">AI Analysis</h2>
          {analysis.summary && (
            <p className="text-[#9898b8] text-sm leading-relaxed">{analysis.summary}</p>
          )}
          {analysis.pros.length > 0 && (
            <div>
              <p className="text-emerald-400 text-xs font-bold uppercase tracking-wider mb-2">Pros</p>
              <ul className="space-y-1">
                {analysis.pros.map((pro, i) => (
                  <li key={i} className="flex gap-2 text-sm text-[#9898b8]">
                    <span className="text-emerald-400 shrink-0">✓</span>
                    {pro}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {analysis.cons.length > 0 && (
            <div>
              <p className="text-red-400 text-xs font-bold uppercase tracking-wider mb-2">Cons</p>
              <ul className="space-y-1">
                {analysis.cons.map((con, i) => (
                  <li key={i} className="flex gap-2 text-sm text-[#9898b8]">
                    <span className="text-red-400 shrink-0">✗</span>
                    {con}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Section D — Featured Reviews */}
        {featuredReviews.length > 0 && (
          <div>
            <h2 className="text-[#ebebf5] font-semibold mb-3">Featured Reviews</h2>
            {featuredReviews.map((review, i) => (
              <ReviewCard key={i} review={review} />
            ))}
          </div>
        )}

      </div>
    </main>
  );
}

// ─── Page (Suspense shell) ─────────────────────────────────────────────────────

export default function UrlAnalysisPage() {
  return (
    <Suspense fallback={null}>
      <UrlAnalysisContent />
    </Suspense>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```

Expected: no errors from `url-analysis/page.tsx`.

- [ ] **Step 3: Verify the route is at the right location**

```bash
ls frontend/app/search/
```

Expected: `[id]/`, `preview/`, and `url-analysis/` all at the same level.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/search/url-analysis/
git commit -m "feat: add URL analysis page with histogram, AI analysis, and featured reviews"
```

---

## Final Verification

- [ ] **Run all backend tests**

```bash
cd backend && uv run pytest tests/test_analyze_url.py -v 2>&1
```

Expected: All 10 tests PASSED.

- [ ] **TypeScript clean compile**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: no errors from files modified in this plan.

- [ ] **Manual smoke test — Confirmation Grid**

1. Start backend: `cd backend && uv run uvicorn main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Run a search (e.g., "wireless headphones")
4. Verify:
   - Confirmation grid shows up to 10 products (was 5)
   - Products are sorted highest-rating first
   - Price appears in orange on its own line below the product title

- [ ] **Manual smoke test — URL Analysis**

1. Copy an Amazon product URL, e.g., `https://www.amazon.com/dp/B09JQMJHXY`
2. Paste it into the search bar on the home page and press Enter
3. Verify routing goes to `/search/url-analysis?asin=...&url=...` (not `/search/preview`)
4. Verify loading spinner appears with "Analyzing product…"
5. Verify the analysis page renders:
   - Product image + title + orange price + rating + "Price history ↗" link
   - Rating Breakdown with 5 bar rows
   - AI Analysis with summary, pros (✓), cons (✗)
   - Featured Reviews with star icons and "show more / show less" toggle
