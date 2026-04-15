import pytest
from core.security import PHIMasker, AESCipher, RBACPolicy, check_permission, generate_hmac


def test_phi_masker_patient_id():
    masked = PHIMasker.mask_patient_id("PAT-12345")
    assert "***" in masked
    assert "2345" in masked


def test_phi_masker_short_id():
    masked = PHIMasker.mask_patient_id("AB")
    assert "***" in masked


def test_phi_masker_name():
    masked = PHIMasker.mask_name("John Smith")
    assert "J." in masked
    assert "S." in masked


def test_phi_masker_dict():
    data = {"patient_id": "PAT-12345", "name": "John Smith", "amount": 5000}
    masked = PHIMasker.mask_phi_dict(data)
    assert "***" in masked["patient_id"]
    assert masked["amount"] == 5000


def test_aes_encrypt_decrypt():
    cipher = AESCipher()
    plaintext = "sensitive-patient-data-12345"
    enc = cipher.encrypt(plaintext)
    assert "ciphertext" in enc
    assert "nonce" in enc
    dec = cipher.decrypt(enc["ciphertext"], enc["nonce"])
    assert dec == plaintext


def test_aes_different_keys():
    cipher1 = AESCipher()
    cipher2 = AESCipher()
    enc = cipher1.encrypt("test")
    with pytest.raises(Exception):
        cipher2.decrypt(enc["ciphertext"], enc["nonce"])


def test_rbac_billing_admin():
    policy = RBACPolicy()
    assert policy.check_permission("billing_admin", "submit_claims") is True
    assert policy.check_permission("billing_admin", "approve_appeal") is False


def test_rbac_clinical_reviewer():
    policy = RBACPolicy()
    assert policy.check_permission("clinical_reviewer", "approve_appeal") is True
    assert policy.check_permission("clinical_reviewer", "submit_claims") is False


def test_rbac_compliance_officer():
    policy = RBACPolicy()
    assert policy.check_permission("compliance_officer", "check_compliance") is True


def test_rbac_auditor():
    policy = RBACPolicy()
    assert policy.check_permission("auditor", "view_audit_log") is True
    assert policy.check_permission("auditor", "submit_claims") is False


def test_rbac_unknown_role():
    assert check_permission("unknown_role", "anything") is False


def test_generate_hmac_consistent():
    sig1 = generate_hmac("data", "key")
    sig2 = generate_hmac("data", "key")
    assert sig1 == sig2


def test_generate_hmac_different_keys():
    sig1 = generate_hmac("data", "key1")
    sig2 = generate_hmac("data", "key2")
    assert sig1 != sig2
