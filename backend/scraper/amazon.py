# backend/scraper/amazon.py
import asyncio
from playwright.async_api import async_playwright
from config import settings


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
    async with async_playwright() as playwright:
        browser, page = await _get_page(playwright)
        try:
            url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
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
                    title_el = await item.query_selector("h2 a span")
                    title = await title_el.inner_text() if title_el else ""

                    # Price
                    price = None
                    price_el = await item.query_selector(".a-price .a-offscreen")
                    if price_el:
                        price_text = await price_el.inner_text()
                        price_text = price_text.replace("$", "").replace(",", "").strip()
                        try:
                            price = float(price_text)
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
                    link_el = await item.query_selector("h2 a")
                    href = await link_el.get_attribute("href") if link_el else ""
                    product_url = f"https://www.amazon.com{href}" if href else ""

                    # Image
                    img_el = await item.query_selector(".s-image")
                    image_url = await img_el.get_attribute("src") if img_el else None

                    if asin and title:
                        products.append({
                            "asin": asin,
                            "title": title,
                            "price": price,
                            "currency": "USD",
                            "rating": rating,
                            "review_count": review_count,
                            "url": product_url,
                            "image_url": image_url,
                        })
                except Exception:
                    continue

            return products
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
