import pytest
from datetime import date
from core.models import ClaimLine, RejectionType, NPHIESAction, ClaimStatus
from core.decision_engine import DecisionEngine


@pytest.fixture
def engine():
    return DecisionEngine()


def make_claim(rejection_type, amount=5000.0, rejection_code=None):
    return ClaimLine(
        service_line_id="SL-TEST",
        patient_id="PAT-001",
        provider_id="PROV-001",
        amount_sar=amount,
        rejection_type=rejection_type,
        rejection_code=rejection_code,
        date_of_service=date(2024, 1, 1),
    )


def test_route_administrative(engine):
    claim = make_claim(RejectionType.ADMINISTRATIVE)
    assert engine.route_claim(claim) == NPHIESAction.RESUBMIT_NEW


def test_route_clinical_documentation(engine):
    claim = make_claim(RejectionType.CLINICAL_DOCUMENTATION)
    assert engine.route_claim(claim) == NPHIESAction.APPEAL


def test_route_preauthorization_be14(engine):
    claim = make_claim(RejectionType.PREAUTHORIZATION, rejection_code="BE-1-4")
    assert engine.route_claim(claim) == NPHIESAction.RESUBMIT_NEW


def test_route_preauthorization_be15(engine):
    claim = make_claim(RejectionType.PREAUTHORIZATION, rejection_code="BE-1-5")
    assert engine.route_claim(claim) == NPHIESAction.APPEAL


def test_route_medication_device(engine):
    claim = make_claim(RejectionType.MEDICATION_DEVICE)
    assert engine.route_claim(claim) == NPHIESAction.APPEAL


def test_route_policy_limitation_normal(engine):
    claim = make_claim(RejectionType.POLICY_LIMITATION)
    assert engine.route_claim(claim) == NPHIESAction.APPEAL


def test_route_policy_limitation_high_fraud(engine):
    claim = make_claim(RejectionType.POLICY_LIMITATION)
    assert engine.route_claim(claim, {"fraud_score": 0.9}) == NPHIESAction.VOID


def test_hitl_trigger_above_threshold(engine):
    claim = make_claim(RejectionType.ADMINISTRATIVE, amount=15000.0)
    assert engine.should_trigger_hitl(claim) is True


def test_hitl_trigger_below_threshold(engine):
    claim = make_claim(RejectionType.ADMINISTRATIVE, amount=5000.0)
    assert engine.should_trigger_hitl(claim) is False


def test_hitl_trigger_exactly_threshold(engine):
    claim = make_claim(RejectionType.ADMINISTRATIVE, amount=10000.0)
    assert engine.should_trigger_hitl(claim) is False


def test_batch_route(engine, sample_claim_lines):
    routes = engine.batch_route(sample_claim_lines)
    assert len(routes) == len(sample_claim_lines)
    for action in routes.values():
        assert isinstance(action, NPHIESAction)


def test_build_hitl_request(engine, sample_claim_line):
    req = engine.build_hitl_request(
        sample_claim_line, NPHIESAction.APPEAL, {"clinical": 0.8}
    )
    assert req.claim_id == sample_claim_line.service_line_id
    assert req.recommended_action == NPHIESAction.APPEAL
