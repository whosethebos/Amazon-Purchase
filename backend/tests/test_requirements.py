# backend/tests/test_requirements.py
"""Tests for requirements field plumbing: models, db client, and API endpoint."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from models import SearchRequest
from db.postgres_client import create_search


def test_search_request_accepts_requirements():
    req = SearchRequest(query="desk", requirements=["60 inch", "under $300"])
    assert req.requirements == ["60 inch", "under $300"]


def test_search_request_requirements_defaults_to_empty():
    req = SearchRequest(query="desk")
    assert req.requirements == []


def _make_mock_pool(fetchone_return: dict):
    """Build a mock pool that simulates async with pool.connection() as conn."""
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=fetchone_return)

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.connection = MagicMock(return_value=mock_cm)
    return mock_pool, mock_conn


@pytest.mark.asyncio
async def test_create_search_passes_requirements_to_db():
    expected_row = {"id": "abc123", "query": "desk", "max_results": 10, "requirements": ["60 inch"]}
    mock_pool, mock_conn = _make_mock_pool(expected_row)

    with patch("db.postgres_client.get_pool", return_value=mock_pool):
        result = await create_search("desk", 10, ["60 inch"])

    sql, params = mock_conn.execute.call_args[0]
    assert "INSERT INTO searches" in sql
    assert result["id"] == "abc123"


@pytest.mark.asyncio
async def test_create_search_requirements_defaults_to_empty():
    expected_row = {"id": "abc123", "query": "desk", "max_results": 10, "requirements": []}
    mock_pool, mock_conn = _make_mock_pool(expected_row)

    with patch("db.postgres_client.get_pool", return_value=mock_pool):
        result = await create_search("desk", 10)

    sql, params = mock_conn.execute.call_args[0]
    assert "INSERT INTO searches" in sql
    assert result["requirements"] == []


from agents.orchestrator import OrchestratorAgent


def test_orchestrator_stores_requirements():
    orch = OrchestratorAgent("sid1", "desk", ["60 inch", "solid wood"])
    assert orch.requirements == ["60 inch", "solid wood"]


def test_orchestrator_requirements_defaults_to_empty():
    orch = OrchestratorAgent("sid1", "desk")
    assert orch.requirements == []


def test_orchestrator_requirements_none_becomes_empty():
    orch = OrchestratorAgent("sid1", "desk", None)
    assert orch.requirements == []


from agents.analyst_agent import ReviewAnalystAgent


@pytest.mark.asyncio
async def test_analyst_uses_requirements_in_prompt():
    agent = ReviewAnalystAgent()
    reviews = [{"rating": 5, "title": "Great", "body": "Love it"}]
    captured_prompt = {}

    async def fake_chat_json(messages):
        captured_prompt["content"] = messages[0]["content"]
        return {"summary": "ok", "pros": [], "cons": [], "sentiment": "positive"}

    with patch("agents.analyst_agent.chat_json", new=fake_chat_json):
        await agent.analyze("Standing Desk", reviews, ["60 inch width", "solid wood"])

    assert "60 inch width" in captured_prompt["content"]
    assert "solid wood" in captured_prompt["content"]


@pytest.mark.asyncio
async def test_analyst_no_requirements_uses_base_prompt():
    agent = ReviewAnalystAgent()
    reviews = [{"rating": 5, "title": "Great", "body": "Love it"}]
    captured_prompt = {}

    async def fake_chat_json(messages):
        captured_prompt["content"] = messages[0]["content"]
        return {"summary": "ok", "pros": [], "cons": [], "sentiment": "positive"}

    with patch("agents.analyst_agent.chat_json", new=fake_chat_json):
        await agent.analyze("Standing Desk", reviews)

    assert "user requirements" not in captured_prompt["content"]


from agents.ranker_agent import RankerAgent


@pytest.mark.asyncio
async def test_ranker_appends_requirements_to_prompt():
    agent = RankerAgent()
    products = [{"asin": "B001", "title": "Desk", "price": 200, "rating": 4.5, "review_count": 100}]
    analyses = {"B001": {"summary": "Good desk", "pros": ["sturdy"], "cons": []}}
    captured_prompt = {}

    async def fake_chat_json(messages):
        captured_prompt["content"] = messages[0]["content"]
        return {"rankings": [{"asin": "B001", "score": 80, "rank": 1}]}

    with patch("agents.ranker_agent.chat_json", new=fake_chat_json):
        await agent.rank(products, analyses, ["60 inch width"])

    assert "60 inch width" in captured_prompt["content"]
    assert "user requirements" in captured_prompt["content"]


@pytest.mark.asyncio
async def test_ranker_no_requirements_uses_base_prompt():
    agent = RankerAgent()
    products = [{"asin": "B001", "title": "Desk", "price": 200, "rating": 4.5, "review_count": 100}]
    analyses = {"B001": {"summary": "Good desk", "pros": ["sturdy"], "cons": []}}
    captured_prompt = {}

    async def fake_chat_json(messages):
        captured_prompt["content"] = messages[0]["content"]
        return {"rankings": [{"asin": "B001", "score": 80, "rank": 1}]}

    with patch("agents.ranker_agent.chat_json", new=fake_chat_json):
        await agent.rank(products, analyses)

    assert "user requirements" not in captured_prompt["content"]


from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_search_endpoint_passes_requirements_to_orchestrator():
    """Verify that POST /api/search forwards requirements to OrchestratorAgent."""
    created_with = {}

    async def fake_create_search(query, max_results, requirements=None):
        created_with["requirements"] = requirements
        return {"id": "11111111-1111-1111-1111-111111111111", "query": query}

    captured_orchestrator = {}

    class FakeOrchestrator:
        def __init__(self, search_id, query, requirements=None):
            captured_orchestrator["requirements"] = requirements

        async def run(self):
            return
            yield  # make it a generator

    with (
        patch("main.db.create_search", side_effect=fake_create_search),
        patch("main.OrchestratorAgent", FakeOrchestrator),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/search",
                json={"query": "desk", "requirements": ["60 inch", "solid wood"]},
            )

    assert resp.status_code == 200
    assert created_with["requirements"] == ["60 inch", "solid wood"]
    assert captured_orchestrator["requirements"] == ["60 inch", "solid wood"]
