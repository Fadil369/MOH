import pytest
from fastapi.testclient import TestClient
from services.financial_rules.main import app
from datetime import date


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_classify_endpoint(client):
    resp = client.post("/classify", json={"rejection_code": "SE-1-10"})
    assert resp.status_code == 200
    assert resp.json()["rejection_type"] == "ADMINISTRATIVE"


def test_classify_endpoint_clinical(client):
    resp = client.post("/classify", json={"rejection_code": "MN-1-1"})
    assert resp.status_code == 200
    assert resp.json()["rejection_type"] == "CLINICAL_DOCUMENTATION"


def test_analyze_endpoint(client):
    claims = [
        {
            "service_line_id": "SL-001",
            "patient_id": "PAT-001",
            "provider_id": "PROV-001",
            "amount_sar": 5000.0,
            "rejection_type": "ADMINISTRATIVE",
            "date_of_service": "2024-01-15",
        },
        {
            "service_line_id": "SL-002",
            "patient_id": "PAT-002",
            "provider_id": "PROV-001",
            "amount_sar": 3000.0,
            "rejection_type": "CLINICAL_DOCUMENTATION",
            "date_of_service": "2024-01-16",
        },
    ]
    resp = client.post("/analyze", json={"claims": claims})
    assert resp.status_code == 200
    data = resp.json()
    assert data["claim_count"] == 2
    assert abs(data["total_rejected_sar"] - 8000.0) < 0.01
