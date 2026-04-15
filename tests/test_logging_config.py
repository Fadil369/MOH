import pytest
from core.logging_config import configure_logging, get_logger, phi_masking_processor


def test_configure_logging_runs():
    configure_logging()


def test_get_logger_returns_logger():
    logger = get_logger("test_module")
    assert logger is not None


def test_phi_masking_patient_id():
    event = {"patient_id": "PAT-12345", "event": "test"}
    result = phi_masking_processor(None, None, event)
    assert result["patient_id"].startswith("***-XX-")
    assert "2345" in result["patient_id"]


def test_phi_masking_short_patient_id():
    event = {"patient_id": "AB", "event": "test"}
    result = phi_masking_processor(None, None, event)
    assert result["patient_id"] == "***REDACTED***"


def test_phi_masking_name():
    event = {"name": "John Smith", "event": "test"}
    result = phi_masking_processor(None, None, event)
    assert result["name"] == "***REDACTED***"


def test_phi_masking_no_phi():
    event = {"claim_id": "CL-001", "amount": 5000}
    result = phi_masking_processor(None, None, event)
    assert result["claim_id"] == "CL-001"
    assert result["amount"] == 5000
