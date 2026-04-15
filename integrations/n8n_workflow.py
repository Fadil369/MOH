import httpx
from datetime import date
from typing import List
from core.models import ClaimLine


class N8NOrchestrator:
    def __init__(self, n8n_url: str = "http://n8n:5678"):
        self.n8n_url = n8n_url

    async def trigger_daily_batch(self, n8n_url: str, batch_date: date) -> dict:
        payload = {
            "batch_date": batch_date.isoformat(),
            "trigger_time": "02:00 AST",
            "workflow": "daily_claims_batch",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{n8n_url}/webhook/claims-batch",
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_workflow_status(self, execution_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.n8n_url}/executions/{execution_id}",
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    def schedule_batch(self, claims: List[ClaimLine]) -> dict:
        return {
            "batch_size": len(claims),
            "total_amount_sar": sum(c.amount_sar for c in claims),
            "claim_ids": [c.service_line_id for c in claims],
            "scheduled": True,
        }
