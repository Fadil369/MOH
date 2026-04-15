from core.models import ClaimLine

COMMON_DIAGNOSIS_CODES = {"J06.9", "I10", "E11.9", "M79.3", "K92.1", "Z51.11"}


class ClinicalLINC:
    def evaluate_medical_necessity(self, claim: ClaimLine, clinical_notes: str = "") -> float:
        score = 0.5
        if claim.medication_code and claim.medication_code in COMMON_DIAGNOSIS_CODES:
            score += 0.2
        if clinical_notes:
            score += 0.1
            keywords = ["acute", "chronic", "necessary", "required", "evidence"]
            score += 0.04 * sum(1 for k in keywords if k.lower() in clinical_notes.lower())
        if claim.preauth_id:
            score += 0.1
        return min(1.0, score)

    def generate_appeal_rationale(self, claim: ClaimLine, score: float) -> str:
        return (
            f"Medical necessity appeal for service line {claim.service_line_id}. "
            f"Amount: {claim.amount_sar:.2f} SAR. "
            f"Necessity score: {score:.2f}. "
            f"Clinical evidence supports the medical necessity of this claim. "
            f"{'Pre-authorization reference: ' + claim.preauth_id + '.' if claim.preauth_id else ''}"
        )

    def validate_inr_temporal(self, claim: ClaimLine, inr_date=None) -> bool:
        from datetime import date, timedelta
        if inr_date is None:
            return True
        return abs((claim.date_of_service - inr_date).days) <= 1
