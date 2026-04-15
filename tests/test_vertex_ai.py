"""Tests for integrations/vertex_ai.py"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from integrations.vertex_ai import VertexAIClient, DEFAULT_LOCATION, GEMINI_MODEL


@pytest.fixture
def vertex():
    return VertexAIClient(project_id="my-project", location_id="us-central1")


def test_endpoint_format(vertex):
    ep = vertex._endpoint()
    expected_host = f"{DEFAULT_LOCATION}-aiplatform.googleapis.com"
    assert ep.startswith(f"https://{expected_host}/")
    assert "my-project" in ep
    assert GEMINI_MODEL in ep


def test_build_request_contains_prompt(vertex):
    req = vertex._build_request("Hello world")
    assert req["contents"]["parts"]["text"] == "Hello world"
    assert "generationConfig" in req
    assert req["generationConfig"]["temperature"] == 0.2


@pytest.mark.asyncio
async def test_summarize_space(vertex):
    api_resp = {
        "candidates": [{"content": {"parts": [{"text": "Summary of conversation."}]}}]
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = api_resp

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await vertex.summarize_space("Alice: hello\nBob: hi", "tok")

    assert result == "Summary of conversation."


@pytest.mark.asyncio
async def test_get_inclusivity_feedback_inclusive(vertex):
    api_resp = {
        "candidates": [{"content": {"parts": [{"text": "It's inclusive!"}]}}]
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = api_resp

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await vertex.get_inclusivity_feedback("Great teamwork!", "tok")

    assert result == "It's inclusive!"


@pytest.mark.asyncio
async def test_get_inclusivity_feedback_non_inclusive(vertex):
    api_resp = {
        "candidates": [{"content": {"parts": [{"text": "guys, man up"}]}}]
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = api_resp

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await vertex.get_inclusivity_feedback("Hey guys, man up", "tok")

    assert "guys" in result
    assert result != "It's inclusive!"


@pytest.mark.asyncio
async def test_summarize_space_prompt_content(vertex):
    """Verify the summarisation prompt contains the conversation history."""
    captured_payload = {}

    async def capture_post(url, **kwargs):
        captured_payload.update(kwargs.get("json", {}))
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
        }
        return m

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=capture_post):
        await vertex.summarize_space("Alice: test", "tok")

    prompt = captured_payload["contents"]["parts"]["text"]
    assert "Alice: test" in prompt
    assert "Summarize" in prompt
