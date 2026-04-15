import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from integrations.google_chat_bot import GoogleChatBot
from core.models import HITLRequest, RejectionType, NPHIESAction, ClaimLine, ClaimStatus
from datetime import date


@pytest.fixture
def bot():
    return GoogleChatBot()


@pytest.fixture
def hitl_request():
    return HITLRequest(
        claim_id="SL-001",
        amount_sar=15000.0,
        rejection_type=RejectionType.CLINICAL_DOCUMENTATION,
        recommended_action=NPHIESAction.APPEAL,
        agent_assessments={"clinical_score": 0.75, "fraud_risk": 0.1},
    )


@pytest.fixture
def claim():
    return ClaimLine(
        service_line_id="SL-001",
        patient_id="PAT-001",
        provider_id="PROV-001",
        amount_sar=15000.0,
        rejection_code="MN-1-1",
        rejection_type=RejectionType.CLINICAL_DOCUMENTATION,
        date_of_service=date(2024, 1, 15),
    )


def test_create_hitl_card(bot, hitl_request):
    card = bot.create_hitl_card(hitl_request)
    assert "cards" in card
    header = card["cards"][0]["header"]
    assert "SL-001" in header["title"]
    assert "15000" in header["subtitle"]


def test_create_hitl_card_has_buttons(bot, hitl_request):
    card = bot.create_hitl_card(hitl_request)
    widgets = card["cards"][0]["sections"][0]["widgets"]
    button_widget = next(w for w in widgets if "buttons" in w)
    buttons = button_widget["buttons"]
    assert any(b["textButton"]["text"] == "APPROVE" for b in buttons)
    assert any(b["textButton"]["text"] == "REJECT" for b in buttons)


@pytest.mark.asyncio
async def test_send_review_request(bot, hitl_request):
    mock_response = MagicMock()
    mock_response.json.return_value = {"thread": {"name": "spaces/xxx/threads/yyy"}}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await bot.send_review_request(
            "https://chat.googleapis.com/webhook", hitl_request
        )
        assert "thread" in result


def test_parse_response_approve(bot):
    response = {"action": {"actionMethodName": "approve"}}
    result = bot.parse_response(response)
    assert result["approved"] is True
    assert result["decision"] == "approve"


def test_parse_response_reject(bot):
    response = {"action": {"actionMethodName": "reject"}}
    result = bot.parse_response(response)
    assert result["approved"] is False


def test_format_claim_summary(bot, claim):
    summary = bot.format_claim_summary(claim, {"clinical": "Score: 0.8"})
    assert "SL-001" in summary
    assert "15000" in summary
    assert "MN-1-1" in summary
