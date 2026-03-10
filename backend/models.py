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
