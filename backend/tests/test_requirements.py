# backend/tests/test_requirements.py
"""Tests for requirements field plumbing: models, db client, and API endpoint."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from models import SearchRequest
from db.supabase_client import create_search


def test_search_request_accepts_requirements():
    req = SearchRequest(query="desk", requirements=["60 inch", "under $300"])
    assert req.requirements == ["60 inch", "under $300"]


def test_search_request_requirements_defaults_to_empty():
    req = SearchRequest(query="desk")
    assert req.requirements == []


def test_create_search_passes_requirements_to_db():
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "abc123", "query": "desk", "max_results": 10, "requirements": ["60 inch"]}
    ]
    with patch("db.supabase_client.get_client", return_value=mock_client):
        result = create_search("desk", 10, ["60 inch"])
    insert_call = mock_client.table.return_value.insert.call_args[0][0]
    assert insert_call["requirements"] == ["60 inch"]
    assert result["id"] == "abc123"


def test_create_search_requirements_defaults_to_empty():
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "abc123", "query": "desk", "max_results": 10, "requirements": []}
    ]
    with patch("db.supabase_client.get_client", return_value=mock_client):
        result = create_search("desk", 10)
    insert_call = mock_client.table.return_value.insert.call_args[0][0]
    assert insert_call["requirements"] == []


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


import pytest
from unittest.mock import AsyncMock, patch
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

    # Base prompt uses REVIEW_ANALYSIS_PROMPT.format() — check no requirements block
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

    def fake_create_search(query, max_results, requirements=None):
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
