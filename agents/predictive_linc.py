from typing import List, Optional
import numpy as np
from core.models import ClaimLine, RejectionType

APPEAL_SUCCESS_RATES = {
    RejectionType.ADMINISTRATIVE: 0.85,
    RejectionType.CLINICAL_DOCUMENTATION: 0.60,
    RejectionType.PREAUTHORIZATION: 0.55,
    RejectionType.MEDICATION_DEVICE: 0.45,
    RejectionType.POLICY_LIMITATION: 0.40,
}


class PredictiveLINC:
    def forecast_cost(self, claim: ClaimLine, historical_data: list = None) -> dict:
        base = claim.amount_sar
        if historical_data:
            amounts = [
                h.get("amount_sar", base)
                for h in historical_data
                if isinstance(h, dict)
            ]
            if amounts:
                avg = np.mean(amounts)
                predicted = (base + avg) / 2
            else:
                predicted = base * 1.05
        else:
            predicted = base * 1.05
        return {
            "predicted_cost": round(predicted, 2),
            "confidence": 0.85,
            "base_amount": base,
        }

    def estimate_appeal_success(self, claim: ClaimLine, rejection_type=None) -> float:
        rtype = rejection_type or claim.rejection_type or RejectionType.ADMINISTRATIVE
        base = APPEAL_SUCCESS_RATES.get(rtype, 0.5)
        if claim.preauth_id:
            base += 0.05
        return min(1.0, base)

    def calculate_roi(self, claims: List[ClaimLine]) -> dict:
        total_at_risk = sum(c.amount_sar for c in claims)
        expected_recovery = sum(
            c.amount_sar * self.estimate_appeal_success(c) for c in claims
        )
        return {
            "total_at_risk_sar": round(total_at_risk, 2),
            "expected_recovery_sar": round(expected_recovery, 2),
            "recovery_rate": round(expected_recovery / total_at_risk, 4)
            if total_at_risk > 0
            else 0.0,
        }
