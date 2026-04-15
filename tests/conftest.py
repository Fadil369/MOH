import pytest
from datetime import date
from core.models import ClaimLine, RejectionType, ClaimStatus, FHIRBundle, HITLRequest, NPHIESAction


@pytest.fixture
def sample_claim_line():
    return ClaimLine(
        service_line_id="SL-001",
        patient_id="PAT-12345",
        provider_id="PROV-001",
        amount_sar=5000.0,
        rejection_code="SE-1-10",
        rejection_type=RejectionType.ADMINISTRATIVE,
        date_of_service=date(2024, 1, 15),
        status=ClaimStatus.REJECTED,
        preauth_id="PA-12345",
        medication_code="MED-001",
    )


@pytest.fixture
def sample_claim_lines():
    claims = []
    rejection_codes = [
        ("SE-1-10", RejectionType.ADMINISTRATIVE),
        ("MN-1-1", RejectionType.CLINICAL_DOCUMENTATION),
        ("BE-1-4", RejectionType.PREAUTHORIZATION),
        ("CV-4-10", RejectionType.MEDICATION_DEVICE),
        ("CV-3-4", RejectionType.POLICY_LIMITATION),
        ("SE-1-11", RejectionType.ADMINISTRATIVE),
        ("MN-1-2", RejectionType.CLINICAL_DOCUMENTATION),
        ("BE-1-5", RejectionType.PREAUTHORIZATION),
        ("CV-4-7", RejectionType.MEDICATION_DEVICE),
        ("AD-3-5", RejectionType.POLICY_LIMITATION),
    ]
    for i, (code, rtype) in enumerate(rejection_codes):
        claims.append(
            ClaimLine(
                service_line_id=f"SL-{i+1:03d}",
                patient_id=f"PAT-{i+1:05d}",
                provider_id=f"PROV-{(i % 3) + 1:03d}",
                amount_sar=float((i + 1) * 1500),
                rejection_code=code,
                rejection_type=rtype,
                date_of_service=date(2024, 1, i + 1),
                status=ClaimStatus.REJECTED,
                preauth_id=f"PA-{i+1:05d}" if i % 2 == 0 else None,
                medication_code=f"MED-{(i % 3) + 1:03d}",
            )
        )
    return claims


@pytest.fixture
def sample_fhir_bundle():
    return FHIRBundle(
        id="BUNDLE-001",
        resourceType="Bundle",
        type="collection",
        entry=[
            {"resource": {"resourceType": "Patient", "id": "PAT-001"}},
            {
                "resource": {
                    "resourceType": "Claim",
                    "id": "CLAIM-001",
                    "total": {"value": 5000, "currency": "SAR"},
                }
            },
        ],
    )


@pytest.fixture
def mock_nphies_response():
    return {
        "resourceType": "Bundle",
        "id": "RESP-001",
        "type": "batch-response",
        "entry": [{"response": {"status": "201 Created"}}],
    }


@pytest.fixture
def hitl_request(sample_claim_line):
    return HITLRequest(
        claim_id=sample_claim_line.service_line_id,
        amount_sar=sample_claim_line.amount_sar,
        rejection_type=RejectionType.ADMINISTRATIVE,
        recommended_action=NPHIESAction.RESUBMIT_NEW,
        agent_assessments={"clinical": 0.8, "fraud": 0.1},
    )
