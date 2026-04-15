from typing import Any

SFDA_APPROVED_CODES = {"MED-001", "MED-002", "MED-003", "DEV-100", "DEV-200"}


class ComplianceLINC:
    def validate_fhir_payload(self, bundle: dict) -> list:
        errors = []
        if bundle.get("resourceType") != "Bundle":
            errors.append("resourceType must be Bundle")
        if not bundle.get("entry"):
            errors.append("Bundle must have entries")
        if not bundle.get("id"):
            errors.append("Bundle must have id")
        if not bundle.get("type"):
            errors.append("Bundle must have type")
        for i, entry in enumerate(bundle.get("entry", [])):
            if "resource" not in entry:
                errors.append(f"Entry {i} missing resource")
        return errors

    def check_pdpl_compliance(self, data: dict) -> dict:
        issues = []
        phi_fields = {"patient_id", "name", "dob", "nric"}
        unmasked = [
            f for f in phi_fields
            if f in data and not str(data[f]).startswith("***")
        ]
        if unmasked:
            issues.append(f"Unmasked PHI fields: {unmasked}")
        return {"compliant": len(issues) == 0, "issues": issues}

    def validate_sfda_certification(self, medication_code: str) -> bool:
        return medication_code in SFDA_APPROVED_CODES

    def compliance_score(self, bundle: dict) -> float:
        errors = self.validate_fhir_payload(bundle)
        base = 1.0
        base -= 0.1 * len(errors)
        return max(0.0, min(1.0, base))
