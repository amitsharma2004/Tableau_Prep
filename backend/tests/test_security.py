import pytest
from cryptography.fernet import Fernet

from app.core import security
from app.core.security import EncryptionNotConfiguredError


def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setattr(security.settings, "encryption_key", Fernet.generate_key().decode())

    secret = "super-secret-db-password"
    ciphertext = security.encrypt(secret)

    assert ciphertext != secret.encode()
    assert security.decrypt(ciphertext) == secret


def test_decrypt_rejects_tampered_ciphertext(monkeypatch):
    monkeypatch.setattr(security.settings, "encryption_key", Fernet.generate_key().decode())

    ciphertext = bytearray(security.encrypt("password123"))
    ciphertext[-1] ^= 0xFF  # flip bits to corrupt

    with pytest.raises(ValueError):
        security.decrypt(bytes(ciphertext))


def test_missing_key_raises_configuration_error(monkeypatch):
    monkeypatch.setattr(security.settings, "encryption_key", "")

    with pytest.raises(EncryptionNotConfiguredError):
        security.encrypt("anything")
