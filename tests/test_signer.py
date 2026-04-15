import pytest
import os
from services.signer.main import SignerService
from core.security import AESCipher, generate_hmac


@pytest.fixture
def signer():
    return SignerService()


def test_sign_payload(signer):
    payload = {"claim_id": "CL-001", "amount": 5000}
    key = "test-secret-key"
    sig = signer.sign_payload(payload, key)
    assert isinstance(sig, str)
    assert len(sig) == 64


def test_verify_signature_valid(signer):
    payload = {"claim_id": "CL-001", "amount": 5000}
    key = "test-secret-key"
    sig = signer.sign_payload(payload, key)
    assert signer.verify_signature(payload, sig, key) is True


def test_verify_signature_invalid(signer):
    payload = {"claim_id": "CL-001", "amount": 5000}
    key = "test-secret-key"
    assert signer.verify_signature(payload, "wrongsig", key) is False


def test_encrypt_phi(signer):
    data = {"patient_id": "PAT-12345", "amount": 1000}
    encrypted = signer.encrypt_phi(data)
    assert isinstance(encrypted["patient_id"], dict)
    assert "ciphertext" in encrypted["patient_id"]
    assert encrypted["amount"] == 1000


def test_decrypt_phi(signer):
    data = {"patient_id": "PAT-12345", "amount": 1000}
    encrypted = signer.encrypt_phi(data)
    decrypted = signer.decrypt_phi(encrypted, signer._aes.key)
    assert decrypted["patient_id"] == "PAT-12345"


def test_aes_cipher_roundtrip():
    cipher = AESCipher()
    original = "sensitive patient data"
    enc = cipher.encrypt(original)
    dec = cipher.decrypt(enc["ciphertext"], enc["nonce"])
    assert dec == original


def test_generate_hmac():
    sig = generate_hmac("test data", "secret")
    assert len(sig) == 64
    sig2 = generate_hmac("test data", "secret")
    assert sig == sig2
