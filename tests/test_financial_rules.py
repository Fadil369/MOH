import pytest
from datetime import date, timedelta
from services.financial_rules.main import FinancialRulesEngine, REJECTION_CODE_MAP
from core.models import RejectionType


@pytest.fixture
def engine():
    return FinancialRulesEngine()


@pytest.mark.parametrize(
    "code,expected",
    [
        ("SE-1-10", RejectionType.ADMINISTRATIVE),
        ("SE-1-11", RejectionType.ADMINISTRATIVE),
        ("MN-1-1", RejectionType.CLINICAL_DOCUMENTATION),
        ("SE-1-2", RejectionType.CLINICAL_DOCUMENTATION),
        ("BE-1-4", RejectionType.PREAUTHORIZATION),
        ("BE-1-5", RejectionType.PREAUTHORIZATION),
        ("CV-4-10", RejectionType.MEDICATION_DEVICE),
        ("CV-4-7", RejectionType.MEDICATION_DEVICE),
        ("CV-3-4", RejectionType.POLICY_LIMITATION),
        ("AD-3-5", RejectionType.POLICY_LIMITATION),
    ],
)
def test_classify_rejection(engine, code, expected):
    assert engine.classify_rejection(code) == expected


def test_classify_unknown_code(engine):
    result = engine.classify_rejection("ZZ-9-9")
    assert isinstance(result, RejectionType)


def test_classify_empty_code(engine):
    result = engine.classify_rejection("")
    assert result == RejectionType.ADMINISTRATIVE


def test_resubmission_deadline(engine):
    rejection_date = date(2024, 1, 1)
    deadline = engine.calculate_resubmission_deadline(rejection_date)
    assert deadline == date(2024, 1, 16)
    assert (deadline - rejection_date).days == 15


def test_prioritize_claims(engine, sample_claim_lines):
    prioritized = engine.prioritize_claims(sample_claim_lines)
    assert len(prioritized) == len(sample_claim_lines)
    amounts = [c.amount_sar for c in prioritized]
    assert amounts[0] >= amounts[1]


def test_analyze_portfolio(engine, sample_claim_lines):
    stats = engine.analyze_portfolio(sample_claim_lines)
    assert "total_rejected_sar" in stats
    assert "by_type" in stats
    assert "claim_count" in stats
    assert stats["claim_count"] == len(sample_claim_lines)
    total = sum(c.amount_sar for c in sample_claim_lines)
    assert abs(stats["total_rejected_sar"] - total) < 0.01


def test_analyze_portfolio_by_type_breakdown(engine, sample_claim_lines):
    stats = engine.analyze_portfolio(sample_claim_lines)
    by_type = stats["by_type"]
    assert len(by_type) > 0
    for rtype_value in by_type:
        assert isinstance(by_type[rtype_value], float)
