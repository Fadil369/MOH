import pytest
from datetime import date
from core.fhir_builder import FHIRBuilder
from core.models import ClaimLine, NPHIESAction, RejectionType


@pytest.fixture
def builder():
    return FHIRBuilder()


@pytest.fixture
def claim():
    return ClaimLine(
        service_line_id="SL-FHIR-001",
        patient_id="PAT-FHIR-001",
        provider_id="PROV-001",
        amount_sar=7500.0,
        rejection_code="MN-1-1",
        rejection_type=RejectionType.CLINICAL_DOCUMENTATION,
        date_of_service=date(2024, 1, 15),
        preauth_id="PA-FHIR-001",
    )


def test_build_patient_resource_masked(builder):
    patient = builder.build_patient_resource("PAT-12345", masked=True)
    assert patient["resourceType"] == "Patient"
    identifier_value = patient["identifier"][0]["value"]
    assert "***" in identifier_value


def test_build_patient_resource_unmasked(builder):
    patient = builder.build_patient_resource("PAT-12345", masked=False)
    assert patient["identifier"][0]["value"] == "PAT-12345"


def test_build_claim_resource(builder, claim):
    resource = builder.build_claim_resource(claim)
    assert resource["resourceType"] == "Claim"
    assert resource["total"]["value"] == 7500.0
    assert resource["total"]["currency"] == "SAR"


def test_build_coverage_resource(builder):
    coverage = builder.build_coverage_resource("PA-001")
    assert coverage["resourceType"] == "Coverage"
    assert coverage["dependent"] == "PA-001"


def test_build_claim_bundle(builder, claim):
    bundle = builder.build_claim_bundle(claim, NPHIESAction.APPEAL)
    assert bundle.resourceType == "Bundle"
    assert len(bundle.entry) >= 2
    resource_types = [e["resource"]["resourceType"] for e in bundle.entry]
    assert "Patient" in resource_types
    assert "Claim" in resource_types


def test_build_appeal_bundle(builder, claim):
    bundle = builder.build_appeal_bundle(claim, "Medical necessity confirmed by physician")
    resource_types = [e["resource"]["resourceType"] for e in bundle.entry]
    assert "Communication" in resource_types


def test_validate_bundle_valid(builder, sample_fhir_bundle):
    errors = builder.validate_bundle(sample_fhir_bundle)
    assert errors == []


def test_validate_bundle_missing_entries(builder):
    from core.models import FHIRBundle

    bundle = FHIRBundle(id="B-001", type="collection", entry=[])
    errors = builder.validate_bundle(bundle)
    assert len(errors) > 0


def test_validate_bundle_missing_resource_type(builder):
    from core.models import FHIRBundle

    bundle = FHIRBundle(
        id="B-001", type="collection", entry=[{"resource": {"id": "no-type"}}]
    )
    errors = builder.validate_bundle(bundle)
    assert len(errors) > 0
