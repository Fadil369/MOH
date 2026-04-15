import pytest
from datetime import date
from core.models import ClaimLine, RejectionType, ClaimStatus
from agents.clinical_linc import ClinicalLINC
from agents.compliance_linc import ComplianceLINC
from agents.auth_linc import AuthLINC
from agents.predictive_linc import PredictiveLINC
from agents.fraud_detection_linc import FraudDetectionLINC


@pytest.fixture
def clinical():
    return ClinicalLINC()


@pytest.fixture
def compliance():
    return ComplianceLINC()


@pytest.fixture
def auth():
    return AuthLINC()


@pytest.fixture
def predictive():
    return PredictiveLINC()


@pytest.fixture
def fraud():
    return FraudDetectionLINC()


class TestClinicalLINC:
    def test_evaluate_necessity_basic(self, clinical, sample_claim_line):
        score = clinical.evaluate_medical_necessity(sample_claim_line)
        assert 0.0 <= score <= 1.0

    def test_evaluate_necessity_with_notes(self, clinical, sample_claim_line):
        score = clinical.evaluate_medical_necessity(
            sample_claim_line, "acute chronic necessary"
        )
        assert score > 0.5

    def test_generate_rationale(self, clinical, sample_claim_line):
        score = 0.75
        rationale = clinical.generate_appeal_rationale(sample_claim_line, score)
        assert "SL-001" in rationale
        assert "5000" in rationale

    def test_validate_inr_temporal(self, clinical, sample_claim_line):
        assert clinical.validate_inr_temporal(sample_claim_line, None) is True
        assert clinical.validate_inr_temporal(sample_claim_line, date(2024, 1, 15)) is True
        assert clinical.validate_inr_temporal(sample_claim_line, date(2024, 1, 10)) is False


class TestComplianceLINC:
    def test_validate_fhir_valid(self, compliance, sample_fhir_bundle):
        bundle_dict = sample_fhir_bundle.model_dump()
        errors = compliance.validate_fhir_payload(bundle_dict)
        assert errors == []

    def test_validate_fhir_missing_resourcetype(self, compliance):
        errors = compliance.validate_fhir_payload(
            {
                "id": "X",
                "type": "collection",
                "entry": [{"resource": {"resourceType": "Claim"}}],
            }
        )
        assert len(errors) > 0

    def test_pdpl_compliance_masked(self, compliance):
        data = {"patient_id": "***-XX-5678", "amount": 500}
        result = compliance.check_pdpl_compliance(data)
        assert result["compliant"] is True

    def test_pdpl_compliance_unmasked(self, compliance):
        data = {"patient_id": "PAT-12345", "amount": 500}
        result = compliance.check_pdpl_compliance(data)
        assert result["compliant"] is False

    def test_sfda_validation(self, compliance):
        assert compliance.validate_sfda_certification("MED-001") is True
        assert compliance.validate_sfda_certification("UNKNOWN-999") is False

    def test_compliance_score(self, compliance, sample_fhir_bundle):
        score = compliance.compliance_score(sample_fhir_bundle.model_dump())
        assert 0.0 <= score <= 1.0


class TestAuthLINC:
    def test_verify_eligibility_valid(self, auth):
        result = auth.verify_eligibility("PAT-001", "INS-001", date(2024, 6, 1))
        assert result["eligible"] is True
        assert result["coverage_percent"] > 0

    def test_verify_eligibility_expired(self, auth):
        result = auth.verify_eligibility("PAT-001", "INS-002", date(2024, 6, 1))
        assert result["eligible"] is False

    def test_check_preauth_valid(self, auth, sample_claim_line):
        result = auth.check_preauthorization("PA-12345", sample_claim_line)
        assert result["valid"] is True

    def test_check_preauth_invalid(self, auth, sample_claim_line):
        result = auth.check_preauthorization("", sample_claim_line)
        assert result["valid"] is False

    def test_get_coverage_details(self, auth):
        coverage = auth.get_coverage_details("INS-001")
        assert "coverage" in coverage


class TestPredictiveLINC:
    def test_forecast_cost(self, predictive, sample_claim_line):
        result = predictive.forecast_cost(sample_claim_line)
        assert "predicted_cost" in result
        assert result["confidence"] == 0.85
        assert result["predicted_cost"] > 0

    def test_forecast_with_history(self, predictive, sample_claim_line):
        history = [{"amount_sar": 4000}, {"amount_sar": 6000}]
        result = predictive.forecast_cost(sample_claim_line, history)
        assert result["predicted_cost"] > 0

    def test_appeal_success_estimate(self, predictive, sample_claim_line):
        prob = predictive.estimate_appeal_success(sample_claim_line)
        assert 0.0 <= prob <= 1.0

    def test_calculate_roi(self, predictive, sample_claim_lines):
        roi = predictive.calculate_roi(sample_claim_lines)
        assert "total_at_risk_sar" in roi
        assert "expected_recovery_sar" in roi
        assert roi["expected_recovery_sar"] <= roi["total_at_risk_sar"]


class TestFraudDetectionLINC:
    def test_detect_anomalies(self, fraud, sample_claim_lines):
        results = fraud.detect_anomalies(sample_claim_lines)
        assert len(results) == len(sample_claim_lines)
        for r in results:
            assert "anomaly" in r

    def test_detect_anomalies_single_claim(self, fraud, sample_claim_line):
        results = fraud.detect_anomalies([sample_claim_line])
        assert results == []

    def test_check_duplicate_billing(self, fraud, sample_claim_line):
        duplicates = fraud.check_duplicate_billing([sample_claim_line, sample_claim_line])
        assert len(duplicates) == 1

    def test_no_duplicates(self, fraud, sample_claim_lines):
        duplicates = fraud.check_duplicate_billing(sample_claim_lines)
        assert isinstance(duplicates, list)

    def test_validate_billing_codes(self, fraud, sample_claim_line):
        result = fraud.validate_billing_codes(sample_claim_line)
        assert result["valid"] is True

    def test_fraud_score_high_amount(self, fraud):
        claim = ClaimLine(
            service_line_id="SL-HIGH",
            patient_id="PAT-001",
            provider_id="PROV-001",
            amount_sar=60000.0,
            date_of_service=date(2024, 1, 1),
        )
        score = fraud.fraud_score(claim)
        assert score > 0.0

    def test_fraud_score_normal(self, fraud, sample_claim_line):
        score = fraud.fraud_score(sample_claim_line)
        assert 0.0 <= score <= 1.0
