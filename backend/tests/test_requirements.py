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
