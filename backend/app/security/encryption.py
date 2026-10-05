"""Gumroad OAuth tokens encrypted at rest with AES-GCM.

- Master key comes from the TOKEN_MASTER_KEY env var (base64, 32 bytes).
- Every encrypted value stores key_version so keys can be rotated later.
- Plaintext tokens are never logged and never leave this module except
  to the Gumroad API client.
"""
import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_VERSION = 1


def _master_key() -> bytes:
    from app.core.config import get_settings

    raw = get_settings().TOKEN_MASTER_KEY.strip()
    if not raw:
        raise RuntimeError("TOKEN_MASTER_KEY is not configured")
    try:
        key = base64.b64decode(raw)
    except Exception as exc:
        raise RuntimeError("TOKEN_MASTER_KEY is not valid base64") from exc
    if len(key) != 32:
        raise RuntimeError("TOKEN_MASTER_KEY must decode to 32 bytes")
    return key


def encrypt_token(plaintext: str) -> tuple[str, int]:
    """Return (base64 ciphertext incl. nonce, key_version)."""
    aesgcm = AESGCM(_master_key())
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii"), KEY_VERSION


def decrypt_token(ciphertext_b64: str, key_version: int) -> str:
    if key_version != KEY_VERSION:
        raise RuntimeError(f"unsupported token key_version={key_version}")
    raw = base64.b64decode(ciphertext_b64)
    nonce, ct = raw[:12], raw[12:]
    try:
        pt = AESGCM(_master_key()).decrypt(nonce, ct, None)
    except InvalidTag as exc:
        raise RuntimeError("token decryption failed") from exc
    return pt.decode("utf-8")


def token_last4(plaintext: str) -> str:
    return plaintext[-4:] if len(plaintext) >= 4 else "****"
