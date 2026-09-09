# app/incident/crypto.py
"""Authenticated encryption for sensitive trusted-contact fields at rest.

Trusted-contact destinations (phone/email) are personally-identifying and must
not persist as plaintext. This module provides a thin, centralized boundary so
the persistence layer and API never handle raw plaintext and the encryption
key is never committed to the repository.

DESIGN:
  - Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.
  - The 32-byte URL-safe base64 key is read from the LUMINA_ENCRYPTION_KEY
    environment variable at call time (never pasted into source).
  - FAIL-CLOSED on storage: if no key is configured we refuse to encrypt
    (raising) rather than silently persisting plaintext.
  - LEGACY-PLAINTEXT SAFE on read: a stored value that is not a Fernet token
    (i.e. a value written before encryption was enabled) is returned unchanged
    so existing rows keep working; it is re-encrypted on the next save.
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

_ENV_KEY = "LUMINA_ENCRYPTION_KEY"

# Fernet v0 tokens always begin with this fixed 9-byte header (b"gAAAA").
_FERNET_HEADER = b"gAAAA"


def _get_fernet() -> Optional[Fernet]:
    """Build a Fernet instance from the env key, or None if not configured."""
    raw = os.environ.get(_ENV_KEY, "").strip()
    if not raw:
        return None
    raw_bytes = raw.encode("utf-8")
    try:
        key = base64.urlsafe_b64decode(raw_bytes)
    except Exception:
        # The variable may hold a raw 32-byte secret; derive a Fernet key.
        key = hashlib.sha256(raw_bytes).digest()
    if len(key) != 32:
        # Derive a stable 32-byte key from whatever was supplied.
        key = hashlib.sha256(raw_bytes).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _is_fernet_token(value: str) -> bool:
    try:
        return value.encode("utf-8").startswith(_FERNET_HEADER)
    except Exception:
        return False


def encrypt_contact_field(plaintext: str) -> str:
    """Encrypt a sensitive contact field for storage.

    Fail-closed: raises when no encryption key is configured so we never
    silently write plaintext. Returns an empty string for empty input.
    """
    if not plaintext:
        return ""
    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError(
            f"{_ENV_KEY} is not set; refusing to persist trusted-contact "
            "plaintext. Configure the encryption key before saving contacts."
        )
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_contact_field(ciphertext: str) -> str:
    """Decrypt a stored contact field.

    Returns plaintext unchanged when the value is legacy plaintext (not a
    Fernet token), so pre-encryption rows remain usable.
    """
    if not ciphertext:
        return ""
    if not _is_fernet_token(ciphertext):
        return ciphertext
    fernet = _get_fernet()
    if fernet is None:
        # Cannot decrypt without a key; fail closed rather than leaking the
        # stored token as if it were plaintext.
        raise RuntimeError(
            f"{_ENV_KEY} is not set; cannot decrypt stored trusted-contact field."
        )
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ciphertext


def generate_encryption_key() -> str:
    """Generate a new Fernet key for operator setup (printed once)."""
    return Fernet.generate_key().decode("utf-8")
