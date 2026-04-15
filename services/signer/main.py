import hmac as hmac_lib
import hashlib
import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any
import json
from core.security import AESCipher, generate_hmac

app = FastAPI(title="Signer Service")


class SignerService:
    def __init__(self, key: bytes = None):
        self._aes = AESCipher(key)
        self._hmac_key = os.urandom(32).hex()

    def sign_payload(self, payload: dict, private_key: str) -> str:
        data = json.dumps(payload, sort_keys=True, default=str)
        return generate_hmac(data, private_key)

    def verify_signature(self, payload: dict, signature: str, key: str) -> bool:
        expected = self.sign_payload(payload, key)
        return hmac_lib.compare_digest(expected, signature)

    def encrypt_phi(self, data: dict) -> dict:
        phi_fields = {"patient_id", "name", "dob", "nric"}
        result = dict(data)
        for field in phi_fields:
            if field in result:
                encrypted = self._aes.encrypt(str(result[field]))
                result[field] = encrypted
        return result

    def decrypt_phi(self, data: dict, key: bytes) -> dict:
        cipher = AESCipher(key)
        result = dict(data)
        phi_fields = {"patient_id", "name", "dob", "nric"}
        for field in phi_fields:
            if field in result and isinstance(result[field], dict) and "ciphertext" in result[field]:
                result[field] = cipher.decrypt(result[field]["ciphertext"], result[field]["nonce"])
        return result


signer = SignerService()


class SignRequest(BaseModel):
    payload: dict
    key: str


class VerifyRequest(BaseModel):
    payload: dict
    signature: str
    key: str


@app.post("/sign")
def sign(req: SignRequest):
    sig = signer.sign_payload(req.payload, req.key)
    return {"signature": sig}


@app.post("/verify")
def verify(req: VerifyRequest):
    valid = signer.verify_signature(req.payload, req.signature, req.key)
    return {"valid": valid}


@app.get("/health")
def health():
    return {"status": "ok", "service": "signer"}
