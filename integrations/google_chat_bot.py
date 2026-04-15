"""
Google Chat bot integration for MOH claim management.

Implements the full issue-management-app lifecycle (adapted from
https://github.com/googleworkspace/google-chat-samples/tree/62dd4336f/
apps-script/issue-management-app) as a Python/httpx async module:

* HITL review cards for high-value claims (> SAR 10 000)
* Slash-command handling: /create, /close
* Dedicated Chat space per claim issue
* App Home dashboard
* Space history export for AI summarisation
"""

from __future__ import annotations

import httpx

from core.models import (
    ClaimIssue,
    ClaimLine,
    HITLRequest,
    IssueStatus,
    NPHIESAction,
    RejectionType,
)
from integrations.issue_store import IssueStore, issue_store as _default_store

# Slash-command IDs (must match Google Chat app configuration)
CREATE_COMMAND_ID = 1
CLOSE_COMMAND_ID = 2

# Primary MOH claims coordination space
HITL_SPACE_ID = "spaces/AAQAUkMiTP8"
HITL_SPACE_URL = "https://chat.google.com/room/AAQAUkMiTP8?cls=7"


class GoogleChatBot:
    """Google Chat bot handling HITL reviews and full issue lifecycle."""

    def __init__(self, store: IssueStore | None = None) -> None:
        self._store = store or _default_store

    # ------------------------------------------------------------------
    # Event entry-points (mirror Apps Script onMessage / onCardClick)
    # ------------------------------------------------------------------

    def handle_message(self, event: dict) -> dict:
        """Route an incoming MESSAGE event to the correct handler."""
        message = event.get("message", {})
        if message.get("slashCommand"):
            return self.process_slash_command(event)
        return {
            "text": (
                "Available slash commands to manage claim issues: "
                "'/create' and '/close'."
            )
        }

    def handle_card_clicked(self, event: dict) -> dict:
        """Route a CARD_CLICKED event to the correct handler."""
        action_name = event.get("action", {}).get("actionMethodName", "")
        if action_name == "createIssue":
            return self._handle_create_issue_submission(event)
        # HITL approve / reject actions
        if action_name in ("approve", "reject"):
            return self.parse_response(event)
        return {"text": "Unknown action."}

    def handle_app_home(self, _event: dict | None = None) -> dict:
        """Return the App Home card listing all tracked claim issues."""
        return self.build_app_home_card()

    # ------------------------------------------------------------------
    # Slash-command processing
    # ------------------------------------------------------------------

    def process_slash_command(self, event: dict) -> dict:
        """Handle /create and /close slash commands."""
        command_id = (
            event.get("message", {}).get("slashCommand", {}).get("commandId")
        )
        space_type = (
            event.get("message", {}).get("space", {}).get("type", "SPACE")
        )

        if command_id == CREATE_COMMAND_ID:
            return self._create_dialog()

        if command_id == CLOSE_COMMAND_ID and space_type != "DM":
            return self._close_issue_from_event(event)

        return {"text": "The command isn't supported."}

    def _create_dialog(self) -> dict:
        """Return the /create dialog asking for title + description."""
        return {
            "actionResponse": {
                "type": "DIALOG",
                "dialogAction": {
                    "dialog": {
                        "body": {
                            "sections": [
                                {
                                    "header": "Create Claim Issue",
                                    "widgets": [
                                        {
                                            "textInput": {
                                                "label": "Title",
                                                "name": "title",
                                            }
                                        },
                                        {
                                            "textInput": {
                                                "label": "Description",
                                                "type": "MULTIPLE_LINE",
                                                "name": "description",
                                            }
                                        },
                                        {
                                            "buttonList": {
                                                "buttons": [
                                                    {
                                                        "text": "Create",
                                                        "onClick": {
                                                            "action": {
                                                                "function": "createIssue"
                                                            }
                                                        },
                                                    }
                                                ]
                                            }
                                        },
                                    ],
                                }
                            ]
                        }
                    }
                },
            }
        }

    def _close_issue_from_event(self, event: dict) -> dict:
        """
        Handle /close in an issue space.

        Callers that need real Chat-API + AI calls should use the async
        ``close_issue()`` method instead.  This sync method returns the
        expected response structure with a placeholder for the report URL.
        """
        space_id = event.get("message", {}).get("space", {}).get("name", "")
        resolution = event.get("message", {}).get("argumentText", "")
        issue = self._store.get(space_id)
        if issue is None:
            return {"text": "No issue found for this space."}
        updated = self._store.close(space_id, resolution, "")
        return {
            "actionResponse": {"type": "NEW_MESSAGE"},
            "text": (
                f"Issue '{updated.title}' is closed. "
                "Generate the full report by calling the async close_issue() method."
            ),
        }

    def _handle_create_issue_submission(self, event: dict) -> dict:
        """
        Handle the createIssue dialog form submission.

        Creates a ClaimIssue in the store.  Callers that need to actually
        create a Chat space should use the async ``create_issue_space()`` method.
        """
        form = event.get("common", {}).get("formInputs", {})
        title = form.get("title", {}).get("", {}).get("stringInputs", {}).get("value", [""])[0]
        description = form.get("description", {}).get("", {}).get("stringInputs", {}).get("value", [""])[0]
        issue = ClaimIssue(title=title, description=description)
        self._store.save(issue)
        return {
            "actionResponse": {"type": "NEW_MESSAGE"},
            "text": (
                f"Issue '{title}' created. "
                f"Issue ID: {issue.issue_id}"
            ),
        }

    # ------------------------------------------------------------------
    # Async Chat-API calls
    # ------------------------------------------------------------------

    async def create_issue_space(
        self,
        title: str,
        description: str,
        chat_api_token: str,
        subscription_id: str = "",
        claim_line_id: str | None = None,
    ) -> ClaimIssue:
        """
        Create a dedicated Google Chat space for a claim issue.

        Mirrors ``createIssueSpace`` + ``saveCreatedIssue`` from the
        Apps Script baseline.

        Args:
            title: Issue / space display name.
            description: Initial message posted to the new space.
            chat_api_token: Bearer token for the Chat REST API.
            subscription_id: Workspace Events subscription ID (if already created).
            claim_line_id: Optional reference to the MOH ClaimLine.

        Returns:
            The persisted ClaimIssue.
        """
        headers = {"Authorization": f"Bearer {chat_api_token}"}
        async with httpx.AsyncClient() as client:
            # 1. Create the space
            resp = await client.post(
                "https://chat.googleapis.com/v1/spaces:setup",
                headers=headers,
                json={"space": {"displayName": title, "spaceType": "SPACE"}},
                timeout=15.0,
            )
            resp.raise_for_status()
            space_name = resp.json()["name"]  # e.g. "spaces/AAABBB"

            # 2. Add the app itself as a member
            member_resp = await client.post(
                f"https://chat.googleapis.com/v1/{space_name}/members",
                headers=headers,
                json={"member": {"name": "users/app", "type": "BOT"}},
                timeout=15.0,
            )
            member_resp.raise_for_status()

            # 3. Post the description as the first message
            message_resp = await client.post(
                f"https://chat.googleapis.com/v1/{space_name}/messages",
                headers=headers,
                json={"text": description},
                timeout=15.0,
            )
            message_resp.raise_for_status()

        issue = ClaimIssue(
            title=title,
            description=description,
            space_id=space_name,
            subscription_id=subscription_id,
            claim_line_id=claim_line_id,
        )
        self._store.save(issue)
        return issue

    async def export_space_history(
        self, space_name: str, chat_api_token: str
    ) -> str:
        """
        Fetch the 100 most recent messages from a Chat space.

        Mirrors ``exportSpaceHistory`` from the Apps Script baseline.
        Slash-command messages are filtered out.

        Returns:
            Concatenated messages in ``"SenderName: text"`` format.
        """
        headers = {"Authorization": f"Bearer {chat_api_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://chat.googleapis.com/v1/{space_name}/messages",
                headers=headers,
                params={"pageSize": 100},
                timeout=15.0,
            )
            resp.raise_for_status()
            messages = resp.json().get("messages", [])

        lines = []
        for msg in messages:
            if msg.get("slashCommand"):
                continue
            sender = msg.get("sender", {}).get("displayName", "Unknown User")
            text = msg.get("text", "")
            lines.append(f"{sender}: {text}")
        return "\n".join(lines)

    async def close_issue(
        self,
        space_id: str,
        resolution: str,
        report_url: str,
        chat_api_token: str,
    ) -> ClaimIssue | None:
        """
        Close a claim issue: persist state and notify the space.

        Mirrors ``saveClosedIssue`` + the /close handler from the Apps
        Script baseline.
        """
        issue = self._store.close(space_id, resolution, report_url)
        if issue is None:
            return None

        headers = {"Authorization": f"Bearer {chat_api_token}"}
        text = f"The issue is closed. Report: {report_url}" if report_url else "The issue is closed."
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://chat.googleapis.com/v1/{space_id}/messages",
                headers=headers,
                json={"text": text},
                timeout=15.0,
            )
            resp.raise_for_status()
        return issue

    # ------------------------------------------------------------------
    # App Home
    # ------------------------------------------------------------------

    def build_app_home_card(self) -> dict:
        """
        Build the App Home card listing all tracked claim issues.

        Mirrors ``onAppHome`` from the Apps Script 2-app-home step.
        """
        sections = []
        for issue in self._store.all():
            space_url = (
                f"https://mail.google.com/mail/u/0/#chat/space/{issue.space_id.replace('spaces/', '')}"
                if issue.space_id
                else HITL_SPACE_URL
            )
            buttons = [
                {
                    "text": "Open Space",
                    "onClick": {"openLink": {"url": space_url}},
                }
            ]
            if issue.report_url:
                buttons.append(
                    {
                        "text": "Open Report",
                        "onClick": {"openLink": {"url": issue.report_url}},
                    }
                )
            sections.append(
                {
                    "header": f"{issue.status.value} – {issue.title}",
                    "widgets": [
                        {
                            "textParagraph": {
                                "text": f"Description: {issue.description}"
                            }
                        },
                        {
                            "textParagraph": {
                                "text": f"Resolution: {issue.resolution or 'N/A'}"
                            }
                        },
                        {"buttonList": {"buttons": buttons}},
                    ],
                }
            )

        return {
            "action": {
                "navigations": [{"push_card": {"sections": sections}}]
            }
        }

    # ------------------------------------------------------------------
    # HITL review cards (original functionality, preserved)
    # ------------------------------------------------------------------

    def create_hitl_card(self, request: HITLRequest) -> dict:
        """Create a HITL review card for claims above the SAR threshold."""
        return {
            "cards": [
                {
                    "header": {
                        "title": f"HITL Review Required: {request.claim_id}",
                        "subtitle": f"Amount: {request.amount_sar:.2f} SAR",
                    },
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": f"<b>Rejection Type:</b> {request.rejection_type.value}"
                                    }
                                },
                                {
                                    "textParagraph": {
                                        "text": f"<b>Recommended Action:</b> {request.recommended_action.value}"
                                    }
                                },
                                {
                                    "textParagraph": {
                                        "text": f"<b>Agent Assessments:</b> {request.agent_assessments}"
                                    }
                                },
                                {
                                    "buttons": [
                                        {
                                            "textButton": {
                                                "text": "APPROVE",
                                                "onClick": {
                                                    "action": {
                                                        "actionMethodName": "approve"
                                                    }
                                                },
                                            }
                                        },
                                        {
                                            "textButton": {
                                                "text": "REJECT",
                                                "onClick": {
                                                    "action": {
                                                        "actionMethodName": "reject"
                                                    }
                                                },
                                            }
                                        },
                                    ]
                                },
                            ]
                        }
                    ],
                }
            ]
        }

    async def send_review_request(
        self, webhook_url: str, request: HITLRequest
    ) -> dict:
        """Post a HITL review card to a Google Chat webhook."""
        card = self.create_hitl_card(request)
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=card, timeout=15.0)
            resp.raise_for_status()
            return resp.json()

    def parse_response(self, response: dict) -> dict:
        """Parse an approve/reject card-click response."""
        action = response.get("action", {}).get("actionMethodName", "unknown")
        return {
            "decision": action,
            "approved": action == "approve",
            "raw": response,
        }

    def format_claim_summary(self, claim: ClaimLine, agents: dict) -> str:
        """Format a human-readable claim summary for HITL review."""
        lines = [
            f"Claim ID: {claim.service_line_id}",
            f"Amount: {claim.amount_sar:.2f} SAR",
            f"Date of Service: {claim.date_of_service}",
            f"Rejection Code: {claim.rejection_code or 'N/A'}",
            f"Rejection Type: {claim.rejection_type.value if claim.rejection_type else 'N/A'}",
        ]
        for agent_name, assessment in agents.items():
            lines.append(f"{agent_name}: {assessment}")
        return "\n".join(lines)

