"""Encryption boundary for stored RAG provider credentials."""
from __future__ import annotations

import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


class CredentialError(RuntimeError):
    pass


class CredentialCipher:
    def __init__(self, key: str | bytes | None = None):
        raw = key or os.getenv("RAG_CREDENTIAL_ENCRYPTION_KEY", "")
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        if not raw:
            raise CredentialError("RAG_CREDENTIAL_ENCRYPTION_KEY 未配置")
        try:
            self._fernet = Fernet(raw)
        except (ValueError, TypeError) as exc:
            raise CredentialError("RAG_CREDENTIAL_ENCRYPTION_KEY 格式无效") from exc

    def encrypt(self, secret: str) -> str:
        value = (secret or "").strip()
        if not value or "*" in value:
            raise CredentialError("API Key 不能为空或使用掩码值")
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, TypeError) as exc:
            raise CredentialError("无法解密 RAG 系统凭据") from exc

    @staticmethod
    def fingerprint(secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]


def redact_secret(value: str, secrets: list[str] | tuple[str, ...]) -> str:
    result = str(value)
    for secret in secrets:
        if secret:
            result = result.replace(secret, "***")
    return result
