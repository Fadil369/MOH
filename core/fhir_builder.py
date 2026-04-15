from datetime import datetime
import uuid
from core.models import ClaimLine, FHIRBundle, NPHIESAction


class FHIRBuilder:
    def build_patient_resource(self, patient_id: str, masked: bool = True) -> dict:
        display_id = (
            f"***-XX-{patient_id[-4:].upper()}"
            if masked and len(patient_id) >= 4
            else patient_id
        )
        return {
            "resourceType": "Patient",
            "id": str(uuid.uuid4()),
            "identifier": [
                {"system": "http://nphies.sa/identifier/patient", "value": display_id}
            ],
            "active": True,
        }

    def build_claim_resource(self, claim: ClaimLine) -> dict:
        resource = {
            "resourceType": "Claim",
            "id": claim.service_line_id,
            "status": "active",
            "type": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                        "code": "professional",
                    }
                ]
            },
            "use": "claim",
            "patient": {"reference": f"Patient/{claim.patient_id}"},
            "created": datetime.utcnow().isoformat(),
            "provider": {"reference": f"Organization/{claim.provider_id}"},
            "priority": {"coding": [{"code": "normal"}]},
            "total": {"value": claim.amount_sar, "currency": "SAR"},
        }
        if claim.preauth_id:
            resource["prescription"] = {
                "reference": f"ServiceRequest/{claim.preauth_id}"
            }
        return resource

    def build_coverage_resource(self, preauth_id: str) -> dict:
        return {
            "resourceType": "Coverage",
            "id": str(uuid.uuid4()),
            "status": "active",
            "beneficiary": {"reference": "Patient/unknown"},
            "payor": [{"reference": "Organization/insurer"}],
            "dependent": preauth_id,
        }

    def build_claim_bundle(self, claim: ClaimLine, action: NPHIESAction) -> FHIRBundle:
        entries = [
            {"resource": self.build_patient_resource(claim.patient_id)},
            {"resource": self.build_claim_resource(claim)},
        ]
        if claim.preauth_id:
            entries.append(
                {"resource": self.build_coverage_resource(claim.preauth_id)}
            )
        return FHIRBundle(
            type="collection",
            entry=entries,
        )

    def build_appeal_bundle(self, claim: ClaimLine, rationale: str) -> FHIRBundle:
        bundle = self.build_claim_bundle(claim, NPHIESAction.APPEAL)
        bundle.entry.append(
            {
                "resource": {
                    "resourceType": "Communication",
                    "id": str(uuid.uuid4()),
                    "status": "completed",
                    "payload": [{"contentString": rationale}],
                }
            }
        )
        return bundle

    def validate_bundle(self, bundle: FHIRBundle) -> list[str]:
        errors = []
        if not bundle.id:
            errors.append("Bundle missing id")
        if not bundle.entry:
            errors.append("Bundle has no entries")
        for i, entry in enumerate(bundle.entry):
            if "resource" not in entry:
                errors.append(f"Entry {i} missing resource")
            elif "resourceType" not in entry["resource"]:
                errors.append(f"Entry {i} resource missing resourceType")
        return errors
