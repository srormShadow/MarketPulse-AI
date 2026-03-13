"""Encryption helpers for sensitive third-party tokens."""

from __future__ import annotations

import base64
import hashlib

from marketpulse.core.config import get_settings


class TokenEncryptionError(RuntimeError):
    """Raised when token encryption prerequisites are not satisfied."""


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise TokenEncryptionError(
            "cryptography is required for token encryption. Install dependencies from requirements.txt."
        ) from exc

    settings = get_settings()
    raw_key = (settings.shopify_token_encryption_key or settings.jwt_secret).strip()
    if not raw_key or raw_key == "change-me-in-production":
        raise TokenEncryptionError("A strong SHOPIFY_TOKEN_ENCRYPTION_KEY must be configured.")
    derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode("utf-8")).digest())
    return Fernet(derived)


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    value = (ciphertext or "").strip()
    if not value:
        return ""
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
