import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
from core.models import FHIRBundle
from services.nphies_bridge.main import app, bridge, SUBMISSION_STORE


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def bundle_payload():
    return {
        "id": "BUNDLE-API-001",
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": {"resourceType": "Claim", "id": "CL-API-001"}}],
        "timestamp": "2024-01-15T10:00:00",
    }


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_status_from_store(client):
    SUBMISSION_STORE["BUNDLE-STORED"] = {"status": "submitted"}
    resp = client.get("/status/BUNDLE-STORED")
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"


@pytest.mark.asyncio
async def test_submit_endpoint_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "accepted"}
    mock_response.raise_for_status = MagicMock()

    bundle = FHIRBundle(
        id="BUNDLE-API-002",
        type="collection",
        entry=[{"resource": {"resourceType": "Claim", "id": "CL-002"}}],
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await bridge.submit_claim(bundle)
        assert result["status"] == "accepted"


@pytest.mark.asyncio
async def test_check_status_api_fallback():
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "pending"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await bridge.check_status("NONEXISTENT-CLAIM")
        assert result["status"] == "pending"
