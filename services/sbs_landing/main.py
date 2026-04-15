from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from core.models import ClaimLine
from core.decision_engine import DecisionEngine
from services.financial_rules.main import FinancialRulesEngine

app = FastAPI(title="SBS Landing Service")
engine = DecisionEngine()
rules = FinancialRulesEngine()


@app.get("/health")
def health():
    return {"status": "ok", "service": "sbs_landing"}


class ProcessRequest(BaseModel):
    claims: List[dict]


@app.post("/process")
async def process(req: ProcessRequest):
    claims = [ClaimLine(**c) for c in req.claims]
    for claim in claims:
        if claim.rejection_code and not claim.rejection_type:
            claim.rejection_type = rules.classify_rejection(claim.rejection_code)
    routes = engine.batch_route(claims)
    hitl_claims = [c.service_line_id for c in claims if engine.should_trigger_hitl(c)]
    return {
        "processed": len(claims),
        "routes": {k: v.value for k, v in routes.items()},
        "hitl_required": hitl_claims,
    }


@app.get("/dashboard")
def dashboard():
    return {
        "status": "operational",
        "services": ["normalizer", "signer", "financial_rules", "nphies_bridge"],
    }
