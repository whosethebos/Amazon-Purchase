# backend/agents/orchestrator.py
import asyncio
from collections.abc import AsyncGenerator
from agents.scraper_agent import ScraperAgent
from agents.confirmation_agent import ConfirmationAgent
from agents.analyst_agent import ReviewAnalystAgent
from agents.ranker_agent import RankerAgent
import db.supabase_client as db
from config import settings


class OrchestratorAgent:
    """
    Coordinates the full product research pipeline:
    1. Scrape product batches from Amazon
    2. Wait for user to confirm which products to analyze
    3. Scrape reviews for confirmed products
    4. Analyze reviews with LLM (ReviewAnalystAgent)
    5. Rank products with LLM (RankerAgent)
    6. Store results in Supabase

    To add a new agent step, add it between phases below and emit an SSE status event.
    """

    def __init__(self, search_id: str, query: str, requirements: list[str] | None = None):
        self.search_id = search_id
        self.query = query
        self.requirements = requirements or []
        self.scraper = ScraperAgent()
        self.confirmation = ConfirmationAgent()
        self.analyst = ReviewAnalystAgent()
        self.ranker = RankerAgent()
        # asyncio.Event used to pause the pipeline until user confirms
        self._confirmation_event = asyncio.Event()
        self._confirmed_product_ids: list[str] = []

    async def receive_confirmation(self, product_ids: list[str]) -> None:
        """
        Called by the API route when the user confirms products.
        Empty list means user rejected all — fetch next batch.
        """
        self._confirmed_product_ids = product_ids
        self._confirmation_event.set()

    async def run(self) -> AsyncGenerator[dict, None]:
        """
        Main pipeline generator. Yields SSE event dicts throughout execution.
        Each yielded dict has {"event": str, "data": dict}.
        """
        db.update_search_status(self.search_id, "scraping")
        yield {"event": "status", "data": {"message": "Searching Amazon...", "status": "scraping"}}

        # --- Phase 1: Scrape product batches until user confirms ---
        offset = 0
        while True:
            search_query = self.query
            if self.requirements:
                search_query = f"{self.query} {' '.join(self.requirements)}"
            products = await self.scraper.fetch_batch(search_query, offset=offset)
            if not products:
                yield {"event": "error", "data": {"message": "No products found. Try a different search."}}
                db.update_search_status(self.search_id, "failed")
                return

            # Save batch to DB (not confirmed yet)
            saved = db.insert_products([
                {**p, "search_id": self.search_id, "confirmed": False}
                for p in products
            ])

            batch_state = self.confirmation.next_batch(saved)
            db.update_search_status(self.search_id, "confirming")

            yield {
                "event": "batch_ready",
                "data": {
                    "batch": saved,
                    "iteration": batch_state["iteration"],
                    "max_iterations": batch_state["max_iterations"],
                    "needs_more_detail": batch_state["needs_more_detail"],
                }
            }

            if batch_state["needs_more_detail"]:
                yield {
                    "event": "need_more_detail",
                    "data": {"message": "Could not find matching products. Please provide more detail."}
                }
                db.update_search_status(self.search_id, "failed")
                return

            # Pause and wait for user confirmation
            self._confirmation_event.clear()
            await self._confirmation_event.wait()

            if self._confirmed_product_ids:
                db.confirm_products(self._confirmed_product_ids)
                break
            else:
                # User rejected all — fetch next batch
                offset += settings.amazon_batch_size
                yield {"event": "status", "data": {"message": "Fetching next batch...", "status": "scraping"}}

        # --- Phase 2: Scrape reviews for confirmed products ---
        db.update_search_status(self.search_id, "analyzing")
        yield {"event": "status", "data": {"message": "Scraping reviews...", "status": "analyzing"}}

        confirmed_products = db.get_confirmed_products(self.search_id)
        for product in confirmed_products:
            yield {"event": "status", "data": {"message": f"Scraping reviews: {product['title'][:50]}..."}}
            reviews = await self.scraper.scrape_reviews(product["url"])
            if reviews:
                db.insert_reviews([{**r, "product_id": product["id"]} for r in reviews])

        # --- Phase 3: Analyze reviews with LLM ---
        yield {"event": "status", "data": {"message": "Analyzing reviews with AI...", "status": "analyzing"}}
        analyses: dict[str, dict] = {}

        for product in confirmed_products:
            yield {"event": "status", "data": {"message": f"Analyzing: {product['title'][:50]}..."}}
            reviews = db.get_reviews_by_product(product["id"])
            analysis = await self.analyst.analyze(product["title"], reviews, self.requirements)
            analyses[product["asin"]] = analysis
            db.insert_analysis({**analysis, "product_id": product["id"]})
            yield {
                "event": "analysis_done",
                "data": {"product_id": product["id"], "analysis": analysis}
            }

        # --- Phase 4: Rank products ---
        yield {"event": "status", "data": {"message": "Ranking products...", "status": "ranking"}}
        ranked = await self.ranker.rank(confirmed_products, analyses, self.requirements)

        # Update scores/ranks in the analysis table
        client = db.get_client()
        for item in ranked:
            existing = db.get_analysis_by_product(item["id"])
            if existing:
                client.table("analysis").update({
                    "score": item.get("score"),
                    "rank": item.get("rank"),
                }).eq("product_id", item["id"]).execute()

        db.update_search_status(self.search_id, "done")
        yield {
            "event": "complete",
            "data": {"message": "Done!", "search_id": self.search_id}
        }
