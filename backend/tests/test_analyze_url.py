# backend/tests/test_analyze_url.py
import pytest
from scraper.amazon import _sort_products_by_rating, extract_asin as _extract_asin


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


from unittest.mock import AsyncMock, patch
from llm.analyze import run_llm_analysis, _LLM_FALLBACK


# ── run_llm_analysis ────────────────────────────────────────────────────────────

async def test_run_llm_analysis_fallback_on_exception():
    """When chat_json raises, run_llm_analysis returns the empty fallback."""
    with patch("llm.analyze.chat_json", new=AsyncMock(side_effect=Exception("LLM down"))):
        result = await run_llm_analysis("Test Product", [], histogram={"5": 0.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0}, review_count=None)
    assert result == _LLM_FALLBACK


async def test_run_llm_analysis_fallback_on_json_decode_error():
    """When chat_json raises JSONDecodeError, run_llm_analysis returns fallback."""
    import json
    with patch("llm.analyze.chat_json", new=AsyncMock(side_effect=json.JSONDecodeError("bad", "", 0))):
        result = await run_llm_analysis("Test Product", [{"stars": 5, "title": "Good", "body": "Nice"}], histogram={"5": 100.0, "4": 0.0, "3": 0.0, "2": 0.0, "1": 0.0}, review_count=1)
    assert result == _LLM_FALLBACK


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
