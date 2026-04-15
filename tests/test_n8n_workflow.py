import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock
from integrations.n8n_workflow import N8NOrchestrator
from core.models import ClaimLine, RejectionType, ClaimStatus


@pytest.fixture
def orchestrator():
    return N8NOrchestrator(n8n_url="http://test-n8n:5678")


@pytest.fixture
def sample_claims():
    return [
        ClaimLine(
            service_line_id=f"SL-N8N-{i:03d}",
            patient_id=f"PAT-{i:05d}",
            provider_id="PROV-001",
            amount_sar=float(i * 1000),
            date_of_service=date(2024, 1, i + 1),
        )
        for i in range(1, 4)
    ]


@pytest.mark.asyncio
async def test_trigger_daily_batch(orchestrator):
    mock_response = MagicMock()
    mock_response.json.return_value = {"execution_id": "EXEC-001", "status": "running"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await orchestrator.trigger_daily_batch(
            "http://test-n8n:5678", date(2024, 1, 15)
        )
        assert result["execution_id"] == "EXEC-001"


@pytest.mark.asyncio
async def test_get_workflow_status(orchestrator):
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "EXEC-001", "status": "finished"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await orchestrator.get_workflow_status("EXEC-001")
        assert result["status"] == "finished"


def test_schedule_batch(orchestrator, sample_claims):
    result = orchestrator.schedule_batch(sample_claims)
    assert result["batch_size"] == 3
    assert result["scheduled"] is True
    assert result["total_amount_sar"] == 6000.0
    assert len(result["claim_ids"]) == 3
