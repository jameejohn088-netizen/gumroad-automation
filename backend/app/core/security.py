"""Authentication primitives: argon2id password hashing, JWT access tokens,
opaque refresh/reset tokens. No user enumeration helpers live here."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()  # argon2id by default


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Passwords (argon2id) ---

def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# --- Opaque tokens (refresh / password-reset / email verification) ---

def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Store only the SHA-256 of opaque tokens so a DB leak does not expose them."""
    return hashlib.sha256(token.encode()).hexdigest()


# --- JWT access tokens (short-lived) ---

def create_access_token(user_id: str, secret_key: str, minutes: int) -> str:
    now = utcnow()
    payload = {
        "sub": user_id,
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_access_token(token: str, secret_key: str) -> dict | None:
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


# --- Email masking for logs (never log raw emails) ---

def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "***"
    local, domain = email.rsplit("@", 1)
    shown = local[:2] if len(local) > 2 else local[:1]
    return f"{shown}***@{domain}"
