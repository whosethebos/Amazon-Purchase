# backend/agents/scraper_agent.py
from scraper.amazon import search_products, scrape_product_reviews
from config import settings


class ScraperAgent:
    """
    Fetches product batches from Amazon and scrapes reviews for confirmed products.
    To modify scraping logic, edit backend/scraper/amazon.py.
    To change batch size, update AMAZON_BATCH_SIZE in .env.
    """

    async def fetch_batch(self, query: str, offset: int = 0) -> list[dict]:
        """
        Fetch a batch of products from Amazon search.
        offset is the starting product index (to get next batch).
        """
        max_fetch = offset + settings.amazon_batch_size
        all_products = await search_products(query, max_results=max_fetch)
        return all_products[offset:max_fetch]

    async def scrape_reviews(self, product_url: str) -> list[dict]:
        """
        Scrape reviews for a specific product URL.
        """
        return await scrape_product_reviews(
            product_url,
            max_reviews=settings.max_reviews_per_product
        )
