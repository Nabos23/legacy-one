"""Symmetric encryption for secrets stored at rest (Fernet / AES-128-CBC + HMAC)."""

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from backend.core.config import settings


def _build_key() -> bytes:
    """Return a valid 32-byte url-safe base64 Fernet key.

    Uses ENCRYPTION_KEY if set; otherwise derives a stable key from
    JWT_SECRET_KEY (dev fallback — set ENCRYPTION_KEY in production).
    """
    if settings.ENCRYPTION_KEY:
        return settings.ENCRYPTION_KEY.encode("utf-8")
    digest = hashlib.sha256(settings.JWT_SECRET_KEY.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_build_key())


def encrypt(plaintext: str) -> str:
    """Encrypt a string for storage."""
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """Decrypt a value produced by `encrypt`."""
    return _fernet.decrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_or_none(token: str) -> Optional[str]:
    """`decrypt()`, but returns None instead of raising when the ciphertext
    can't be decrypted with the current key (e.g. ENCRYPTION_KEY rotated, or
    JWT_SECRET_KEY changed since the value was stored under the derived-key
    fallback). Any caller reading a stored secret back for use — as opposed to
    encrypting/decrypting within the same request — should prefer this over
    `decrypt()` so a stale/corrupted secret degrades to "needs reconfiguring"
    instead of a 500."""
    try:
        return decrypt(token)
    except InvalidToken:
        return None


def mask_connection_string(plaintext: str) -> str:
    """Return a display-safe form that hides credentials/host.

    e.g. "postgresql://user:pass@host:5432/db" -> "postgresql://****"
    """
    if "://" in plaintext:
        scheme = plaintext.split("://", 1)[0]
        return f"{scheme}://****"
    return "****"
