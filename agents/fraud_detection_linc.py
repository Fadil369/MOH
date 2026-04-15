from typing import List
import numpy as np
from core.models import ClaimLine


class FraudDetectionLINC:
    def detect_anomalies(self, claims: List[ClaimLine]) -> List[dict]:
        if len(claims) < 2:
            return []
        from sklearn.ensemble import IsolationForest

        amounts = np.array([[c.amount_sar] for c in claims])
        clf = IsolationForest(contamination=0.1, random_state=42)
        labels = clf.fit_predict(amounts)
        return [
            {"service_line_id": c.service_line_id, "anomaly": bool(label == -1)}
            for c, label in zip(claims, labels)
        ]

    def check_duplicate_billing(self, claims: List[ClaimLine]) -> List[dict]:
        seen = {}
        duplicates = []
        for c in claims:
            key = (c.patient_id, c.date_of_service, c.medication_code)
            if key in seen:
                duplicates.append(
                    {
                        "original": seen[key],
                        "duplicate": c.service_line_id,
                    }
                )
            else:
                seen[key] = c.service_line_id
        return duplicates

    def validate_billing_codes(self, claim: ClaimLine) -> dict:
        issues = []
        if claim.amount_sar <= 0:
            issues.append("Amount must be positive")
        if claim.medication_code and len(claim.medication_code) > 20:
            issues.append("Medication code too long")
        return {"valid": len(issues) == 0, "issues": issues}

    def fraud_score(self, claim: ClaimLine) -> float:
        score = 0.0
        if claim.amount_sar > 50_000:
            score += 0.3
        if not claim.preauth_id and claim.amount_sar > 10_000:
            score += 0.2
        if claim.rejection_code and claim.rejection_code.startswith("CV"):
            score += 0.1
        return min(1.0, score)
