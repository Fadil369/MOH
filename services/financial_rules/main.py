from datetime import date, timedelta
from typing import List, Dict
from fastapi import FastAPI
from pydantic import BaseModel
from core.models import ClaimLine, RejectionType

app = FastAPI(title="Financial Rules Service")

REJECTION_CODE_MAP = {
    "SE-1-10": RejectionType.ADMINISTRATIVE,
    "SE-1-11": RejectionType.ADMINISTRATIVE,
    "SE-1-12": RejectionType.ADMINISTRATIVE,
    "SE-1-2": RejectionType.CLINICAL_DOCUMENTATION,
    "MN-1-1": RejectionType.CLINICAL_DOCUMENTATION,
    "MN-1-2": RejectionType.CLINICAL_DOCUMENTATION,
    "BE-1-4": RejectionType.PREAUTHORIZATION,
    "BE-1-5": RejectionType.PREAUTHORIZATION,
    "BE-1-6": RejectionType.PREAUTHORIZATION,
    "CV-4-10": RejectionType.MEDICATION_DEVICE,
    "CV-4-7": RejectionType.MEDICATION_DEVICE,
    "CV-4-8": RejectionType.MEDICATION_DEVICE,
    "CV-3-4": RejectionType.POLICY_LIMITATION,
    "AD-3-5": RejectionType.POLICY_LIMITATION,
    "CV-3-5": RejectionType.POLICY_LIMITATION,
}

RESUBMISSION_WINDOW_DAYS = 15


class FinancialRulesEngine:
    def classify_rejection(self, rejection_code: str) -> RejectionType:
        if not rejection_code:
            return RejectionType.ADMINISTRATIVE
        code = rejection_code.strip().upper()
        for k, v in REJECTION_CODE_MAP.items():
            if code.startswith(k) or code == k:
                return v
        if code.startswith("SE-"):
            return RejectionType.ADMINISTRATIVE
        if code.startswith("MN-"):
            return RejectionType.CLINICAL_DOCUMENTATION
        if code.startswith("BE-"):
            return RejectionType.PREAUTHORIZATION
        if code.startswith("CV-4"):
            return RejectionType.MEDICATION_DEVICE
        if code.startswith("CV-3") or code.startswith("AD-"):
            return RejectionType.POLICY_LIMITATION
        return RejectionType.ADMINISTRATIVE

    def calculate_resubmission_deadline(self, rejection_date: date) -> date:
        return rejection_date + timedelta(days=RESUBMISSION_WINDOW_DAYS)

    def prioritize_claims(self, claims: List[ClaimLine]) -> List[ClaimLine]:
        today = date.today()

        def sort_key(c):
            deadline = self.calculate_resubmission_deadline(c.date_of_service)
            days_left = (deadline - today).days
            return (-c.amount_sar, days_left)

        return sorted(claims, key=sort_key)

    def analyze_portfolio(self, claims: List[ClaimLine]) -> dict:
        total_rejected = sum(c.amount_sar for c in claims)
        by_type: Dict[str, float] = {}
        for c in claims:
            rtype = (c.rejection_type or RejectionType.ADMINISTRATIVE).value
            by_type[rtype] = by_type.get(rtype, 0.0) + c.amount_sar
        return {
            "total_rejected_sar": total_rejected,
            "claim_count": len(claims),
            "by_type": by_type,
        }


engine = FinancialRulesEngine()


class ClassifyRequest(BaseModel):
    rejection_code: str


class AnalyzeRequest(BaseModel):
    claims: List[dict]


@app.post("/classify")
def classify(req: ClassifyRequest):
    rtype = engine.classify_rejection(req.rejection_code)
    return {"rejection_type": rtype.value}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    claims = [ClaimLine(**c) for c in req.claims]
    stats = engine.analyze_portfolio(claims)
    return stats


@app.get("/health")
def health():
    return {"status": "ok", "service": "financial_rules"}
