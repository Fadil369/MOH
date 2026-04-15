from datetime import date
from core.models import ClaimLine

MOCK_ELIGIBILITY = {
    "INS-001": {"active": True, "expiry": date(2025, 12, 31), "coverage": 80.0},
    "INS-002": {"active": False, "expiry": date(2024, 1, 1), "coverage": 0.0},
}


class AuthLINC:
    def verify_eligibility(self, patient_id: str, insurance_id: str, date_of_service: date) -> dict:
        coverage = MOCK_ELIGIBILITY.get(
            insurance_id,
            {"active": True, "expiry": date(2026, 1, 1), "coverage": 75.0},
        )
        eligible = coverage["active"] and coverage["expiry"] >= date_of_service
        return {
            "eligible": eligible,
            "patient_id": patient_id,
            "insurance_id": insurance_id,
            "coverage_percent": coverage["coverage"] if eligible else 0.0,
        }

    def check_preauthorization(self, preauth_id: str, claim: ClaimLine) -> dict:
        if not preauth_id:
            return {"valid": False, "reason": "No preauth_id provided"}
        valid = preauth_id.startswith("PA-") or preauth_id.startswith("AUTH-")
        return {
            "valid": valid,
            "preauth_id": preauth_id,
            "claim_id": claim.service_line_id,
            "reason": "Valid preauthorization" if valid else "Invalid preauth format",
        }

    def get_coverage_details(self, insurance_id: str) -> dict:
        return MOCK_ELIGIBILITY.get(
            insurance_id,
            {
                "active": True,
                "coverage": 75.0,
                "insurance_id": insurance_id,
            },
        )
