import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from services.nphies_bridge.main import NPHIESBridge
from core.models import FHIRBundle


@pytest.fixture
def bridge():
    return NPHIESBridge(nphies_url="https://test.nphies.sa/api")


@pytest.fixture
def sample_bundle():
    return FHIRBundle(
        id="BUNDLE-TEST-001",
        type="collection",
        entry=[{"resource": {"resourceType": "Claim", "id": "CL-001"}}],
    )


@pytest.mark.asyncio
async def test_submit_claim_success(bridge, sample_bundle):
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "accepted", "id": "RESP-001"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await bridge.submit_claim(sample_bundle)
        assert result["status"] == "accepted"


@pytest.mark.asyncio
async def test_submit_appeal_success(bridge, sample_bundle):
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "appeal_accepted"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await bridge.submit_appeal(sample_bundle)
        assert "appeal_accepted" in result["status"]


@pytest.mark.asyncio
async def test_check_status_from_store(bridge, sample_bundle):
    from services.nphies_bridge.main import SUBMISSION_STORE

    SUBMISSION_STORE["BUNDLE-TEST-001"] = {"status": "submitted"}
    result = await bridge.check_status("BUNDLE-TEST-001")
    assert result["status"] == "submitted"


@pytest.mark.asyncio
async def test_submit_claim_http_error(bridge, sample_bundle):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock()
        )
        with pytest.raises(httpx.HTTPStatusError):
            await bridge.submit_claim(sample_bundle)
