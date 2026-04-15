"""
Google Workspace Events integration for real-time Chat space monitoring.

Adapted from the Apps Script ``WorkspaceEvent.js`` in
https://github.com/googleworkspace/google-chat-samples/tree/62dd4336f/
apps-script/issue-management-app/4-inclusivity-help

Provides:
* ``create_space_subscription`` – subscribe to message-created events via
  the Workspace Events API + deliver to a Pub/Sub topic.
* ``process_subscription`` – pull + process up to N events from Pub/Sub,
  running the Gemini inclusivity check on every human message.
* ``renew_subscription`` / ``delete_subscription`` – lifecycle helpers.
"""

from __future__ import annotations

import base64
import json

import httpx

from integrations.vertex_ai import VertexAIClient

WORKSPACE_EVENTS_BASE = "https://workspaceevents.googleapis.com/v1"
PUBSUB_BASE = "https://pubsub.googleapis.com/v1"

CE_TYPE_MESSAGE_CREATED = "google.workspace.chat.message.v1.created"
CE_TYPE_SUBSCRIPTION_EXPIRY = (
    "google.workspace.events.subscription.v1.expirationReminder"
)


class WorkspaceEventsClient:
    """Async client for Google Workspace Events + Pub/Sub subscription management."""

    def __init__(
        self,
        pubsub_topic_id: str = "",
        pubsub_subscription_id: str = "",
        vertex_ai_client: VertexAIClient | None = None,
    ) -> None:
        self.pubsub_topic_id = pubsub_topic_id
        self.pubsub_subscription_id = pubsub_subscription_id
        self._vertex = vertex_ai_client or VertexAIClient()

    # ------------------------------------------------------------------
    # Subscription lifecycle
    # ------------------------------------------------------------------

    async def create_space_subscription(
        self, space_id: str, oauth_token: str
    ) -> str:
        """
        Subscribe to message-created events in *space_id* via the
        Workspace Events API.  Returns the subscription resource name.
        """
        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "targetResource": f"//chat.googleapis.com/{space_id}",
            "eventTypes": [CE_TYPE_MESSAGE_CREATED],
            "notificationEndpoint": {"pubsubTopic": self.pubsub_topic_id},
            "payloadOptions": {"includeResource": True},
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{WORKSPACE_EVENTS_BASE}/subscriptions",
                headers=headers,
                json=payload,
                timeout=15.0,
            )
            resp.raise_for_status()
            operation = resp.json()
        return operation.get("response", {}).get("name", "")

    async def renew_subscription(
        self, subscription_id: str, oauth_token: str
    ) -> None:
        """Renew a near-expiry subscription using the default TTL."""
        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{WORKSPACE_EVENTS_BASE}/{subscription_id}",
                headers=headers,
                json={"ttl": "0s"},
                timeout=15.0,
            )
            resp.raise_for_status()

    async def delete_subscription(
        self, subscription_id: str, oauth_token: str
    ) -> None:
        """Delete a subscription when an issue space is closed."""
        headers = {"Authorization": f"Bearer {oauth_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{WORKSPACE_EVENTS_BASE}/{subscription_id}",
                headers=headers,
                timeout=15.0,
            )
            resp.raise_for_status()

    # ------------------------------------------------------------------
    # Pub/Sub event processing
    # ------------------------------------------------------------------

    async def process_subscription(
        self,
        oauth_token: str,
        chat_api_token: str,
        max_messages: int = 10,
    ) -> list[dict]:
        """
        Pull up to *max_messages* events from Pub/Sub, process each one,
        and acknowledge them.

        For every human message event the Gemini inclusivity check is run.
        If non-inclusive language is detected the bot posts a warning card
        back to the space.

        Returns a list of processing results for observability / testing.
        """
        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            pull_resp = await client.post(
                f"{PUBSUB_BASE}/{self.pubsub_subscription_id}:pull",
                headers=headers,
                json={"maxMessages": max_messages},
                timeout=15.0,
            )
            pull_resp.raise_for_status()
            received = pull_resp.json().get("receivedMessages", [])

            results = []
            for item in received:
                result = await self._handle_pubsub_message(
                    item, oauth_token, chat_api_token, client
                )
                results.append(result)

                # Acknowledge the message so it isn't re-delivered.
                ack_resp = await client.post(
                    f"{PUBSUB_BASE}/{self.pubsub_subscription_id}:acknowledge",
                    headers=headers,
                    json={"ackIds": [item["ackId"]]},
                    timeout=15.0,
                )
                ack_resp.raise_for_status()

        return results

    async def _handle_pubsub_message(
        self,
        item: dict,
        oauth_token: str,
        chat_api_token: str,
        client: httpx.AsyncClient,
    ) -> dict:
        """Dispatch a single Pub/Sub message to the appropriate handler."""
        msg = item.get("message", {})
        ce_type = msg.get("attributes", {}).get("ce-type", "")
        raw_data = msg.get("data", "")
        data_str = base64.b64decode(raw_data).decode("utf-8") if raw_data else "{}"
        data = json.loads(data_str)

        if ce_type == CE_TYPE_SUBSCRIPTION_EXPIRY:
            sub_name = data.get("subscription", {}).get("name", "")
            await self.renew_subscription(sub_name, oauth_token)
            return {"type": "renewal", "subscription": sub_name}

        if ce_type == CE_TYPE_MESSAGE_CREATED:
            return await self._handle_message_created(
                data, oauth_token, chat_api_token, client
            )

        return {"type": "unknown", "ce_type": ce_type}

    async def _handle_message_created(
        self,
        data: dict,
        oauth_token: str,
        chat_api_token: str,
        client: httpx.AsyncClient,
    ) -> dict:
        """
        Run the Gemini inclusivity check on every human-authored message.
        Post a warning card if non-inclusive language is detected.
        """
        chat_message = data.get("message", {})
        sender_type = chat_message.get("sender", {}).get("type", "")
        if sender_type == "BOT":
            return {"type": "message_created", "skipped": True}

        text = chat_message.get("text", "")
        space_name = chat_message.get("space", {}).get("name", "")
        feedback = await self._vertex.get_inclusivity_feedback(text, oauth_token)

        if feedback != "It's inclusive!":
            warning_card = {
                "cardsV2": [
                    {
                        "cardId": "inclusivity-warning",
                        "card": {
                            "header": {
                                "title": "Inclusivity Notice",
                                "subtitle": (
                                    f"The following words may not be inclusive: {feedback}"
                                ),
                            }
                        },
                    }
                ]
            }
            chat_headers = {"Authorization": f"Bearer {chat_api_token}"}
            await client.post(
                f"https://chat.googleapis.com/v1/{space_name}/messages",
                headers=chat_headers,
                json=warning_card,
                timeout=15.0,
            )

        return {
            "type": "message_created",
            "space": space_name,
            "inclusive": feedback == "It's inclusive!",
            "feedback": feedback,
        }
