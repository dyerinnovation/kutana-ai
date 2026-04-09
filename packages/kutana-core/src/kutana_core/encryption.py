"""Symmetric encryption for sensitive values (e.g. user-provided API keys).

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography library.
The encryption key is loaded from the ENCRYPTION_KEY environment variable.
"""

from __future__ import annotations

import logging
import os

from cryptography.fernet import Fernet, InvalidToken  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Get or create the Fernet cipher instance.

    Returns:
        A Fernet instance initialized from ENCRYPTION_KEY env var.

    Raises:
        RuntimeError: If ENCRYPTION_KEY is not set.
    """
    global _fernet
    if _fernet is not None:
        return _fernet

    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY not set. Generate one with: "
            "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    _fernet = Fernet(key.encode())
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string.

    Args:
        plaintext: The value to encrypt.

    Returns:
        Base64-encoded ciphertext string.
    """
    f = _get_fernet()
    return str(f.encrypt(plaintext.encode()).decode())


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string.

    Args:
        ciphertext: The base64-encoded ciphertext.

    Returns:
        The decrypted plaintext string.

    Raises:
        ValueError: If decryption fails (wrong key or tampered data).
    """
    f = _get_fernet()
    try:
        return str(f.decrypt(ciphertext.encode()).decode())
    except InvalidToken as e:
        raise ValueError("Decryption failed: invalid key or corrupted data") from e
