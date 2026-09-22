"""Encryption for secrets at rest (DB passwords, Tableau PATs).

Decrypted values must never be logged, persisted, or passed into the LLM
prompt context (see app/llm/planner.py, which only ever receives
SchemaContext/SampleContext DTOs, never a Connection/secret).
"""
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class EncryptionNotConfiguredError(RuntimeError):
    pass


def _fernet() -> Fernet:
    if not settings.encryption_key:
        raise EncryptionNotConfiguredError(
            "ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` and set it in .env."
        )
    return Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode()
    except InvalidToken as exc:
        raise ValueError("Stored secret could not be decrypted (bad key or corrupt data).") from exc
