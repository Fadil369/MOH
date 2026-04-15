import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
from core.models import FHIRBundle
from services.nphies_bridge.main import app, bridge, SUBMISSION_STORE, PORTAL_EXTRACTION_STORE


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_stores():
    SUBMISSION_STORE.clear()
    PORTAL_EXTRACTION_STORE.clear()


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


def test_ingest_portal_extraction(client):
    payload = {
        "source": "oracle",
        "portalUrl": "https://oracle.example/faces/Home",
        "currentUrl": "https://oracle.example/faces/Dashboard",
        "title": "Oracle Dashboard",
        "capturedAt": "2026-04-15T10:00:00Z",
        "auth": {
            "attempted": True,
            "mode": "password",
            "likelySuccessful": True,
        },
        "endpoints": {
            "urls": ["https://oracle.example/api/claims"],
            "processUrls": ["https://oracle.example/api/claims"],
            "ipUrls": ["https://128.1.1.185/prod/faces/Home"],
            "relativePaths": ["/prod/faces/Home"],
            "ids": {"claim": ["CLM-1001"]},
        },
        "links": [
            {
                "text": "Claims",
                "href": "/claims",
                "absoluteUrl": "https://oracle.example/claims",
                "kind": "process",
            }
        ],
        "forms": [
            {
                "tag": "input",
                "type": "text",
                "name": "claimNumber",
                "id": "claim-number",
                "placeholder": "Claim Number",
                "text": "",
            }
        ],
        "tables": [
            {
                "headers": ["Claim", "Status"],
                "rows": [["CLM-1001", "Pending"]],
                "rowCount": 1,
            }
        ],
        "notes": ["Login succeeded"],
        "metadata": {"scanner": "sbs"},
    }

    resp = client.post("/portal-extractions", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "stored"
    assert body["downstream"]["forwarded"] is False
    assert body["downstream"]["reason"] == "webhook-not-configured"
    extraction_id = body["extractionId"]

    stored = client.get(f"/portal-extractions/{extraction_id}")
    assert stored.status_code == 200
    stored_body = stored.json()
    assert stored_body["source"] == "oracle"
    assert stored_body["auth"]["likelySuccessful"] is True
    assert stored_body["endpoints"]["processUrls"] == ["https://oracle.example/api/claims"]


def test_list_portal_extractions_filtered_by_source(client):
    first = {
        "source": "oracle",
        "portalUrl": "https://oracle.example",
        "capturedAt": "2026-04-15T10:00:00Z",
    }
    second = {
        "source": "nphies",
        "portalUrl": "https://portal.nphies.sa",
        "capturedAt": "2026-04-15T10:05:00Z",
    }

    assert client.post("/portal-extractions", json=first).status_code == 200
    assert client.post("/portal-extractions", json=second).status_code == 200

    resp = client.get("/portal-extractions", params={"source": "nphies"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["items"][0]["source"] == "nphies"


def test_get_portal_extraction_missing(client):
    resp = client.get("/portal-extractions/missing-id")
    assert resp.status_code == 404


def test_ingest_portal_extraction_forwards_to_n8n(client, monkeypatch):
    monkeypatch.setenv("N8N_PORTAL_EXTRACTION_WEBHOOK_URL", "https://n8n.example/webhook/extraction")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        payload = {
            "source": "nphies",
            "portalUrl": "https://portal.nphies.sa",
            "capturedAt": "2026-04-15T10:05:00Z",
        }
        resp = client.post("/portal-extractions", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["downstream"]["forwarded"] is True
    assert body["downstream"]["target"] == "n8n"


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
