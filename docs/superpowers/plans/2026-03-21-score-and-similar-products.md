# Score & Similar Products Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 1–10 product score to the top of the analysis page and a lazy-loaded "Similar Products" section at the bottom that links directly to Amazon.

**Architecture:** The LLM prompt is extended to return a `score` field; score validation runs in `main.py` after the LLM call. A new `GET /api/similar-products` endpoint reuses the existing `search_products` scraper function. The frontend fetches similar products in a second `useEffect` after the main analysis resolves, rendering skeleton cards while loading.

**Tech Stack:** Python 3.11 + FastAPI + Playwright (backend), Next.js 14 + TypeScript + Tailwind CSS (frontend), pytest with `asyncio_mode=auto` (tests)

---

## File Map

| File | Role |
|------|------|
| `backend/llm/analyze.py` | LLM prompt + fallback — add `score` field, new params |
| `backend/main.py` | Call site update, score validation, new `/api/similar-products` endpoint |
| `backend/tests/test_analyze_url.py` | Existing tests (need signature update) + new score validation tests |
| `frontend/lib/types.ts` | Add `score` to `ReviewAnalysis`, add `SimilarProduct` interface |
| `frontend/lib/api.ts` | Add `fetchSimilarProducts()` |
| `frontend/app/search/url-analysis/page.tsx` | Add `ScoreCard` component, `similarProducts` state, Section E |

---

## Task 1: Update `run_llm_analysis` signature and prompt

**Files:**
- Modify: `backend/llm/analyze.py`
- Modify: `backend/tests/test_analyze_url.py`

- [ ] **Step 1: Update the existing tests to pass the new required params**

The existing `run_llm_analysis` tests call with 2 args. Add the new required args (`histogram`, `review_count`) so they continue to compile after the signature changes.

In `backend/tests/test_analyze_url.py`, find the two `run_llm_analysis` calls and update them:

```python
# Before
result = await run_llm_analysis("Test Product", [])
# After
result = await run_llm_analysis("Test Product", [], histogram={"5": 0.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0}, review_count=None)

# Before
result = await run_llm_analysis("Test Product", [{"stars": 5, "title": "Good", "body": "Nice"}])
# After
result = await run_llm_analysis("Test Product", [{"stars": 5, "title": "Good", "body": "Nice"}], histogram={"5": 100.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0}, review_count=1)
```

- [ ] **Step 2: Add a test that verifies `score` key exists in the fallback**

Append to `backend/tests/test_analyze_url.py`:

```python
async def test_run_llm_analysis_fallback_contains_score():
    """Fallback dict must include a 'score' key (value None) after signature change."""
    with patch("llm.analyze.chat_json", new=AsyncMock(side_effect=Exception("down"))):
        result = await run_llm_analysis(
            "Test Product", [],
            histogram={"5": 0.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0},
            review_count=None,
        )
    assert "score" in result
    assert result["score"] is None
```

- [ ] **Step 3: Run the new test to verify it fails (score key not in fallback yet)**

```bash
cd backend && python -m pytest tests/test_analyze_url.py::test_run_llm_analysis_fallback_contains_score -v
```
Expected: FAIL — `KeyError` or `AssertionError` because `score` not in `_LLM_FALLBACK` yet.

- [ ] **Step 4: Update `run_llm_analysis` in `backend/llm/analyze.py`**

Replace the entire file content:

```python
# backend/llm/analyze.py
"""LLM analysis helper — isolated from FastAPI for testability."""
from llm.ollama_client import chat_json

_LLM_FALLBACK: dict = {
    "summary": "",
    "pros": [],
    "cons": [],
    "featured_review_indices": [],
    "score": None,
}


async def run_llm_analysis(
    title: str,
    reviews: list[dict],
    histogram: dict,
    review_count: int | None,
) -> dict:
    """
    Call Ollama to summarize product reviews, pick representative ones, and score the product.
    Returns a shallow copy of _LLM_FALLBACK on any error.
    """
    formatted = "\n\n".join(
        f"[{i}] {r['stars']}★ — {r['title']}\n{r['body']}"
        for i, r in enumerate(reviews)
    )

    histogram_lines = "\n".join(
        f"  {star}★: {histogram.get(str(star), 0):.1f}%"
        for star in [5, 4, 3, 2, 1]
    )
    review_count_str = str(review_count) if review_count is not None else "unknown"

    prompt = f"""You are analyzing customer reviews for an Amazon product.

Product: {title}
Total reviews: {review_count_str}
Star distribution:
{histogram_lines}

Reviews (indexed 0 to {len(reviews) - 1}):
{formatted or "(no reviews available)"}

Respond ONLY with valid JSON in this exact shape:
{{
  "summary": "<2-3 sentence overview>",
  "pros": ["<specific pro>", ...],
  "cons": ["<specific con>", ...],
  "featured_review_indices": [<3-5 indices from 0 to {len(reviews) - 1} — pick substantive reviews covering both praise and criticism; return [] if no reviews>],
  "score": <plain integer between 1 and 10 inclusive — not a float, not a string>
}}

Rules:
- pros and cons: 3-5 items each, grounded in the review text
- featured_review_indices: valid 0-based indices only
- score: rate 1–10 based on (a) value for the price per review sentiment, (b) volume/trustworthiness of reviews, (c) star distribution quality, (d) balance of pros vs cons. Return an integer, not a float or string.
- Return only the JSON object, no other text"""

    try:
        return await chat_json([{"role": "user", "content": prompt}])
    except Exception:
        return dict(_LLM_FALLBACK)
```

- [ ] **Step 5: Run all tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_analyze_url.py -v
```
Expected: All tests PASS. The two existing fallback tests still pass because `dict(_LLM_FALLBACK)` equals `_LLM_FALLBACK` by value.

- [ ] **Step 6: Commit**

```bash
cd backend && git add llm/analyze.py tests/test_analyze_url.py
git commit -m "feat: extend run_llm_analysis with score, histogram, review_count params"
```

---

## Task 2: Add score validation in `main.py` and update call site

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/tests/test_analyze_url.py`

- [ ] **Step 1: Write tests for the score validation logic**

The validation logic will live in a helper `_validate_score(raw)` in `main.py`. Add these tests to `backend/tests/test_analyze_url.py`:

```python
# At top of file, add this import after the existing imports:
# from main import _validate_score

# Add at the end of the file:

from main import _validate_score


# ── _validate_score ─────────────────────────────────────────────────────────────

def test_validate_score_none():
    assert _validate_score(None) is None

def test_validate_score_valid_int():
    assert _validate_score(7) == 7

def test_validate_score_boundary_1():
    assert _validate_score(1) == 1

def test_validate_score_boundary_10():
    assert _validate_score(10) == 10

def test_validate_score_out_of_range_low():
    assert _validate_score(0) is None

def test_validate_score_out_of_range_high():
    assert _validate_score(11) is None

def test_validate_score_float_rounds_to_valid():
    assert _validate_score(7.6) == 8

def test_validate_score_float_rounds_to_invalid():
    assert _validate_score(0.4) is None  # rounds to 0, out of range

def test_validate_score_string_valid():
    assert _validate_score("7") == 7

def test_validate_score_string_invalid():
    assert _validate_score("good") is None

def test_validate_score_bool_true():
    assert _validate_score(True) is None  # bool is subclass of int; must reject

def test_validate_score_bool_false():
    assert _validate_score(False) is None
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
cd backend && python -m pytest tests/test_analyze_url.py -k "validate_score" -v
```
Expected: All FAIL — `ImportError: cannot import name '_validate_score' from 'main'`

- [ ] **Step 3: Add `_validate_score` helper and update the call site in `main.py`**

Add this helper function near the top of `backend/main.py` (after imports):

```python
def _validate_score(raw) -> int | None:
    """Coerce LLM-returned score to int 1–10, or None if invalid."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, float):
        raw = round(raw)
    elif isinstance(raw, str):
        try:
            raw = int(raw)
        except ValueError:
            return None
    if isinstance(raw, int) and 1 <= raw <= 10:
        return raw
    return None
```

Then update the `analyze_url` endpoint — find the `run_llm_analysis` call:

```python
# Before:
analysis = await run_llm_analysis(product_data["title"], reviews)

# After:
analysis = await run_llm_analysis(
    product_data["title"],
    reviews,
    histogram=product_data["histogram"],
    review_count=product_data["review_count"],
)
analysis["score"] = _validate_score(analysis.get("score"))
```

- [ ] **Step 4: Run the score validation tests**

```bash
cd backend && python -m pytest tests/test_analyze_url.py -k "validate_score" -v
```
Expected: All 12 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_analyze_url.py
git commit -m "feat: add score validation and pass histogram/review_count to LLM"
```

---

## Task 3: Add `/api/similar-products` endpoint

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/tests/test_analyze_url.py`

- [ ] **Step 1: Write tests for the new endpoint**

The endpoint uses `search_products` (Playwright-based). Mock it in tests using `unittest.mock.patch`.

Add to the end of `backend/tests/test_analyze_url.py`.

Note: `AsyncMock` and `patch` are already imported at the top of the file — do NOT add them again. Only add the two new imports and then the test functions:

```python
from httpx import AsyncClient, ASGITransport
from main import app


# ── /api/similar-products ───────────────────────────────────────────────────────

@pytest.fixture
def mock_search_results():
    return [
        {"asin": "B001", "title": "Similar Product One", "price": 29.99, "currency": "USD",
         "rating": 4.5, "review_count": 500, "image_url": "https://img.example.com/1.jpg",
         "url": "https://www.amazon.com/dp/B001"},
        {"asin": "B002", "title": "Similar Product Two", "price": 19.99, "currency": "USD",
         "rating": 4.2, "review_count": 200, "image_url": None,
         "url": "https://www.amazon.com/dp/B002"},
        {"asin": "SOURCE", "title": "Source Product (should be filtered)", "price": 49.99,
         "currency": "USD", "rating": 4.0, "review_count": 100, "image_url": None,
         "url": "https://www.amazon.com/dp/SOURCE"},
        {"asin": "B003", "title": "Similar Product Three", "price": 39.99, "currency": "USD",
         "rating": 3.8, "review_count": 80, "image_url": None,
         "url": "https://www.amazon.com/dp/B003"},
        {"asin": "B004", "title": "Similar Product Four", "price": 24.99, "currency": "USD",
         "rating": 4.1, "review_count": 150, "image_url": None,
         "url": "https://www.amazon.com/dp/B004"},
    ]


async def test_similar_products_filters_source_asin(mock_search_results):
    with patch("main.search_products", new=AsyncMock(return_value=mock_search_results)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/similar-products?asin=SOURCE&title=Some+Product+Name")
    assert resp.status_code == 200
    asins = [p["asin"] for p in resp.json()["products"]]
    assert "SOURCE" not in asins


async def test_similar_products_returns_at_most_4(mock_search_results):
    with patch("main.search_products", new=AsyncMock(return_value=mock_search_results)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/similar-products?asin=SOURCE&title=Some+Product+Name")
    assert len(resp.json()["products"]) <= 4


async def test_similar_products_empty_title_returns_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/similar-products?asin=SOURCE&title=   ")
    assert resp.status_code == 200
    assert resp.json() == {"products": []}


async def test_similar_products_scraper_error_returns_empty():
    with patch("main.search_products", new=AsyncMock(side_effect=Exception("scrape failed"))):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/similar-products?asin=SOURCE&title=Some+Product")
    assert resp.status_code == 200
    assert resp.json() == {"products": []}


async def test_similar_products_uses_first_6_words_of_title():
    """search_products should be called with a query of max 6 words."""
    long_title = "One Two Three Four Five Six Seven Eight Nine Ten extra words here"
    captured = {}
    async def mock_search(query, max_results):
        captured["query"] = query
        return []
    with patch("main.search_products", new=AsyncMock(side_effect=mock_search)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get(f"/api/similar-products?asin=B0XX&title={long_title.replace(' ', '+')}")
    assert len(captured["query"].split()) == 6
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_analyze_url.py -k "similar_products" -v
```
Expected: All FAIL — `404 Not Found` or `AttributeError` because the endpoint doesn't exist yet.

- [ ] **Step 3: Add the endpoint to `main.py`**

First add `search_products` to the import at the top of `main.py`:

```python
# Before:
from scraper.amazon import scrape_current_price, scrape_product_details, scrape_preview_images, extract_asin

# After:
from scraper.amazon import scrape_current_price, scrape_product_details, scrape_preview_images, extract_asin, search_products
```

Then add the endpoint after the existing `@app.get("/api/preview-images")` route:

```python
@app.get("/api/similar-products")
async def get_similar_products(asin: str, title: str):
    """Find similar Amazon products by searching with the product title."""
    try:
        if not title.strip():
            return {"products": []}
        query = " ".join(title.split()[:6])
        results = await search_products(query, max_results=8)
        filtered = [p for p in results if p.get("asin") != asin]
        return {"products": filtered[:4]}
    except Exception:
        return {"products": []}
```

- [ ] **Step 4: Run the similar-products tests**

```bash
cd backend && python -m pytest tests/test_analyze_url.py -k "similar_products" -v
```
Expected: All 5 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_analyze_url.py
git commit -m "feat: add /api/similar-products endpoint"
```

---

## Task 4: Update frontend types

**Files:**
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: Add `score` to `ReviewAnalysis` and add `SimilarProduct` interface**

In `frontend/lib/types.ts`, update `ReviewAnalysis`:

```typescript
export interface ReviewAnalysis {
  summary: string;
  pros: string[];
  cons: string[];
  featured_review_indices: number[];
  score: number | null;
}
```

Add the new interface after `ReviewAnalysis`:

```typescript
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

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types.ts
git commit -m "feat: add score to ReviewAnalysis and SimilarProduct type"
```

---

## Task 5: Add `fetchSimilarProducts` to the API client

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add `SimilarProduct` to the import and add the function**

In `frontend/lib/api.ts`, update the import line at the top:

```typescript
import type { AnalyzeUrlResponse, SimilarProduct } from "./types";
```

Add the new function at the end of the file:

```typescript
export async function fetchSimilarProducts(asin: string, title: string): Promise<SimilarProduct[]> {
  try {
    const res = await fetch(
      `${API_URL}/api/similar-products?asin=${encodeURIComponent(asin)}&title=${encodeURIComponent(title)}`
    );
    if (!res.ok) return [];
    const data = await res.json();
    return data.products ?? [];
  } catch {
    return [];
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add fetchSimilarProducts API function"
```

---

## Task 6: Add ScoreCard and Similar Products section to the analysis page

**Files:**
- Modify: `frontend/app/search/url-analysis/page.tsx`

- [ ] **Step 1: Add the `ScoreCard` component (above `ReviewCard`)**

At the top of `page.tsx`, **replace** the two existing import lines (lines 5–6):
```typescript
// existing line 5 — replace this:
import { analyzeUrl } from "@/lib/api";
// existing line 6 — replace this:
import type { AnalyzeUrlResponse, Histogram, Review } from "@/lib/types";
```
With:
```typescript
import { analyzeUrl, fetchSimilarProducts } from "@/lib/api";
import type { AnalyzeUrlResponse, Histogram, Review, SimilarProduct } from "@/lib/types";
```

Then add this component after the imports and before `ReviewCard`:

```typescript
// ─── ScoreCard ─────────────────────────────────────────────────────────────────

function ScoreCard({ score }: { score: number | null }) {
  if (score === null || score < 1 || score > 10) return null;

  const color =
    score >= 7 ? "text-emerald-400" : score >= 4 ? "text-yellow-400" : "text-red-400";
  const label =
    score >= 7 ? "Good buy" : score >= 4 ? "Mixed bag" : "Avoid";

  return (
    <div className="bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-5 flex items-center gap-5">
      <div className={`text-5xl font-bold tabular-nums ${color}`}>
        {score}<span className="text-2xl text-[#9898b8] font-normal">/10</span>
      </div>
      <div>
        <p className={`text-lg font-semibold ${color}`}>{label}</p>
        <p className="text-[#9898b8] text-xs mt-0.5">Overall score based on reviews & analysis</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add `SimilarProductCard` component**

Add after `ScoreCard`:

```typescript
// ─── SimilarProductCard ────────────────────────────────────────────────────────

function SimilarProductCard({ product }: { product: SimilarProduct }) {
  return (
    <a
      href={product.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-4 hover:border-[#818cf8] transition-colors"
    >
      <div className="flex gap-3 items-start">
        {product.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.image_url}
            alt={product.title}
            width={64}
            height={64}
            className="object-contain rounded-lg shrink-0 w-16 h-16"
          />
        ) : (
          <div className="w-16 h-16 bg-[#1a1a2e] rounded-lg shrink-0" />
        )}
        <div className="min-w-0 space-y-1">
          <p className="text-[#ebebf5] text-sm font-medium line-clamp-2 leading-snug">
            {product.title}
          </p>
          {product.price != null && (
            <p className="text-[#f97316] font-bold text-sm">
              {product.currency ?? "USD"} {product.price.toFixed(2)}
            </p>
          )}
          {product.rating != null && (
            <p className="text-[#9898b8] text-xs">
              ★ {product.rating.toFixed(1)}
              {product.review_count != null && (
                <span> ({product.review_count.toLocaleString()})</span>
              )}
            </p>
          )}
        </div>
      </div>
    </a>
  );
}
```

- [ ] **Step 3: Add `SimilarProductSkeleton` component**

Add after `SimilarProductCard`:

```typescript
// ─── SimilarProductSkeleton ────────────────────────────────────────────────────

function SimilarProductSkeleton() {
  return (
    <div className="bg-[#0f0f1a] border border-[#2a2a45] rounded-xl p-4 animate-pulse">
      <div className="flex gap-3 items-start">
        <div className="w-16 h-16 bg-[#1a1a2e] rounded-lg shrink-0" />
        <div className="flex-1 space-y-2 pt-1">
          <div className="h-3 bg-[#1a1a2e] rounded w-full" />
          <div className="h-3 bg-[#1a1a2e] rounded w-3/4" />
          <div className="h-3 bg-[#1a1a2e] rounded w-1/2" />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add `similarProducts` state and the lazy-load `useEffect`**

In `UrlAnalysisContent`, add the new state and effect after the existing state declarations (after `const [stepIndex, setStepIndex] = useState(0);`):

```typescript
const [similarProducts, setSimilarProducts] = useState<SimilarProduct[] | null>(null);
```

Add this effect after the existing two `useEffect` hooks (the step timer one and the main fetch one):

```typescript
useEffect(() => {
  if (!data) return;
  fetchSimilarProducts(data.product.asin, data.product.title)
    .then(setSimilarProducts)
    .catch(() => setSimilarProducts([]));
}, [data]);
```

- [ ] **Step 5: Render `ScoreCard` and Section E in the results view**

In the results JSX (inside the `return` that starts with `<main className="min-h-screen bg-[#07070d]">`):

Add `ScoreCard` between the back link and Section A:

```tsx
{/* Back link */}
<Link href="/" className="text-[#818cf8] text-sm hover:text-indigo-300 transition-colors">
  ← New Search
</Link>

{/* Score */}
<ScoreCard score={analysis.score} />

{/* Section A — Product Header */}
```

Add Section E at the very bottom, after Section D (Featured Reviews), before the closing `</div></main>`:

```tsx
{/* Section E — Similar Products */}
{(similarProducts === null || similarProducts.length > 0) && (
  <div>
    <h2 className="text-[#ebebf5] font-semibold mb-3">Similar Products</h2>
    <div className="grid grid-cols-1 gap-3">
      {similarProducts === null
        ? Array.from({ length: 4 }).map((_, i) => <SimilarProductSkeleton key={i} />)
        : similarProducts.map((p) => <SimilarProductCard key={p.asin} product={p} />)
      }
    </div>
  </div>
)}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/search/url-analysis/page.tsx
git commit -m "feat: add ScoreCard and lazy-loaded Similar Products section to analysis page"
```

---

## Final Verification

- [ ] **Start the backend**

```bash
cd backend && uvicorn main:app --reload
```

- [ ] **Start the frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Manual smoke test**

Navigate to the app and analyze a product URL. Verify:
1. Score card appears at the top with a colored number and label
2. "Similar Products" skeleton appears while loading, then resolves to product cards
3. Clicking a similar product card opens the Amazon page in a new tab
4. If score is null (LLM fallback), the score card is hidden entirely

- [ ] **Run all backend tests one final time**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: All tests PASS.
