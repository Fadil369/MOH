import pytest
import io
from fastapi.testclient import TestClient
from services.normalizer.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ingest_endpoint(client):
    csv_content = (
        "service_line_id,patient_id,amount_sar\n"
        "SL-001,PAT-001,5000.0\n"
        "SL-002,PAT-002,3000.0\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post("/ingest", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"] == 2
    assert "service_line_id" in data["columns"]
