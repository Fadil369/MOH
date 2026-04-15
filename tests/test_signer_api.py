import pytest
import io
from fastapi.testclient import TestClient
from services.signer.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_sign_endpoint(client):
    resp = client.post("/sign", json={"payload": {"claim_id": "CL-001"}, "key": "secret"})
    assert resp.status_code == 200
    assert "signature" in resp.json()
    assert len(resp.json()["signature"]) == 64


def test_verify_endpoint_valid(client):
    payload = {"claim_id": "CL-001"}
    key = "my-secret"
    sign_resp = client.post("/sign", json={"payload": payload, "key": key})
    sig = sign_resp.json()["signature"]
    verify_resp = client.post(
        "/verify", json={"payload": payload, "signature": sig, "key": key}
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["valid"] is True


def test_verify_endpoint_invalid(client):
    verify_resp = client.post(
        "/verify",
        json={"payload": {"claim_id": "CL-001"}, "signature": "badsig", "key": "key"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["valid"] is False
