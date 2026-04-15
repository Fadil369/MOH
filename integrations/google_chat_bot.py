import httpx
from core.models import HITLRequest, ClaimLine


class GoogleChatBot:
    def create_hitl_card(self, request: HITLRequest) -> dict:
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

    async def send_review_request(self, webhook_url: str, request: HITLRequest) -> dict:
        card = self.create_hitl_card(request)
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=card, timeout=15.0)
            resp.raise_for_status()
            return resp.json()

    def parse_response(self, response: dict) -> dict:
        action = response.get("action", {}).get("actionMethodName", "unknown")
        return {
            "decision": action,
            "approved": action == "approve",
            "raw": response,
        }

    def format_claim_summary(self, claim: ClaimLine, agents: dict) -> str:
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
