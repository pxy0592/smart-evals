import pytest
from cryptography.fernet import Fernet

from services.credential_cipher import CredentialCipher, CredentialError, redact_secret


def test_encrypt_decrypt_and_fingerprint():
    cipher = CredentialCipher(Fernet.generate_key())
    encrypted = cipher.encrypt("sk-secret-value")
    assert "sk-secret-value" not in encrypted
    assert cipher.decrypt(encrypted) == "sk-secret-value"
    assert cipher.fingerprint("sk-secret-value") == cipher.fingerprint("sk-secret-value")


def test_missing_key_fails_closed(monkeypatch):
    monkeypatch.delenv("RAG_CREDENTIAL_ENCRYPTION_KEY", raising=False)
    with pytest.raises(CredentialError):
        CredentialCipher()


def test_mask_value_is_not_accepted():
    cipher = CredentialCipher(Fernet.generate_key())
    with pytest.raises(CredentialError):
        cipher.encrypt("sk-****")


def test_redaction():
    assert redact_secret("key=secret", ["secret"]) == "key=***"
