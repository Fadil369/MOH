import hmac
import hashlib
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import Any


class PHIMasker:
    @staticmethod
    def mask_patient_id(patient_id: str) -> str:
        if not patient_id:
            return "***"
        return f"***-XX-{patient_id[-4:].upper() if len(patient_id) >= 4 else 'XXXX'}"

    @staticmethod
    def mask_name(name: str) -> str:
        if not name:
            return "***"
        parts = name.split()
        return " ".join(p[0] + "." for p in parts if p)

    @staticmethod
    def mask_phi_dict(data: dict) -> dict:
        masked = dict(data)
        phi_fields = {"patient_id", "name", "dob", "nric", "national_id"}
        for field in phi_fields:
            if field in masked:
                if field == "patient_id":
                    masked[field] = PHIMasker.mask_patient_id(str(masked[field]))
                elif field == "name":
                    masked[field] = PHIMasker.mask_name(str(masked[field]))
                else:
                    masked[field] = "***REDACTED***"
        return masked


class AESCipher:
    def __init__(self, key: bytes = None):
        self.key = key or os.urandom(32)

    def encrypt(self, plaintext: str) -> dict:
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "nonce": base64.b64encode(nonce).decode(),
        }

    def decrypt(self, ciphertext_b64: str, nonce_b64: str) -> str:
        aesgcm = AESGCM(self.key)
        ciphertext = base64.b64decode(ciphertext_b64)
        nonce = base64.b64decode(nonce_b64)
        return aesgcm.decrypt(nonce, ciphertext, None).decode()


ROLES_PERMISSIONS = {
    "billing_admin": {"read_claims", "submit_claims", "view_dashboard"},
    "clinical_reviewer": {"read_claims", "review_clinical", "approve_appeal"},
    "compliance_officer": {"read_claims", "view_audit_log", "check_compliance"},
    "auditor": {"read_claims", "view_audit_log"},
}


class RBACPolicy:
    def __init__(self):
        self.roles = ROLES_PERMISSIONS

    def check_permission(self, role: str, action: str) -> bool:
        return action in self.roles.get(role, set())

    def get_permissions(self, role: str) -> set:
        return self.roles.get(role, set())


def check_permission(role: str, action: str) -> bool:
    policy = RBACPolicy()
    return policy.check_permission(role, action)


def generate_hmac(data: str, key: str) -> str:
    h = hmac.new(key.encode(), data.encode(), hashlib.sha256)
    return h.hexdigest()
