# Post-Implementation Changes — Mar 15, 2026

This document captures all changes made after the initial implementations documented in:
- `docs/superpowers/specs/2026-03-13-ux-upgrade-design.md`
- `docs/superpowers/specs/2026-03-13-url-analysis-design.md`

---

## 1. Baymax Avatar — Added and Removed

A Baymax animated mascot/avatar was added briefly (as a status indicator during search) and then fully removed at the user's request.

**What was removed:**
- `frontend/components/BaymaxAvatar.tsx` — deleted
- `frontend/lib/BaymaxContext.tsx` — deleted
- All `useBaymax()` / `setBaymaxState()` / `setBaymaxMessage()` calls from every page
- All `@keyframes baymax-*` CSS animations from `frontend/app/globals.css`
- `BaymaxProvider` wrapper and `BaymaxAvatar` render from `frontend/app/layout.tsx`

**Current state:** No Baymax references exist anywhere. The ux-upgrade spec's references to `setBaymaxState` and `useBaymax` are historical artifacts — the actual code does not use them.

---

## 2. Amazon International Domain Support

The original url-analysis spec stated: _"Only amazon.com is supported. International Amazon domains fall through to the normal search flow."_ This is now outdated.

### Frontend (`frontend/app/page.tsx`)

The URL detection regexes were broadened to cover:
- Any Amazon domain (`amazon.in`, `amazon.co.uk`, `amazon.de`, etc.)
- Short links (`amzn.in`, `amzn.to`)

```ts
// AMAZON_ASIN_RE: detect full product URLs on any Amazon domain
const AMAZON_ASIN_RE = /^https?:\/\/(www\.)?amazon\.\w+(\.\w+)?\/(dp|gp\/product)\/([A-Z0-9]{10})/;
// Note: ASIN is capture group 4 (group 2 is the optional .co subdomain)

// AMAZON_URL_RE: catch any Amazon URL or short link (fallback when ASIN not in URL)
const AMAZON_URL_RE = /^https?:\/\/(www\.)?amazon\.|^https?:\/\/amzn\./i;
```

Both now route to `/search/url-analysis`.

### Backend (`backend/main.py` — `POST /api/analyze-url`)

Short URLs (`amzn.in`, `amzn.to`) don't contain an ASIN. After failing the ASIN regex, the endpoint now follows the redirect to get the full URL:

```python
if not asin_match:
    import httpx
    headers = {"User-Agent": "Mozilla/5.0 ...Chrome/124.0.0.0 Safari/537.36"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=10, headers=headers) as client:
        resp = await client.get(url)
        url = str(resp.url)
    asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
```

**Note:** `HEAD` requests are rejected by `amzn.in` (returns 405). Must use `GET`.

---

## 3. Analysis Timeout Increased

Original: `asyncio.timeout(60)` — was too short for amazon.in which requires 2 page navigations × ~30s each + LLM.

**Current:** `asyncio.timeout(180)` in `backend/main.py` → `POST /api/analyze-url`.

---

## 4. Amazon.in Scraper Fixes (`backend/scraper/amazon.py` — `scrape_product_details`)

### 4a. Currency Detection

Previously hardcoded to `"USD"`. Now derived from the product URL domain:

```python
if "amazon.in" in url:   currency = "INR"
elif "amazon.co.uk" in url: currency = "GBP"
elif "amazon.de" in url or "amazon.fr" in url or "amazon.es" in url or "amazon.it" in url: currency = "EUR"
else: currency = "USD"
```

### 4b. Price Selector — Priority-Order Cascade

`.a-offscreen` alone is unreliable on amazon.in because it matches MRP and list prices before the actual buy-box price. Selectors are now tried in priority order:

```python
for _sel in [
    ".apexPriceToPay .a-offscreen",          # deal/sale price (most reliable)
    "#priceblock_dealprice",
    "#priceblock_ourprice",
    "span[id='price_inside_buybox']",
    ".a-price[data-a-color='price'] .a-offscreen",
    ".a-offscreen",                            # fallback
]:
    _el = await page.query_selector(_sel)
    if _el:
        _raw = (await _el.inner_text()).strip().replace(",", "")
        try:
            _v = float("".join(c for c in _raw if c.isdigit() or c == "."))
            if _v > 0:
                price = _v
                break
        except ValueError:
            pass
```

**Known limitation:** Amazon.in shows a personalized deal price (e.g. ₹11,990) for logged-in users based on location/offers. The scraper — running without session cookies — gets the non-personalized buy-box price (e.g. ₹12,997). This is expected behavior; fixing it requires storing session cookies.

### 4c. Histogram — Switched from `#histogramTable` to `.a-meter-bar`

On amazon.in, `#histogramTable` does not exist. Instead, histogram percentages are stored as inline CSS `width` on `.a-meter-bar` elements (e.g. `style="width:62%"`).

```python
stars_order = [5, 4, 3, 2, 1]
bar_els = await page.query_selector_all(".a-meter-bar")
for i, bar in enumerate(bar_els[:5]):
    style = await bar.get_attribute("style") or ""
    m = _re.search(r"width\s*:\s*(\d+\.?\d*)%", style)
    if m:
        histogram[str(stars_order[i])] = float(m.group(1))
```

### 4d. Reviews — Scraped from Product Page (Not Separate Reviews Page)

The separate `https://www.amazon.com/product-reviews/{asin}` navigation was removed. On amazon.in, this page redirects unauthenticated bots to the sign-in page, returning 0 reviews.

Reviews are now scraped from the product page itself after scrolling to trigger lazy-load:

```python
await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.75)")
await asyncio.sleep(2)
review_els = await page.query_selector_all("[data-hook='review']")
for el in review_els[:20]:
    star_el = await el.query_selector(
        "[data-hook='review-star-rating'] .a-icon-alt, "
        "[data-hook='review-star-rating-view'] .a-icon-alt, "
        "[data-hook='cmps-review-star-rating'] .a-icon-alt"
    )
    # ... scrape author, title, body
```

This works for both amazon.com and amazon.in — product pages show customer reviews without authentication.

---

## 5. Preview Images — Switched to Google Images (Headless)

The original DuckDuckGo httpx approach in `GET /api/preview-images` was replaced with a Playwright-based Google Images scraper after DuckDuckGo's API became unreliable server-side.

**Current implementation** in `backend/scraper/amazon.py` → `scrape_preview_images`:

```python
async def scrape_preview_images(query: str, max_images: int = 4) -> list[str]:
    encoded = query.replace(" ", "+")
    url = f"https://www.google.com/search?q={encoded}&tbm=isch&hl=en"
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, ...)
        # ... navigate, wait for images, filter by width >= 100px
```

Called from `backend/main.py` → `GET /api/preview-images` which calls `scrape_preview_images(q)`.

---

## Summary of Current Architecture Differences from Original Specs

| Area | Spec Said | Current Reality |
|------|-----------|-----------------|
| Supported domains | amazon.com only | amazon.com, amazon.in, amazon.co.uk, amazon.de, etc. + amzn.in/amzn.to short links |
| Short URL handling | Not supported | httpx GET with User-Agent follows redirect to resolve ASIN |
| Currency | Always USD | Derived from URL domain |
| Histogram source | `#histogramTable tr` | `.a-meter-bar` `style="width:X%"` |
| Reviews source | Separate `/product-reviews/{asin}` page | Product page scroll lazy-load |
| Preview images | DuckDuckGo via httpx | Google Images via headless Playwright |
| Analysis timeout | 60 seconds | 180 seconds |
| Baymax mascot | Part of ux-upgrade spec | Fully removed |
