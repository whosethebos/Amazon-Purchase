# backend/scraper/amazon.py
import asyncio
from playwright.async_api import async_playwright
from config import settings
import re as _re


def extract_asin(url: str) -> str | None:
    """Extract ASIN from an Amazon product URL. Returns None if not found."""
    m = _re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
    return m.group(1) if m else None


def _sort_products_by_rating(products: list[dict]) -> list[dict]:
    """Sort products by rating descending; products with no rating sort last."""
    return sorted(products, key=lambda p: p.get("rating") or 0, reverse=True)


def _currency_for_domain(domain: str) -> str:
    """Derive the currency code from an Amazon domain or URL string."""
    if "amazon.in" in domain:
        return "INR"
    if "amazon.co.uk" in domain:
        return "GBP"
    if any(x in domain for x in ("amazon.de", "amazon.fr", "amazon.es", "amazon.it")):
        return "EUR"
    return "USD"


async def _get_page(playwright):
    browser = await playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"]
    )
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
    )
    page = await context.new_page()
    return browser, page


async def search_products(query: str, max_results: int = 10) -> list[dict]:
    """
    Search Amazon for a query and return a list of product summaries.
    Returns up to max_results products with: asin, title, price, rating,
    review_count, url, image_url.
    """
    domain = settings.amazon_domain
    currency = _currency_for_domain(domain)

    async with async_playwright() as playwright:
        browser, page = await _get_page(playwright)
        try:
            url = f"https://www.{domain}/s?k={query.replace(' ', '+')}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # brief pause to avoid bot detection

            products = []
            items = await page.query_selector_all("[data-component-type='s-search-result']")

            for item in items[:max_results]:
                try:
                    asin = await item.get_attribute("data-asin") or ""
                    if not asin:
                        continue

                    # Title
                    title_el = await item.query_selector("h2 span")
                    title = await title_el.inner_text() if title_el else ""

                    # Price — try multiple selectors to handle different layouts
                    price = None
                    for _sel in [
                        ".a-price .a-offscreen",
                        ".a-price[data-a-color='base'] .a-offscreen",
                        ".a-price[data-a-color='price'] .a-offscreen",
                        ".a-color-price .a-offscreen",
                        ".a-price-whole",
                    ]:
                        price_el = await item.query_selector(_sel)
                        if price_el:
                            price_text = _re.sub(r"[^\d.]", "", await price_el.inner_text())
                            try:
                                price = float(price_text)
                                if price > 0:
                                    break
                            except ValueError:
                                pass

                    # Rating
                    rating = None
                    rating_el = await item.query_selector(".a-icon-alt")
                    if rating_el:
                        rating_text = await rating_el.inner_text()
                        try:
                            rating = float(rating_text.split()[0])
                        except (ValueError, IndexError):
                            pass

                    # Review count
                    review_count = None
                    review_el = await item.query_selector("[aria-label*='stars'] + span a span")
                    if not review_el:
                        review_el = await item.query_selector(".a-size-base.s-underline-text")
                    if review_el:
                        rc_text = await review_el.inner_text()
                        rc_text = rc_text.replace(",", "").strip()
                        try:
                            review_count = int(rc_text)
                        except ValueError:
                            pass

                    # Product URL
                    link_el = await item.query_selector("a[href*='/dp/']")
                    href = await link_el.get_attribute("href") if link_el else ""
                    product_url = f"https://www.{domain}{href}" if href else ""

                    # Image — try src first, fall back to data-src for lazy-loaded images
                    img_el = await item.query_selector(".s-image")
                    image_url = None
                    if img_el:
                        src = await img_el.get_attribute("src") or ""
                        image_url = src if src.startswith("https://") else (
                            await img_el.get_attribute("data-src") or None
                        )

                    if asin and title:
                        products.append({
                            "asin": asin,
                            "title": title,
                            "price": price,
                            "currency": currency,
                            "rating": rating,
                            "review_count": review_count,
                            "url": product_url,
                            "image_url": image_url,
                        })
                except Exception:
                    continue

            return _sort_products_by_rating(products)
        finally:
            await browser.close()


async def scrape_product_reviews(product_url: str, max_reviews: int = 20) -> list[dict]:
    """
    Scrape reviews from a product page.
    Returns a list of review dicts: reviewer, rating, title, body,
    helpful_votes, verified_purchase.
    """
    async with async_playwright() as playwright:
        browser, page = await _get_page(playwright)
        try:
            reviews_url = product_url.split("?")[0] + "#customerReviews"
            await page.goto(reviews_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            reviews = []
            review_els = await page.query_selector_all("[data-hook='review']")

            for el in review_els[:max_reviews]:
                try:
                    reviewer_el = await el.query_selector("[class*='profile-name']")
                    reviewer = await reviewer_el.inner_text() if reviewer_el else "Anonymous"

                    rating_el = await el.query_selector("[data-hook='review-star-rating'] .a-icon-alt")
                    rating = None
                    if rating_el:
                        try:
                            rating = int(float((await rating_el.inner_text()).split()[0]))
                        except (ValueError, IndexError):
                            pass

                    title_el = await el.query_selector("[data-hook='review-title'] span:not(.a-icon-alt)")
                    title = await title_el.inner_text() if title_el else ""

                    body_el = await el.query_selector("[data-hook='review-body'] span")
                    body = await body_el.inner_text() if body_el else ""

                    helpful_el = await el.query_selector("[data-hook='helpful-vote-statement']")
                    helpful_votes = 0
                    if helpful_el:
                        helpful_text = await helpful_el.inner_text()
                        try:
                            helpful_votes = int(helpful_text.split()[0])
                        except (ValueError, IndexError):
                            pass

                    verified_el = await el.query_selector("[data-hook='avp-badge']")
                    verified = verified_el is not None

                    reviews.append({
                        "reviewer": reviewer.strip(),
                        "rating": rating,
                        "title": title.strip(),
                        "body": body.strip(),
                        "helpful_votes": helpful_votes,
                        "verified_purchase": verified,
                    })
                except Exception:
                    continue

            return reviews
        finally:
            await browser.close()


async def scrape_current_price(product_url: str) -> dict | None:
    """
    Scrape only the current price from a product page (for watchlist refresh).
    Returns {"price": float, "currency": str} or None.
    """
    async with async_playwright() as playwright:
        browser, page = await _get_page(playwright)
        try:
            await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            price_el = await page.query_selector(".a-price .a-offscreen")
            if not price_el:
                price_el = await page.query_selector("#priceblock_ourprice")
            if not price_el:
                return None

            price_text = await price_el.inner_text()
            price_text = price_text.replace("$", "").replace(",", "").strip()
            price = float(price_text)
            return {"price": price, "currency": "USD"}
        except Exception:
            return None
        finally:
            await browser.close()


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
    asin = extract_asin(url) or ""
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

            # Price — try specific selectors first to avoid picking up MRP/crossed-out prices
            price = None
            for _sel in [
                ".apexPriceToPay .a-offscreen",         # sale/deal price (most reliable)
                "#priceblock_dealprice",
                "#priceblock_ourprice",
                "span[id='price_inside_buybox']",
                ".a-price[data-a-color='price'] .a-offscreen",
                ".a-offscreen",                          # fallback
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

            currency = _currency_for_domain(url)

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

            # ── Histogram: parse .a-meter-bar style widths (order: 5★→1★) ─────────
            # The separate /product-reviews page requires sign-in on some locales,
            # so we scrape both histogram and reviews from the product page itself.
            histogram = dict(empty_histogram)
            reviews: list[dict] = []

            stars_order = [5, 4, 3, 2, 1]
            bar_els = await page.query_selector_all(".a-meter-bar")
            for i, bar in enumerate(bar_els[:5]):
                style = await bar.get_attribute("style") or ""
                m = _re.search(r"width\s*:\s*(\d+\.?\d*)%", style)
                if m:
                    try:
                        histogram[str(stars_order[i])] = float(m.group(1))
                    except ValueError:
                        pass

            # ── Reviews: scroll product page to trigger lazy-load ───────────────
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.75)")
            await asyncio.sleep(2)

            review_els = await page.query_selector_all("[data-hook='review']")
            for el in review_els[:20]:
                try:
                    stars = 0
                    star_el = await el.query_selector(
                        "[data-hook='review-star-rating'] .a-icon-alt, "
                        "[data-hook='review-star-rating-view'] .a-icon-alt, "
                        "[data-hook='cmps-review-star-rating'] .a-icon-alt"
                    )
                    if star_el:
                        try:
                            stars = int(float((await star_el.text_content()).split()[0]))
                        except (ValueError, IndexError):
                            pass

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


async def scrape_preview_images(query: str, max_images: int = 4) -> list[str]:
    """
    Fetch preview image URLs via Bing Images using headless Chromium.
    Returns up to max_images HTTPS URLs. Best-effort; returns [] on failure.
    """
    encoded = query.replace(" ", "+")
    url = f"https://www.bing.com/images/search?q={encoded}&form=HDRSC2"
    async with async_playwright() as playwright:
        browser, page = await _get_page(playwright)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
            # Bing renders thumbnails as .mimg elements with src set directly
            images: list[str] = await page.evaluate("""
                () => Array.from(document.querySelectorAll('img.mimg'))
                    .map(img => img.src)
                    .filter(src => src && src.startsWith('https://'))
                    .slice(0, 4)
            """)
            return images[:max_images]
        except Exception:
            return []
        finally:
            await browser.close()
