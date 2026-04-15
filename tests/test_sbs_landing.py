import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from services.sbs_landing.main import app
from core.models import RejectionType, ClaimStatus
from datetime import date


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_dashboard(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "operational"
    assert "normalizer" in data["services"]


def test_process_claims(client):
    claims = [
        {
            "service_line_id": "SL-P-001",
            "patient_id": "PAT-001",
            "provider_id": "PROV-001",
            "amount_sar": 3000.0,
            "rejection_code": "SE-1-10",
            "rejection_type": "ADMINISTRATIVE",
            "date_of_service": "2024-01-15",
        }
    ]
    resp = client.post("/process", json={"claims": claims})
    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] == 1
    assert "routes" in data
    assert "hitl_required" in data


def test_process_claims_hitl_triggered(client):
    claims = [
        {
            "service_line_id": "SL-BIG",
            "patient_id": "PAT-001",
            "provider_id": "PROV-001",
            "amount_sar": 25000.0,
            "rejection_code": "MN-1-1",
            "date_of_service": "2024-01-15",
        }
    ]
    resp = client.post("/process", json={"claims": claims})
    assert resp.status_code == 200
    data = resp.json()
    assert "SL-BIG" in data["hitl_required"]


def test_process_claims_no_rejection_type(client):
    """Claims without rejection_type get classified from rejection_code."""
    claims = [
        {
            "service_line_id": "SL-P-002",
            "patient_id": "PAT-002",
            "provider_id": "PROV-001",
            "amount_sar": 1000.0,
            "rejection_code": "BE-1-4",
            "date_of_service": "2024-01-16",
        }
    ]
    resp = client.post("/process", json={"claims": claims})
    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] == 1
