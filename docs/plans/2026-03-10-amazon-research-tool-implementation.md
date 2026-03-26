# Amazon Product Research Tool — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full-stack Amazon product research tool with AI agents that scrape, analyze, and rank products, with a Next.js UI for search, product confirmation, results, and watchlist.

**Architecture:** FastAPI backend orchestrates Google ADK agents (Scraper → ConfirmationAgent → ReviewAnalyst → Ranker). Playwright handles Amazon scraping. Ollama (qwen3:14b) powers all LLM work. Results stream to Next.js via SSE. Everything persists in PostgreSQL (local).

**Tech Stack:** Python 3.11, FastAPI, Google ADK, Playwright, Ollama (qwen3:14b), PostgreSQL (psycopg3), Next.js 14 (App Router), TypeScript, Tailwind CSS

**Design doc:** [docs/plans/2026-03-10-amazon-research-tool-design.md](2026-03-10-amazon-research-tool-design.md)

---

## Task 1: Backend Project Initialization

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/.env.example`

**Step 1: Create backend requirements**

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
playwright==1.47.0
google-adk==1.0.0
httpx==0.27.0
psycopg[binary]>=3.1
psycopg-pool>=3.2
pydantic==2.8.0
pydantic-settings==2.4.0
python-dotenv==1.0.1
```

Save to `backend/requirements.txt`.

**Step 2: Create config**

```python
# backend/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama
    ollama_model: str = "qwen3:14b"
    ollama_base_url: str = "http://localhost:11434"

    # Database
    database_url: str = "postgresql://localhost/amazon_purchase"

    # Scraping
    amazon_batch_size: int = 5
    max_confirmation_iterations: int = 3
    max_reviews_per_product: int = 20

    # App
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
```

**Step 3: Create .env.example**

```
DATABASE_URL=postgresql://user:password@localhost:5432/amazon_purchase
OLLAMA_MODEL=qwen3:14b
OLLAMA_BASE_URL=http://localhost:11434
AMAZON_BATCH_SIZE=5
MAX_CONFIRMATION_ITERATIONS=3
MAX_REVIEWS_PER_PRODUCT=20
FRONTEND_URL=http://localhost:3000
```

**Step 4: Install dependencies**

```bash
cd backend
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
playwright install chromium
```

Expected: All packages install without errors. Chromium browser downloads.

**Step 5: Commit**

```bash
git init
git add backend/
git commit -m "feat: initialize backend project structure"
```

---

## Task 2: Pydantic Models

**Files:**
- Create: `backend/models.py`

**Step 1: Write the models**

```python
# backend/models.py
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


# --- Request models ---

class SearchRequest(BaseModel):
    query: str
    max_results: int = 10


class ConfirmationRequest(BaseModel):
    product_ids: list[UUID]   # IDs of confirmed products


# --- Response models ---

class ProductBase(BaseModel):
    id: UUID
    asin: str
    title: str
    price: float | None
    currency: str
    rating: float | None
    review_count: int | None
    url: str
    image_url: str | None
    confirmed: bool


class AnalysisResult(BaseModel):
    summary: str
    pros: list[str]
    cons: list[str]
    sentiment: str
    score: int    # 0-100
    rank: int


class ProductWithAnalysis(ProductBase):
    analysis: AnalysisResult | None = None


class SearchResult(BaseModel):
    search_id: UUID
    query: str
    status: str
    products: list[ProductWithAnalysis]
    created_at: datetime


class WatchlistItem(BaseModel):
    id: UUID
    product: ProductBase
    added_at: datetime
    last_checked_at: datetime | None
    current_price: float | None
    previous_price: float | None   # last price_history entry before current


class SearchHistoryItem(BaseModel):
    id: UUID
    query: str
    status: str
    product_count: int
    created_at: datetime


# --- SSE event models ---

class SSEEvent(BaseModel):
    event: str   # "status" | "batch_ready" | "analysis_done" | "complete" | "error"
    data: dict
```

**Step 2: Commit**

```bash
git add backend/models.py
git commit -m "feat: add pydantic models"
```

---

## Task 3: PostgreSQL Schema Setup

**Files:**
- Create: `backend/db/schema.sql`
- Create: `backend/db/postgres_client.py`

**Step 1: Create SQL schema**

Run this against your local PostgreSQL database:

```sql
-- backend/db/schema.sql

CREATE TABLE searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    max_results INT DEFAULT 10,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id UUID REFERENCES searches(id) ON DELETE CASCADE,
    asin TEXT NOT NULL,
    title TEXT,
    price DECIMAL,
    currency TEXT DEFAULT 'USD',
    rating DECIMAL,
    review_count INT,
    url TEXT NOT NULL,
    image_url TEXT,
    confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    reviewer TEXT,
    rating INT,
    title TEXT,
    body TEXT,
    helpful_votes INT DEFAULT 0,
    verified_purchase BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    summary TEXT,
    pros JSONB DEFAULT '[]',
    cons JSONB DEFAULT '[]',
    sentiment TEXT,
    score INT,
    rank INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ,
    UNIQUE(product_id)
);

CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL,
    currency TEXT DEFAULT 'USD',
    checked_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Step 2: Create PostgreSQL client helpers**

```python
# backend/db/postgres_client.py
from uuid import UUID
from db.pool import get_pool
from config import settings


def get_client() -> Client:
    return get_pool()


# --- Searches ---

def create_search(query: str, max_results: int) -> dict:
    client = get_client()
    result = client.table("searches").insert({
        "query": query,
        "max_results": max_results,
        "status": "pending"
    }).execute()
    return result.data[0]


def update_search_status(search_id: str, status: str) -> None:
    client = get_client()
    client.table("searches").update({"status": status}).eq("id", search_id).execute()


def get_search(search_id: str) -> dict | None:
    client = get_client()
    result = client.table("searches").select("*").eq("id", search_id).execute()
    return result.data[0] if result.data else None


def list_searches() -> list[dict]:
    client = get_client()
    result = client.table("searches").select("*").order("created_at", desc=True).execute()
    return result.data


def delete_search(search_id: str) -> None:
    client = get_client()
    client.table("searches").delete().eq("id", search_id).execute()


# --- Products ---

def insert_products(products: list[dict]) -> list[dict]:
    client = get_client()
    result = client.table("products").insert(products).execute()
    return result.data


def confirm_products(product_ids: list[str]) -> None:
    client = get_client()
    client.table("products").update({"confirmed": True}).in_("id", product_ids).execute()


def get_products_by_search(search_id: str) -> list[dict]:
    client = get_client()
    result = client.table("products").select("*").eq("search_id", search_id).execute()
    return result.data


def get_confirmed_products(search_id: str) -> list[dict]:
    client = get_client()
    result = (
        client.table("products")
        .select("*")
        .eq("search_id", search_id)
        .eq("confirmed", True)
        .execute()
    )
    return result.data


def get_product(product_id: str) -> dict | None:
    client = get_client()
    result = client.table("products").select("*").eq("id", product_id).execute()
    return result.data[0] if result.data else None


# --- Reviews ---

def insert_reviews(reviews: list[dict]) -> None:
    client = get_client()
    client.table("reviews").insert(reviews).execute()


def get_reviews_by_product(product_id: str) -> list[dict]:
    client = get_client()
    result = client.table("reviews").select("*").eq("product_id", product_id).execute()
    return result.data


# --- Analysis ---

def insert_analysis(analysis: dict) -> dict:
    client = get_client()
    result = client.table("analysis").insert(analysis).execute()
    return result.data[0]


def get_analysis_by_product(product_id: str) -> dict | None:
    client = get_client()
    result = client.table("analysis").select("*").eq("product_id", product_id).execute()
    return result.data[0] if result.data else None


# --- Watchlist ---

def add_to_watchlist(product_id: str) -> dict:
    client = get_client()
    result = client.table("watchlist").upsert({"product_id": product_id}).execute()
    return result.data[0]


def get_watchlist() -> list[dict]:
    client = get_client()
    result = (
        client.table("watchlist")
        .select("*, products(*)")
        .order("added_at", desc=True)
        .execute()
    )
    return result.data


def delete_watchlist_item(watchlist_id: str) -> None:
    client = get_client()
    client.table("watchlist").delete().eq("id", watchlist_id).execute()


def update_watchlist_checked(watchlist_id: str) -> None:
    from datetime import datetime, timezone
    client = get_client()
    client.table("watchlist").update({
        "last_checked_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", watchlist_id).execute()


# --- Price history ---

def insert_price_history(product_id: str, price: float, currency: str = "USD") -> None:
    client = get_client()
    client.table("price_history").insert({
        "product_id": product_id,
        "price": price,
        "currency": currency
    }).execute()


def get_price_history(product_id: str) -> list[dict]:
    client = get_client()
    result = (
        client.table("price_history")
        .select("*")
        .eq("product_id", product_id)
        .order("checked_at", desc=True)
        .limit(30)
        .execute()
    )
    return result.data
```

**Step 3: Create `backend/db/__init__.py`**

```python
# backend/db/__init__.py
```

**Step 4: Commit**

```bash
git add backend/db/
git commit -m "feat: add postgres schema and client helpers"
```

---

## Task 4: Ollama LLM Client

**Files:**
- Create: `backend/llm/__init__.py`
- Create: `backend/llm/ollama_client.py`

**Step 1: Create the Ollama client**

```python
# backend/llm/ollama_client.py
import json
import httpx
from config import settings


async def chat(messages: list[dict], response_format: str = "text") -> str:
    """
    Send a chat request to Ollama.

    Args:
        messages: list of {"role": "user"|"assistant"|"system", "content": "..."}
        response_format: "text" or "json" (for structured output)

    Returns:
        The model's response as a string.
    """
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
    }
    if response_format == "json":
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]


async def chat_json(messages: list[dict]) -> dict:
    """
    Like chat() but always requests JSON output and parses it.
    """
    content = await chat(messages, response_format="json")
    return json.loads(content)
```

**Step 2: Create `backend/llm/__init__.py`**

```python
# backend/llm/__init__.py
```

**Step 3: Verify Ollama is running**

```bash
curl http://localhost:11434/api/tags
```

Expected: JSON listing your installed models including `qwen3:14b`. If not installed:

```bash
ollama pull qwen3:14b
```

**Step 4: Commit**

```bash
git add backend/llm/
git commit -m "feat: add ollama async client"
```

---

## Task 5: Amazon Playwright Scraper

**Files:**
- Create: `backend/scraper/__init__.py`
- Create: `backend/scraper/amazon.py`

**Step 1: Create the scraper**

```python
# backend/scraper/amazon.py
import asyncio
from playwright.async_api import async_playwright, Page
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
            # Go to reviews page directly
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
```

**Step 2: Create `backend/scraper/__init__.py`**

```python
# backend/scraper/__init__.py
```

**Step 3: Commit**

```bash
git add backend/scraper/
git commit -m "feat: add playwright amazon scraper"
```

---

## Task 6: Google ADK Agents

**Files:**
- Create: `backend/agents/__init__.py`
- Create: `backend/agents/scraper_agent.py`
- Create: `backend/agents/confirmation_agent.py`
- Create: `backend/agents/analyst_agent.py`
- Create: `backend/agents/ranker_agent.py`
- Create: `backend/agents/orchestrator.py`

**Step 1: Create `backend/agents/__init__.py`**

```python
# backend/agents/__init__.py
```

**Step 2: Create ScraperAgent**

```python
# backend/agents/scraper_agent.py
from scraper.amazon import search_products, scrape_product_reviews
from config import settings


class ScraperAgent:
    """
    Fetches product batches from Amazon and scrapes reviews for confirmed products.
    """

    async def fetch_batch(
        self,
        query: str,
        offset: int = 0,
    ) -> list[dict]:
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
```

**Step 3: Create ConfirmationAgent**

```python
# backend/agents/confirmation_agent.py
from config import settings


class ConfirmationAgent:
    """
    Manages the iterative product confirmation loop.
    Tracks batches and iteration count.
    """

    def __init__(self):
        self.iteration = 0
        self.all_fetched: list[dict] = []

    def next_batch(self, new_products: list[dict]) -> dict:
        """
        Record a new batch and increment iteration counter.
        Returns state dict to emit via SSE.
        """
        self.iteration += 1
        self.all_fetched.extend(new_products)
        return {
            "iteration": self.iteration,
            "batch": new_products,
            "max_iterations": settings.max_confirmation_iterations,
            "needs_more_detail": self.iteration >= settings.max_confirmation_iterations,
        }

    def should_ask_for_more_detail(self) -> bool:
        return self.iteration >= settings.max_confirmation_iterations
```

**Step 4: Create ReviewAnalystAgent**

```python
# backend/agents/analyst_agent.py
from llm.ollama_client import chat_json


REVIEW_ANALYSIS_PROMPT = """You are a product review analyst.

Analyze the following Amazon product reviews and return a JSON object with:
- "summary": a 2-3 sentence overview of what customers think
- "pros": a list of 3-5 key positive points (strings)
- "cons": a list of 2-4 key negative points (strings)
- "sentiment": overall sentiment, one of "positive", "mixed", or "negative"

Product: {title}

Reviews:
{reviews_text}

Return only valid JSON, no extra text."""


class ReviewAnalystAgent:
    """
    Analyzes scraped product reviews using the local LLM (Ollama).
    """

    async def analyze(self, product_title: str, reviews: list[dict]) -> dict:
        """
        Returns analysis dict: summary, pros, cons, sentiment.
        """
        if not reviews:
            return {
                "summary": "No reviews available.",
                "pros": [],
                "cons": [],
                "sentiment": "mixed",
            }

        # Format reviews for the prompt
        reviews_text = "\n\n".join([
            f"Rating: {r.get('rating', '?')}/5\n{r.get('title', '')}\n{r.get('body', '')}"
            for r in reviews[:20]
        ])

        prompt = REVIEW_ANALYSIS_PROMPT.format(
            title=product_title,
            reviews_text=reviews_text,
        )

        result = await chat_json([{"role": "user", "content": prompt}])
        return {
            "summary": result.get("summary", ""),
            "pros": result.get("pros", []),
            "cons": result.get("cons", []),
            "sentiment": result.get("sentiment", "mixed"),
        }
```

**Step 5: Create RankerAgent**

```python
# backend/agents/ranker_agent.py
from llm.ollama_client import chat_json


RANKING_PROMPT = """You are a product ranking expert.

Score each of the following Amazon products on a scale of 0 to 100 based on:
- Value for money (price vs features)
- Quality (build quality, durability based on reviews)
- Reliability (consistency of positive reviews)

Products:
{products_text}

Return a JSON object with a "rankings" array. Each item must have:
- "asin": the product ASIN
- "score": integer 0-100
- "rank": integer starting from 1 (1 = best)

Sort by score descending. Return only valid JSON, no extra text."""


class RankerAgent:
    """
    Scores and ranks analyzed products using the local LLM (Ollama).
    """

    async def rank(self, products: list[dict], analyses: dict[str, dict]) -> list[dict]:
        """
        products: list of product dicts with asin, title, price, rating, review_count
        analyses: dict mapping product asin to analysis dict (summary, pros, cons)
        Returns products sorted by score with score and rank added.
        """
        if not products:
            return []

        products_text = ""
        for i, p in enumerate(products, 1):
            analysis = analyses.get(p["asin"], {})
            products_text += (
                f"{i}. ASIN: {p['asin']}\n"
                f"   Title: {p.get('title', 'Unknown')}\n"
                f"   Price: ${p.get('price', 'N/A')}\n"
                f"   Rating: {p.get('rating', 'N/A')}/5 ({p.get('review_count', 0)} reviews)\n"
                f"   Summary: {analysis.get('summary', 'N/A')}\n"
                f"   Pros: {', '.join(analysis.get('pros', []))}\n"
                f"   Cons: {', '.join(analysis.get('cons', []))}\n\n"
            )

        result = await chat_json([{
            "role": "user",
            "content": RANKING_PROMPT.format(products_text=products_text)
        }])

        # Build lookup of asin -> rank data
        rank_map = {
            r["asin"]: {"score": r["score"], "rank": r["rank"]}
            for r in result.get("rankings", [])
        }

        # Merge rank data back into products
        ranked = []
        for p in products:
            rank_data = rank_map.get(p["asin"], {"score": 50, "rank": 99})
            ranked.append({**p, **rank_data})

        ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
        return ranked
```

**Step 6: Create OrchestratorAgent**

```python
# backend/agents/orchestrator.py
import asyncio
from collections.abc import AsyncGenerator
from agents.scraper_agent import ScraperAgent
from agents.confirmation_agent import ConfirmationAgent
from agents.analyst_agent import ReviewAnalystAgent
from agents.ranker_agent import RankerAgent
import db.postgres_client as db
from config import settings


class OrchestratorAgent:
    """
    Coordinates the full product research pipeline:
    1. Scrape product batches
    2. Wait for user confirmation
    3. Scrape reviews for confirmed products
    4. Analyze reviews with LLM
    5. Rank products with LLM
    6. Store and return results
    """

    def __init__(self, search_id: str, query: str):
        self.search_id = search_id
        self.query = query
        self.scraper = ScraperAgent()
        self.confirmation = ConfirmationAgent()
        self.analyst = ReviewAnalystAgent()
        self.ranker = RankerAgent()
        # Event used to receive confirmation from user
        self._confirmation_event = asyncio.Event()
        self._confirmed_product_ids: list[str] = []

    async def receive_confirmation(self, product_ids: list[str]) -> None:
        """
        Called by the API route when the user confirms products.
        Unblocks the pipeline.
        """
        self._confirmed_product_ids = product_ids
        self._confirmation_event.set()

    async def run(self) -> AsyncGenerator[dict, None]:
        """
        Main pipeline generator. Yields SSE event dicts throughout execution.
        """
        db.update_search_status(self.search_id, "scraping")
        yield {"event": "status", "data": {"message": "Searching Amazon...", "status": "scraping"}}

        # --- Phase 1: Scrape batches until confirmed ---
        offset = 0
        while True:
            products = await self.scraper.fetch_batch(self.query, offset=offset)
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
                    "needs_more_detail": batch_state["needs_more_detail"],
                }
            }

            if batch_state["needs_more_detail"]:
                yield {
                    "event": "need_more_detail",
                    "data": {"message": "Could not find matching products. Please provide more detail or a reference image."}
                }
                db.update_search_status(self.search_id, "failed")
                return

            # Wait for user to confirm (or reject and request next batch)
            self._confirmation_event.clear()
            await self._confirmation_event.wait()

            if self._confirmed_product_ids:
                # User confirmed some products — proceed
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
            yield {"event": "status", "data": {"message": f"Scraping reviews for {product['title'][:40]}..."}}
            reviews = await self.scraper.scrape_reviews(product["url"])
            if reviews:
                db.insert_reviews([
                    {**r, "product_id": product["id"]}
                    for r in reviews
                ])

        # --- Phase 3: Analyze reviews with LLM ---
        yield {"event": "status", "data": {"message": "Analyzing reviews with AI...", "status": "analyzing"}}
        analyses: dict[str, dict] = {}

        for product in confirmed_products:
            yield {"event": "status", "data": {"message": f"Analyzing: {product['title'][:40]}..."}},
            reviews = db.get_reviews_by_product(product["id"])
            analysis = await self.analyst.analyze(product["title"], reviews)
            analyses[product["asin"]] = analysis
            db.insert_analysis({**analysis, "product_id": product["id"]})
            yield {
                "event": "analysis_done",
                "data": {"product_id": product["id"], "analysis": analysis}
            }

        # --- Phase 4: Rank products ---
        yield {"event": "status", "data": {"message": "Ranking products...", "status": "ranking"}}
        ranked = await self.ranker.rank(confirmed_products, analyses)

        # Update scores/ranks in DB
        for item in ranked:
            existing = db.get_analysis_by_product(item["id"])
            if existing:
                db.get_client().table("analysis").update({
                    "score": item.get("score"),
                    "rank": item.get("rank"),
                }).eq("product_id", item["id"]).execute()

        db.update_search_status(self.search_id, "done")
        yield {
            "event": "complete",
            "data": {"message": "Done!", "search_id": self.search_id}
        }
```

**Step 7: Commit**

```bash
git add backend/agents/
git commit -m "feat: add google adk agents (scraper, confirmation, analyst, ranker, orchestrator)"
```

---

## Task 7: FastAPI Routes

**Files:**
- Create: `backend/main.py`

**Step 1: Create main FastAPI app**

```python
# backend/main.py
import asyncio
import json
from uuid import UUID
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from models import SearchRequest, ConfirmationRequest
from agents.orchestrator import OrchestratorAgent
import db.postgres_client as db
from scraper.amazon import scrape_current_price
from config import settings

app = FastAPI(title="Amazon Research Tool")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store of active orchestrators keyed by search_id
# In production you'd use Redis, but this is fine for a local tool
_active_orchestrators: dict[str, OrchestratorAgent] = {}
_sse_queues: dict[str, asyncio.Queue] = {}


# --- Search ---

@app.post("/api/search")
async def start_search(request: SearchRequest, background_tasks: BackgroundTasks):
    """Start a new search. Returns search_id immediately."""
    search = db.create_search(request.query, request.max_results)
    search_id = str(search["id"])

    orchestrator = OrchestratorAgent(search_id, request.query)
    _active_orchestrators[search_id] = orchestrator

    queue: asyncio.Queue = asyncio.Queue()
    _sse_queues[search_id] = queue

    async def run_and_queue():
        async for event in orchestrator.run():
            await queue.put(event)
        await queue.put(None)  # sentinel

    background_tasks.add_task(run_and_queue)

    return {"search_id": search_id}


@app.get("/api/search/{search_id}/stream")
async def stream_search(search_id: str):
    """SSE stream of agent progress events."""
    queue = _sse_queues.get(search_id)
    if not queue:
        raise HTTPException(404, "Search not found or already complete")

    async def event_generator():
        while True:
            event = await queue.get()
            if event is None:
                yield "data: {\"event\": \"done\"}\n\n"
                break
            yield f"data: {json.dumps(event)}\n\n"
        _sse_queues.pop(search_id, None)
        _active_orchestrators.pop(search_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/search/{search_id}/confirm")
async def confirm_products(search_id: str, request: ConfirmationRequest):
    """
    Submit user's product confirmation. product_ids=[] means reject all and fetch next batch.
    """
    orchestrator = _active_orchestrators.get(search_id)
    if not orchestrator:
        raise HTTPException(404, "Active search not found")

    await orchestrator.receive_confirmation([str(pid) for pid in request.product_ids])
    return {"ok": True}


@app.get("/api/search/{search_id}/results")
async def get_results(search_id: str):
    """Fetch final ranked results for a completed search."""
    search = db.get_search(search_id)
    if not search:
        raise HTTPException(404, "Search not found")

    products = db.get_confirmed_products(search_id)
    result = []
    for product in products:
        analysis = db.get_analysis_by_product(product["id"])
        result.append({**product, "analysis": analysis})

    result.sort(key=lambda x: (x.get("analysis") or {}).get("rank") or 99)
    return {"search": search, "products": result}


# --- Search history ---

@app.get("/api/searches")
async def list_searches():
    """List all past searches for the history panel."""
    searches = db.list_searches()
    result = []
    for s in searches:
        products = db.get_confirmed_products(str(s["id"]))
        result.append({**s, "product_count": len(products)})
    return result


@app.delete("/api/searches/{search_id}")
async def delete_search(search_id: str):
    """Delete a search and all its associated data."""
    db.delete_search(search_id)
    return {"ok": True}


# --- Watchlist ---

@app.get("/api/watchlist")
async def get_watchlist():
    """Get all watchlist items with current and previous price."""
    items = db.get_watchlist()
    result = []
    for item in items:
        product = item.get("products", {})
        price_history = db.get_price_history(str(product["id"])) if product else []
        current_price = price_history[0]["price"] if price_history else product.get("price")
        previous_price = price_history[1]["price"] if len(price_history) > 1 else None
        result.append({
            "id": item["id"],
            "product": product,
            "added_at": item["added_at"],
            "last_checked_at": item["last_checked_at"],
            "current_price": current_price,
            "previous_price": previous_price,
        })
    return result


@app.post("/api/watchlist")
async def add_to_watchlist(body: dict):
    """Add a product to the watchlist by product_id."""
    product_id = body.get("product_id")
    if not product_id:
        raise HTTPException(400, "product_id required")
    item = db.add_to_watchlist(str(product_id))
    return item


@app.delete("/api/watchlist/{watchlist_id}")
async def remove_from_watchlist(watchlist_id: str):
    """Remove a product from the watchlist."""
    db.delete_watchlist_item(watchlist_id)
    return {"ok": True}


@app.post("/api/watchlist/{watchlist_id}/refresh")
async def refresh_watchlist_item(watchlist_id: str):
    """On-demand price refresh for a watchlist item."""
    items = db.get_watchlist()
    item = next((i for i in items if str(i["id"]) == watchlist_id), None)
    if not item:
        raise HTTPException(404, "Watchlist item not found")

    product = item.get("products", {})
    price_data = await scrape_current_price(product["url"])
    if price_data:
        db.insert_price_history(str(product["id"]), price_data["price"], price_data["currency"])
        db.update_watchlist_checked(watchlist_id)

    return {"price": price_data}
```

**Step 2: Run and verify the API starts**

```bash
cd backend
uv run uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000/docs` — you should see the FastAPI Swagger UI with all routes listed.

**Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: add fastapi routes with sse streaming and watchlist"
```

---

## Task 8: Frontend Project Initialization

**Files:**
- Create: `frontend/` (Next.js project)

**Step 1: Create Next.js project**

```bash
cd /path/to/Amazon-Purchase
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --app \
  --no-src-dir \
  --import-alias "@/*"
```

Wait for prompts and accept defaults.

**Step 2: Install additional dependencies**

```bash
cd frontend
npm install lucide-react
```

**Step 3: Create API base URL config**

Create `frontend/lib/config.ts`:

```typescript
// frontend/lib/config.ts
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
```

Create `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: initialize next.js frontend"
```

---

## Task 9: Frontend API Client and SSE Hook

**Files:**
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/useSSE.ts`

**Step 1: Create API client**

```typescript
// frontend/lib/api.ts
import { API_URL } from "./config";

export async function startSearch(query: string, maxResults = 10): Promise<{ search_id: string }> {
  const res = await fetch(`${API_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, max_results: maxResults }),
  });
  if (!res.ok) throw new Error("Failed to start search");
  return res.json();
}

export async function confirmProducts(searchId: string, productIds: string[]): Promise<void> {
  const res = await fetch(`${API_URL}/api/search/${searchId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_ids: productIds }),
  });
  if (!res.ok) throw new Error("Failed to confirm products");
}

export async function getResults(searchId: string) {
  const res = await fetch(`${API_URL}/api/search/${searchId}/results`);
  if (!res.ok) throw new Error("Failed to fetch results");
  return res.json();
}

export async function getSearchHistory() {
  const res = await fetch(`${API_URL}/api/searches`);
  if (!res.ok) throw new Error("Failed to fetch search history");
  return res.json();
}

export async function deleteSearch(searchId: string): Promise<void> {
  await fetch(`${API_URL}/api/searches/${searchId}`, { method: "DELETE" });
}

export async function getWatchlist() {
  const res = await fetch(`${API_URL}/api/watchlist`);
  if (!res.ok) throw new Error("Failed to fetch watchlist");
  return res.json();
}

export async function addToWatchlist(productId: string) {
  const res = await fetch(`${API_URL}/api/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_id: productId }),
  });
  if (!res.ok) throw new Error("Failed to add to watchlist");
  return res.json();
}

export async function removeFromWatchlist(watchlistId: string): Promise<void> {
  await fetch(`${API_URL}/api/watchlist/${watchlistId}`, { method: "DELETE" });
}

export async function refreshWatchlistItem(watchlistId: string) {
  const res = await fetch(`${API_URL}/api/watchlist/${watchlistId}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to refresh price");
  return res.json();
}
```

**Step 2: Create SSE hook**

```typescript
// frontend/lib/useSSE.ts
"use client";
import { useEffect, useRef, useState } from "react";
import { API_URL } from "./config";

export type SSEEvent = {
  event: string;
  data: Record<string, unknown>;
};

export function useSSE(searchId: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!searchId) return;
    const es = new EventSource(`${API_URL}/api/search/${searchId}/stream`);
    esRef.current = es;
    setIsConnected(true);

    es.onmessage = (e) => {
      const parsed: SSEEvent = JSON.parse(e.data);
      if (parsed.event === "done") {
        setIsDone(true);
        es.close();
        setIsConnected(false);
        return;
      }
      setEvents((prev) => [...prev, parsed]);
    };

    es.onerror = () => {
      es.close();
      setIsConnected(false);
    };

    return () => {
      es.close();
    };
  }, [searchId]);

  return { events, isConnected, isDone };
}
```

**Step 3: Commit**

```bash
git add frontend/lib/
git commit -m "feat: add frontend api client and sse hook"
```

---

## Task 10: Frontend Components

**Files:**
- Create: `frontend/components/SearchBar.tsx`
- Create: `frontend/components/ProgressFeed.tsx`
- Create: `frontend/components/ConfirmationGrid.tsx`
- Create: `frontend/components/ProductCard.tsx`
- Create: `frontend/components/WatchlistCard.tsx`
- Create: `frontend/components/SearchHistory.tsx`

**Step 1: SearchBar**

```tsx
// frontend/components/SearchBar.tsx
"use client";
import { useState } from "react";
import { Search } from "lucide-react";

type Props = {
  onSearch: (query: string) => void;
  isLoading?: boolean;
};

export function SearchBar({ onSearch, isLoading }: Props) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search for a product on Amazon..."
        className="flex-1 px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-orange-400 text-base"
        disabled={isLoading}
      />
      <button
        type="submit"
        disabled={isLoading || !query.trim()}
        className="px-6 py-3 bg-orange-500 text-white rounded-lg font-semibold hover:bg-orange-600 disabled:opacity-50 flex items-center gap-2"
      >
        <Search size={18} />
        {isLoading ? "Searching..." : "Search"}
      </button>
    </form>
  );
}
```

**Step 2: ProgressFeed**

```tsx
// frontend/components/ProgressFeed.tsx
import type { SSEEvent } from "@/lib/useSSE";

type Props = { events: SSEEvent[] };

export function ProgressFeed({ events }: Props) {
  if (events.length === 0) return null;
  return (
    <div className="bg-gray-50 rounded-lg p-4 space-y-1 max-h-40 overflow-y-auto">
      {events.map((e, i) => (
        <div key={i} className="text-sm text-gray-600 flex items-center gap-2">
          <span className="text-orange-400">›</span>
          {String((e.data as { message?: string }).message ?? e.event)}
        </div>
      ))}
    </div>
  );
}
```

**Step 3: ConfirmationGrid**

```tsx
// frontend/components/ConfirmationGrid.tsx
"use client";
import { useState } from "react";
import Image from "next/image";

type Product = {
  id: string;
  title: string;
  price: number | null;
  rating: number | null;
  review_count: number | null;
  image_url: string | null;
};

type Props = {
  products: Product[];
  iteration: number;
  maxIterations: number;
  onConfirm: (selectedIds: string[]) => void;
  onNextBatch: () => void;
};

export function ConfirmationGrid({ products, iteration, maxIterations, onConfirm, onNextBatch }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(products.map((p) => p.id)));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">
          Is this the kind of product you&apos;re looking for?
          <span className="ml-2 text-sm text-gray-500 font-normal">Batch {iteration} / {maxIterations}</span>
        </h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        {products.map((product) => (
          <button
            key={product.id}
            onClick={() => toggle(product.id)}
            className={`text-left rounded-xl border-2 p-3 transition-all ${
              selected.has(product.id)
                ? "border-orange-500 bg-orange-50"
                : "border-gray-200 hover:border-gray-300"
            }`}
          >
            {product.image_url && (
              <div className="w-full h-40 relative mb-2 rounded-lg overflow-hidden bg-gray-100">
                <Image src={product.image_url} alt={product.title} fill className="object-contain p-2" />
              </div>
            )}
            <p className="text-sm font-medium text-gray-900 line-clamp-2">{product.title}</p>
            <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
              {product.price && <span className="font-semibold text-gray-800">${product.price}</span>}
              {product.rating && <span>★ {product.rating}</span>}
              {product.review_count && <span>({product.review_count.toLocaleString()})</span>}
            </div>
          </button>
        ))}
      </div>

      <div className="flex gap-3 pt-2">
        <button onClick={selectAll} className="text-sm text-orange-500 hover:underline">
          Select All
        </button>
        <div className="flex-1" />
        <button
          onClick={onNextBatch}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
        >
          None of these →
        </button>
        <button
          onClick={() => onConfirm([...selected])}
          disabled={selected.size === 0}
          className="px-5 py-2 bg-orange-500 text-white rounded-lg text-sm font-semibold hover:bg-orange-600 disabled:opacity-40"
        >
          Confirm Selected ({selected.size})
        </button>
      </div>
    </div>
  );
}
```

**Step 4: ProductCard**

```tsx
// frontend/components/ProductCard.tsx
import Image from "next/image";
import { ExternalLink, Plus } from "lucide-react";

type Analysis = {
  summary: string;
  pros: string[];
  cons: string[];
  score: number;
  rank: number;
};

type Product = {
  id: string;
  title: string;
  price: number | null;
  rating: number | null;
  review_count: number | null;
  url: string;
  image_url: string | null;
  analysis?: Analysis | null;
};

type Props = {
  product: Product;
  onAddToWatchlist?: (productId: string) => void;
};

export function ProductCard({ product, onAddToWatchlist }: Props) {
  const { analysis } = product;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex gap-5">
      {/* Rank badge */}
      {analysis?.rank && (
        <div className="flex-shrink-0 w-10 h-10 bg-orange-500 text-white rounded-full flex items-center justify-center font-bold text-lg">
          {analysis.rank}
        </div>
      )}

      {/* Image */}
      {product.image_url && (
        <div className="flex-shrink-0 w-24 h-24 relative rounded-lg overflow-hidden bg-gray-100">
          <Image src={product.image_url} alt={product.title} fill className="object-contain p-1" />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-gray-900 line-clamp-2">{product.title}</h3>
          {analysis?.score != null && (
            <span className="flex-shrink-0 text-sm font-bold text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full">
              {analysis.score}/100
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-sm text-gray-500">
          {product.price && <span className="text-lg font-bold text-gray-900">${product.price}</span>}
          {product.rating && <span>★ {product.rating}</span>}
          {product.review_count && <span>({product.review_count.toLocaleString()} reviews)</span>}
        </div>

        {analysis && (
          <div className="space-y-1">
            <p className="text-sm text-gray-600">{analysis.summary}</p>
            <div className="flex gap-4 text-xs">
              <div>
                <span className="text-green-600 font-semibold">Pros: </span>
                {analysis.pros.slice(0, 2).join(" · ")}
              </div>
              <div>
                <span className="text-red-500 font-semibold">Cons: </span>
                {analysis.cons.slice(0, 2).join(" · ")}
              </div>
            </div>
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <a
            href={product.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-sm text-orange-500 hover:underline"
          >
            <ExternalLink size={14} /> View on Amazon
          </a>
          {onAddToWatchlist && (
            <button
              onClick={() => onAddToWatchlist(product.id)}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
            >
              <Plus size={14} /> Watchlist
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 5: WatchlistCard**

```tsx
// frontend/components/WatchlistCard.tsx
import Image from "next/image";
import { Trash2, RefreshCw, ExternalLink, TrendingDown, TrendingUp, Minus } from "lucide-react";

type WatchlistItem = {
  id: string;
  product: {
    title: string;
    url: string;
    image_url: string | null;
  };
  current_price: number | null;
  previous_price: number | null;
  last_checked_at: string | null;
};

type Props = {
  item: WatchlistItem;
  onDelete: (id: string) => void;
  onRefresh: (id: string) => void;
};

export function WatchlistCard({ item, onDelete, onRefresh }: Props) {
  const { product, current_price, previous_price } = item;
  const priceDiff = current_price != null && previous_price != null
    ? current_price - previous_price
    : null;

  return (
    <div className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
      {product.image_url && (
        <div className="w-12 h-12 relative flex-shrink-0 rounded overflow-hidden bg-gray-100">
          <Image src={product.image_url} alt={product.title} fill className="object-contain" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 line-clamp-1">{product.title}</p>
        <div className="flex items-center gap-2 text-sm">
          {current_price != null && (
            <span className="font-bold text-gray-800">${current_price}</span>
          )}
          {priceDiff != null && priceDiff !== 0 && (
            <span className={`flex items-center gap-0.5 text-xs ${priceDiff < 0 ? "text-green-600" : "text-red-500"}`}>
              {priceDiff < 0 ? <TrendingDown size={12} /> : <TrendingUp size={12} />}
              {priceDiff < 0 ? `-$${Math.abs(priceDiff).toFixed(2)}` : `+$${priceDiff.toFixed(2)}`}
            </span>
          )}
          {priceDiff === 0 && <Minus size={12} className="text-gray-400" />}
        </div>
      </div>
      <div className="flex gap-1">
        <a href={product.url} target="_blank" rel="noopener noreferrer"
          className="p-1.5 text-gray-400 hover:text-orange-500 rounded">
          <ExternalLink size={14} />
        </a>
        <button onClick={() => onRefresh(item.id)}
          className="p-1.5 text-gray-400 hover:text-blue-500 rounded">
          <RefreshCw size={14} />
        </button>
        <button onClick={() => onDelete(item.id)}
          className="p-1.5 text-gray-400 hover:text-red-500 rounded">
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
```

**Step 6: SearchHistory**

```tsx
// frontend/components/SearchHistory.tsx
import { Trash2, ChevronRight } from "lucide-react";
import Link from "next/link";

type HistoryItem = {
  id: string;
  query: string;
  status: string;
  product_count: number;
  created_at: string;
};

type Props = {
  items: HistoryItem[];
  onDelete: (id: string) => void;
};

export function SearchHistory({ items, onDelete }: Props) {
  if (items.length === 0) return <p className="text-sm text-gray-400">No searches yet.</p>;

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item.id} className="flex items-center gap-2 p-3 bg-white rounded-lg border border-gray-200">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-900 text-sm truncate">&quot;{item.query}&quot;</p>
            <p className="text-xs text-gray-400">
              {item.product_count} products · {new Date(item.created_at).toLocaleDateString()}
            </p>
          </div>
          {item.status === "done" && (
            <Link href={`/search/${item.id}/results`}
              className="flex items-center gap-1 text-xs text-orange-500 hover:underline">
              View <ChevronRight size={12} />
            </Link>
          )}
          <button onClick={() => onDelete(item.id)}
            className="p-1.5 text-gray-400 hover:text-red-500 rounded">
            <Trash2 size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
```

**Step 7: Commit**

```bash
git add frontend/components/
git commit -m "feat: add all frontend components"
```

---

## Task 11: Frontend Pages

**Files:**
- Modify: `frontend/app/page.tsx`
- Create: `frontend/app/search/[id]/confirm/page.tsx`
- Create: `frontend/app/search/[id]/results/page.tsx`

**Step 1: Home page**

```tsx
// frontend/app/page.tsx
"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { SearchBar } from "@/components/SearchBar";
import { WatchlistCard } from "@/components/WatchlistCard";
import { SearchHistory } from "@/components/SearchHistory";
import {
  startSearch,
  getWatchlist,
  getSearchHistory,
  removeFromWatchlist,
  refreshWatchlistItem,
  deleteSearch,
} from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [isSearching, setIsSearching] = useState(false);
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);

  const loadData = useCallback(async () => {
    const [wl, hist] = await Promise.all([getWatchlist(), getSearchHistory()]);
    setWatchlist(wl);
    setHistory(hist);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSearch = async (query: string) => {
    setIsSearching(true);
    try {
      const { search_id } = await startSearch(query);
      router.push(`/search/${search_id}/confirm`);
    } catch (err) {
      console.error(err);
      setIsSearching(false);
    }
  };

  const handleDeleteWatchlist = async (id: string) => {
    await removeFromWatchlist(id);
    await loadData();
  };

  const handleRefreshWatchlist = async (id: string) => {
    await refreshWatchlistItem(id);
    await loadData();
  };

  const handleDeleteSearch = async (id: string) => {
    await deleteSearch(id);
    await loadData();
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 py-12 space-y-10">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-gray-900">Amazon Research Tool</h1>
          <p className="text-gray-500">AI-powered product research with review analysis</p>
        </div>

        {/* Search */}
        <SearchBar onSearch={handleSearch} isLoading={isSearching} />

        {/* Watchlist */}
        {watchlist.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold text-gray-800 mb-3">Watchlist</h2>
            <div className="space-y-2">
              {watchlist.map((item) => (
                <WatchlistCard
                  key={item.id}
                  item={item}
                  onDelete={handleDeleteWatchlist}
                  onRefresh={handleRefreshWatchlist}
                />
              ))}
            </div>
          </section>
        )}

        {/* History */}
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Search History</h2>
          <SearchHistory items={history} onDelete={handleDeleteSearch} />
        </section>
      </div>
    </main>
  );
}
```

**Step 2: Confirmation page**

```tsx
// frontend/app/search/[id]/confirm/page.tsx
"use client";
import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { ConfirmationGrid } from "@/components/ConfirmationGrid";
import { ProgressFeed } from "@/components/ProgressFeed";
import { useSSE } from "@/lib/useSSE";
import { confirmProducts } from "@/lib/api";

export default function ConfirmPage() {
  const { id: searchId } = useParams<{ id: string }>();
  const router = useRouter();
  const { events } = useSSE(searchId);
  const [currentBatch, setCurrentBatch] = useState<any[]>([]);
  const [iteration, setIteration] = useState(0);
  const [maxIterations, setMaxIterations] = useState(3);
  const [needsMoreDetail, setNeedsMoreDetail] = useState(false);
  const [isWaiting, setIsWaiting] = useState(false);
  const processedEvents = useRef(new Set<number>());

  useEffect(() => {
    events.forEach((event, idx) => {
      if (processedEvents.current.has(idx)) return;
      processedEvents.current.add(idx);

      if (event.event === "batch_ready") {
        const d = event.data as any;
        setCurrentBatch(d.batch ?? []);
        setIteration(d.iteration ?? 0);
        setMaxIterations(d.max_iterations ?? 3);
        setNeedsMoreDetail(d.needs_more_detail ?? false);
        setIsWaiting(false);
      }
      if (event.event === "complete") {
        router.push(`/search/${searchId}/results`);
      }
    });
  }, [events, router, searchId]);

  const handleConfirm = async (selectedIds: string[]) => {
    setIsWaiting(true);
    await confirmProducts(searchId, selectedIds);
    // If confirmed → will redirect via "complete" event
  };

  const handleNextBatch = async () => {
    setIsWaiting(true);
    await confirmProducts(searchId, []); // empty = reject all
  };

  if (needsMoreDetail) {
    return (
      <main className="max-w-lg mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-semibold text-gray-900">Could not find a match</h2>
        <p className="text-gray-500">
          After {iteration} attempts, we couldn&apos;t find the product you&apos;re looking for.
          Please go back and try a more specific search query.
        </p>
        <a href="/" className="inline-block mt-4 px-5 py-2 bg-orange-500 text-white rounded-lg font-semibold hover:bg-orange-600">
          ← Back to Search
        </a>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <a href="/" className="text-sm text-gray-500 hover:text-gray-700">← Back</a>
      <ProgressFeed events={events} />
      {isWaiting ? (
        <div className="text-center py-16 text-gray-500">Working on it...</div>
      ) : currentBatch.length > 0 ? (
        <ConfirmationGrid
          products={currentBatch}
          iteration={iteration}
          maxIterations={maxIterations}
          onConfirm={handleConfirm}
          onNextBatch={handleNextBatch}
        />
      ) : (
        <div className="text-center py-16 text-gray-400">Searching Amazon...</div>
      )}
    </main>
  );
}
```

**Step 3: Results page**

```tsx
// frontend/app/search/[id]/results/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ProductCard } from "@/components/ProductCard";
import { getResults, addToWatchlist } from "@/lib/api";

export default function ResultsPage() {
  const { id: searchId } = useParams<{ id: string }>();
  const [search, setSearch] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getResults(searchId)
      .then(({ search, products }) => {
        setSearch(search);
        setProducts(products);
      })
      .finally(() => setLoading(false));
  }, [searchId]);

  const handleAddToWatchlist = async (productId: string) => {
    await addToWatchlist(productId);
    alert("Added to watchlist!");
  };

  if (loading) return <div className="text-center py-16 text-gray-400">Loading results...</div>;

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <div className="flex items-center gap-3">
        <a href="/" className="text-sm text-gray-500 hover:text-gray-700">← Back</a>
        <h1 className="text-xl font-bold text-gray-900">
          Results: &quot;{search?.query}&quot;
        </h1>
        <span className="text-sm text-gray-400">{products.length} products</span>
      </div>

      {products.length === 0 ? (
        <p className="text-center text-gray-400 py-16">No results found.</p>
      ) : (
        <div className="space-y-4">
          {products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onAddToWatchlist={handleAddToWatchlist}
            />
          ))}
        </div>
      )}
    </main>
  );
}
```

**Step 4: Run the frontend**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000` — you should see the home page with search bar.

**Step 5: Commit**

```bash
git add frontend/app/
git commit -m "feat: add all frontend pages (home, confirm, results)"
```

---

## Task 12: Create Amazon Scraper Skill

**Files:**
- Create: `docs/skills/amazon-scraper.md`

**Step 1: Create the skill file**

```markdown
# Amazon Scraper Skill

This skill captures patterns and conventions for the Amazon Research Tool project.

## Project Structure

- `backend/` — Python FastAPI + Google ADK agents
- `frontend/` — Next.js + TypeScript
- `backend/scraper/amazon.py` — All Playwright scraping logic
- `backend/agents/orchestrator.py` — Pipeline entry point
- `backend/config.py` — All configurable constants (model, batch sizes, etc.)

## Adding a New Agent

1. Create `backend/agents/your_agent.py` with a class `YourAgent`
2. Add your agent to `OrchestratorAgent` in `backend/agents/orchestrator.py`
3. Emit SSE events using `yield {"event": "status", "data": {...}}` for UI updates

## Changing the LLM Model

Edit `backend/.env`:
\```
OLLAMA_MODEL=llama3.2
\```
All agents share the same model via `config.settings.ollama_model`.

## Changing Scraping Criteria

- Batch size: `AMAZON_BATCH_SIZE` in `.env`
- Max reviews: `MAX_REVIEWS_PER_PRODUCT` in `.env`
- Confirmation retries: `MAX_CONFIRMATION_ITERATIONS` in `.env`

## Adding a New Scraper Field

1. Edit `backend/scraper/amazon.py` — add selector in `search_products()`
2. Add the field to the `products` table in `db/schema.sql`
3. Update `backend/models.py` — add to `ProductBase`
4. Update `frontend/components/ProductCard.tsx` to display it

## Changing the Ranking Criteria

Edit `RANKING_PROMPT` in `backend/agents/ranker_agent.py`. The prompt currently
scores on: value for money, quality, reliability. Change these to match your needs.

## Common Commands

\```bash
# Start backend
cd backend && uv run uvicorn main:app --reload

# Start frontend
cd frontend && npm run dev

# Install a new Python package
cd backend && uv add <pkg>

# Pull a different Ollama model
ollama pull <model-name>
\```

## SSE Event Types

| Event | When | Data |
|-------|------|------|
| `status` | Any status update | `{message, status}` |
| `batch_ready` | New product batch ready | `{batch, iteration, needs_more_detail}` |
| `analysis_done` | One product analyzed | `{product_id, analysis}` |
| `need_more_detail` | Too many failed iterations | `{message}` |
| `complete` | Pipeline finished | `{search_id}` |
| `error` | Something failed | `{message}` |
```

**Step 2: Commit**

```bash
git add docs/
git commit -m "feat: add amazon-scraper skill documentation"
```

---

## End-to-End Verification

Run through this checklist manually after completing all tasks:

1. Start Ollama: `ollama serve` — verify `qwen3:14b` is available
2. Copy `.env.example` to `.env` and set DATABASE_URL for your local Postgres
3. Run schema SQL: `psql amazon_purchase < backend/db/schema.sql`
4. Start backend: `cd backend && uv run uvicorn main:app --reload`
5. Start frontend: `cd frontend && npm run dev`
6. Open `http://localhost:3000`
7. Search for "wireless headphones"
8. SSE progress feed appears
9. Confirmation grid shows 3-5 products with images
10. Select 2 products and click Confirm
11. Progress feed shows review scraping + LLM analysis
12. Redirect to results page with ranked products + scores
13. Click "View on Amazon ↗" — Amazon page opens in new tab
14. Click "+ Watchlist" on a product — added
15. Return home — watchlist shows the product
16. Click refresh on watchlist item — price updates
17. Delete a search from history — it disappears
18. Delete a watchlist item — it disappears

---

## Notes for Modification

- **Change ranking criteria:** Edit `RANKING_PROMPT` in `backend/agents/ranker_agent.py`
- **Add new search filters:** Add fields to `SearchRequest` in `models.py` and pass to `OrchestratorAgent`
- **Change LLM model:** Update `OLLAMA_MODEL` in `.env`
- **Add more product fields:** Update `amazon.py` scraper selectors + `db/schema.sql` + `ProductBase` model
- **Change batch size:** Update `AMAZON_BATCH_SIZE` in `.env`
