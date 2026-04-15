import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from integrations.google_chat_bot import GoogleChatBot, CREATE_COMMAND_ID, CLOSE_COMMAND_ID
from integrations.issue_store import IssueStore
from core.models import (
    HITLRequest,
    RejectionType,
    NPHIESAction,
    ClaimLine,
    ClaimStatus,
    ClaimIssue,
    IssueStatus,
)
from datetime import date


@pytest.fixture
def store():
    return IssueStore()


@pytest.fixture
def bot(store):
    return GoogleChatBot(store=store)


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


# -----------------------------------------------------------------------
# HITL card tests (original behaviour preserved)
# -----------------------------------------------------------------------

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


# -----------------------------------------------------------------------
# Issue lifecycle tests
# -----------------------------------------------------------------------

def test_handle_message_no_slash_command(bot):
    event = {"message": {"text": "hello"}}
    resp = bot.handle_message(event)
    assert "slash commands" in resp["text"].lower()


def test_handle_message_slash_create(bot):
    event = {
        "message": {
            "slashCommand": {"commandId": CREATE_COMMAND_ID},
            "space": {"type": "SPACE"},
        }
    }
    resp = bot.handle_message(event)
    assert resp["actionResponse"]["type"] == "DIALOG"


def test_handle_message_slash_close_no_space(bot):
    event = {
        "message": {
            "slashCommand": {"commandId": CLOSE_COMMAND_ID},
            "space": {"type": "DM"},
            "argumentText": "",
        }
    }
    resp = bot.handle_message(event)
    assert "isn't supported" in resp["text"]


def test_close_slash_command_unknown_space(bot):
    event = {
        "message": {
            "slashCommand": {"commandId": CLOSE_COMMAND_ID},
            "space": {"type": "SPACE", "name": "spaces/UNKNOWN"},
            "argumentText": "resolved",
        }
    }
    resp = bot.process_slash_command(event)
    assert "No issue found" in resp["text"]


def test_close_slash_command_known_space(bot, store):
    issue = ClaimIssue(
        title="Test Issue",
        description="A test",
        space_id="spaces/KNOWN",
    )
    store.save(issue)
    event = {
        "message": {
            "slashCommand": {"commandId": CLOSE_COMMAND_ID},
            "space": {"type": "SPACE", "name": "spaces/KNOWN"},
            "argumentText": "Fixed",
        }
    }
    resp = bot.process_slash_command(event)
    assert "closed" in resp["text"].lower()
    assert store.get("spaces/KNOWN").status == IssueStatus.CLOSED


def test_handle_card_clicked_create_issue(bot):
    event = {
        "action": {"actionMethodName": "createIssue"},
        "common": {
            "formInputs": {
                "title": {"": {"stringInputs": {"value": ["Claim SAR 50K"]}}},
                "description": {"": {"stringInputs": {"value": ["Rejected BE-1-4"]}}},
            }
        },
    }
    resp = bot.handle_card_clicked(event)
    assert "Claim SAR 50K" in resp["text"]


def test_handle_card_clicked_approve(bot):
    event = {"action": {"actionMethodName": "approve"}}
    result = bot.handle_card_clicked(event)
    assert result["approved"] is True


def test_handle_card_clicked_unknown(bot):
    event = {"action": {"actionMethodName": "unknown_action"}}
    resp = bot.handle_card_clicked(event)
    assert "Unknown" in resp["text"]


# -----------------------------------------------------------------------
# App Home tests
# -----------------------------------------------------------------------

def test_build_app_home_empty(bot):
    card = bot.build_app_home_card()
    sections = card["action"]["navigations"][0]["push_card"]["sections"]
    assert sections == []


def test_build_app_home_with_issues(bot, store):
    store.save(ClaimIssue(title="Issue A", description="Desc A", space_id="spaces/A"))
    store.save(
        ClaimIssue(
            title="Issue B",
            description="Desc B",
            space_id="spaces/B",
            status=IssueStatus.CLOSED,
            report_url="https://docs.google.com/report",
        )
    )
    card = bot.build_app_home_card()
    sections = card["action"]["navigations"][0]["push_card"]["sections"]
    assert len(sections) == 2
    headers = [s["header"] for s in sections]
    assert any("Issue A" in h for h in headers)
    assert any("Issue B" in h for h in headers)


def test_build_app_home_report_button_only_when_url(bot, store):
    store.save(ClaimIssue(title="No Report", description="X", space_id="spaces/NR"))
    card = bot.build_app_home_card()
    section = card["action"]["navigations"][0]["push_card"]["sections"][0]
    buttons = section["widgets"][-1]["buttonList"]["buttons"]
    labels = [b["text"] for b in buttons]
    assert "Open Space" in labels
    assert "Open Report" not in labels


# -----------------------------------------------------------------------
# Async Chat-API methods (mocked)
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_issue_space(bot):
    async def mock_post(url, **kwargs):
        m = MagicMock()
        m.raise_for_status = MagicMock()
        if "setup" in url:
            m.json.return_value = {"name": "spaces/NEWSPACE"}
        else:
            m.json.return_value = {}
        return m

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post):
        issue = await bot.create_issue_space(
            title="NPHIES Appeal",
            description="Missing preauth BE-1-4",
            chat_api_token="tok",
            claim_line_id="SL-9999",
        )
    assert issue.space_id == "spaces/NEWSPACE"
    assert issue.title == "NPHIES Appeal"
    assert bot._store.get("spaces/NEWSPACE") is not None


@pytest.mark.asyncio
async def test_export_space_history(bot):
    messages_json = {
        "messages": [
            {"sender": {"displayName": "Alice"}, "text": "Checking claim"},
            {"sender": {"displayName": "Bot"}, "text": "ok", "slashCommand": {}},
            {"sender": {"displayName": "Bob"}, "text": "Approved"},
        ]
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = messages_json

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        history = await bot.export_space_history("spaces/XYZ", "tok")

    assert "Alice: Checking claim" in history
    assert "Bob: Approved" in history
    assert "slashCommand" not in history


@pytest.mark.asyncio
async def test_close_issue_async(bot, store):
    issue = ClaimIssue(
        title="Open Issue", description="desc", space_id="spaces/CI"
    )
    store.save(issue)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        updated = await bot.close_issue(
            space_id="spaces/CI",
            resolution="Preauth obtained",
            report_url="https://docs.google.com/xxx",
            chat_api_token="tok",
        )

    assert updated.status == IssueStatus.CLOSED
    assert updated.report_url == "https://docs.google.com/xxx"


@pytest.mark.asyncio
async def test_close_issue_async_unknown_space(bot):
    result = await bot.close_issue("spaces/NONE", "res", "url", "tok")
    assert result is None

