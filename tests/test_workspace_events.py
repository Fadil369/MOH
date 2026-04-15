"""Tests for integrations/workspace_events.py"""

import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from integrations.workspace_events import (
    WorkspaceEventsClient,
    CE_TYPE_MESSAGE_CREATED,
    CE_TYPE_SUBSCRIPTION_EXPIRY,
)
from integrations.vertex_ai import VertexAIClient


@pytest.fixture
def vertex():
    return VertexAIClient(project_id="test-project")


@pytest.fixture
def client(vertex):
    return WorkspaceEventsClient(
        pubsub_topic_id="projects/p/topics/t",
        pubsub_subscription_id="projects/p/subscriptions/s",
        vertex_ai_client=vertex,
    )


# ------------------------------------------------------------------
# Subscription lifecycle
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_space_subscription(client):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": {"name": "subscriptions/SUB123"}}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        sub_name = await client.create_space_subscription("spaces/ABC", "tok")

    assert sub_name == "subscriptions/SUB123"


@pytest.mark.asyncio
async def test_renew_subscription(client):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.patch", new_callable=AsyncMock, return_value=mock_resp):
        await client.renew_subscription("subscriptions/SUB123", "tok")  # no exception


@pytest.mark.asyncio
async def test_delete_subscription(client):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.delete", new_callable=AsyncMock, return_value=mock_resp):
        await client.delete_subscription("subscriptions/SUB123", "tok")  # no exception


# ------------------------------------------------------------------
# Pub/Sub processing – expiry renewal
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_subscription_renewal(client):
    sub_data = {"subscription": {"name": "subscriptions/EXP"}}
    encoded = base64.b64encode(json.dumps(sub_data).encode()).decode()
    pubsub_payload = {
        "receivedMessages": [
            {
                "ackId": "ack1",
                "message": {
                    "attributes": {"ce-type": CE_TYPE_SUBSCRIPTION_EXPIRY},
                    "data": encoded,
                },
            }
        ]
    }
    pull_resp = MagicMock()
    pull_resp.raise_for_status = MagicMock()
    pull_resp.json.return_value = pubsub_payload

    patch_resp = MagicMock()
    patch_resp.raise_for_status = MagicMock()

    ack_resp = MagicMock()
    ack_resp.raise_for_status = MagicMock()

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=[pull_resp, ack_resp]),
        patch("httpx.AsyncClient.patch", new_callable=AsyncMock, return_value=patch_resp),
    ):
        results = await client.process_subscription("tok", "chat_tok")

    assert results[0]["type"] == "renewal"
    assert results[0]["subscription"] == "subscriptions/EXP"


# ------------------------------------------------------------------
# Pub/Sub processing – inclusive message
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_subscription_inclusive_message(client, vertex):
    msg_data = {
        "message": {
            "sender": {"type": "HUMAN"},
            "text": "Great work everyone",
            "space": {"name": "spaces/XYZ"},
        }
    }
    encoded = base64.b64encode(json.dumps(msg_data).encode()).decode()
    pubsub_payload = {
        "receivedMessages": [
            {
                "ackId": "ack2",
                "message": {
                    "attributes": {"ce-type": CE_TYPE_MESSAGE_CREATED},
                    "data": encoded,
                },
            }
        ]
    }
    pull_resp = MagicMock()
    pull_resp.raise_for_status = MagicMock()
    pull_resp.json.return_value = pubsub_payload

    ack_resp = MagicMock()
    ack_resp.raise_for_status = MagicMock()

    # Vertex AI returns "It's inclusive!" – no warning card posted
    vertex.get_inclusivity_feedback = AsyncMock(return_value="It's inclusive!")

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=[pull_resp, ack_resp],
    ):
        results = await client.process_subscription("tok", "chat_tok")

    assert results[0]["inclusive"] is True


# ------------------------------------------------------------------
# Pub/Sub processing – non-inclusive message → warning card posted
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_subscription_non_inclusive_message(client, vertex):
    msg_data = {
        "message": {
            "sender": {"type": "HUMAN"},
            "text": "Hey guys, man up",
            "space": {"name": "spaces/XYZ"},
        }
    }
    encoded = base64.b64encode(json.dumps(msg_data).encode()).decode()
    pubsub_payload = {
        "receivedMessages": [
            {
                "ackId": "ack3",
                "message": {
                    "attributes": {"ce-type": CE_TYPE_MESSAGE_CREATED},
                    "data": encoded,
                },
            }
        ]
    }
    pull_resp = MagicMock()
    pull_resp.raise_for_status = MagicMock()
    pull_resp.json.return_value = pubsub_payload

    warning_resp = MagicMock()
    warning_resp.raise_for_status = MagicMock()

    ack_resp = MagicMock()
    ack_resp.raise_for_status = MagicMock()

    vertex.get_inclusivity_feedback = AsyncMock(return_value="guys, man up")

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=[pull_resp, warning_resp, ack_resp],
    ):
        results = await client.process_subscription("tok", "chat_tok")

    assert results[0]["inclusive"] is False
    assert "guys" in results[0]["feedback"]


# ------------------------------------------------------------------
# Pub/Sub processing – bot message skipped
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_subscription_bot_message_skipped(client):
    msg_data = {
        "message": {
            "sender": {"type": "BOT"},
            "text": "Automated notice",
            "space": {"name": "spaces/XYZ"},
        }
    }
    encoded = base64.b64encode(json.dumps(msg_data).encode()).decode()
    pubsub_payload = {
        "receivedMessages": [
            {
                "ackId": "ack4",
                "message": {
                    "attributes": {"ce-type": CE_TYPE_MESSAGE_CREATED},
                    "data": encoded,
                },
            }
        ]
    }
    pull_resp = MagicMock()
    pull_resp.raise_for_status = MagicMock()
    pull_resp.json.return_value = pubsub_payload

    ack_resp = MagicMock()
    ack_resp.raise_for_status = MagicMock()

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=[pull_resp, ack_resp],
    ):
        results = await client.process_subscription("tok", "chat_tok")

    assert results[0]["skipped"] is True


# ------------------------------------------------------------------
# Unknown event type
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_subscription_unknown_event(client):
    pubsub_payload = {
        "receivedMessages": [
            {
                "ackId": "ack5",
                "message": {
                    "attributes": {"ce-type": "google.workspace.unknown"},
                    "data": base64.b64encode(b"{}").decode(),
                },
            }
        ]
    }
    pull_resp = MagicMock()
    pull_resp.raise_for_status = MagicMock()
    pull_resp.json.return_value = pubsub_payload

    ack_resp = MagicMock()
    ack_resp.raise_for_status = MagicMock()

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=[pull_resp, ack_resp],
    ):
        results = await client.process_subscription("tok", "chat_tok")

    assert results[0]["type"] == "unknown"
