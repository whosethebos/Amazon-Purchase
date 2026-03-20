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
