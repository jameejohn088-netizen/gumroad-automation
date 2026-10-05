"""User authentication service: signup, login, logout, refresh rotation,
forgot/reset password, email verification, change password.

Security rules:
- argon2id password hashing
- generic error messages (no user enumeration anywhere)
- rate limiting + lockout on login and reset endpoints (enforced in routers)
- opaque refresh/reset tokens stored as SHA-256 hashes, single-use
"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import mailer
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    utcnow,
    verify_password,
)
from app.models.models import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    User,
)

GENERIC_LOGIN_ERROR = "Invalid email or password."
GENERIC_FORGOT_MESSAGE = "If an account exists for that email, a reset link was sent."


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower().strip()))


def signup(db: Session, email: str, password: str, name: str) -> User:
    email = email.lower().strip()
    if get_user_by_email(db, email):
        # No enumeration: behave as if created (caller returns 201 anyway),
        # but do not create a duplicate or send mail.
        raise _Exists()
    user = User(email=email, password_hash=hash_password(password), name=name or "")
    db.add(user)
    db.flush()
    token = new_opaque_token()
    db.add(EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(hours=24),
    ))
    db.commit()
    db.refresh(user)
    mailer.send_email(email, "Verify your email", mailer.verification_email_body(token))
    return user


class _Exists(Exception):
    pass


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user on success, None on failure (generic — no enumeration)."""
    user = get_user_by_email(db, email)
    now = utcnow()
    if user and user.locked_until and user.locked_until > now:
        return None
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now + timedelta(minutes=15)
            db.commit()
        return None
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return user


def issue_token_pair(db: Session, user: User, refresh_days: int) -> tuple[str, str]:
    from app.core.config import get_settings

    settings = get_settings()
    access = create_access_token(user.id, settings.SECRET_KEY, settings.ACCESS_TOKEN_MINUTES)
    raw_refresh = new_opaque_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=utcnow() + timedelta(days=refresh_days),
    ))
    db.commit()
    return access, raw_refresh


def rotate_refresh_token(db: Session, raw_refresh: str, refresh_days: int) -> tuple[str, str] | None:
    """Validate + single-use rotate. Returns new pair or None."""
    from app.core.config import get_settings

    rec = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh)))
    if not rec or rec.revoked_at or rec.expires_at < utcnow():
        return None
    user = db.get(User, rec.user_id)
    if not user or not user.is_active:
        return None
    settings = get_settings()
    new_raw = new_opaque_token()
    new_rec = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_raw),
        expires_at=utcnow() + timedelta(days=refresh_days),
    )
    db.add(new_rec)
    db.flush()
    rec.revoked_at = utcnow()
    rec.replaced_by = new_rec.id
    db.commit()
    access = create_access_token(user.id, settings.SECRET_KEY, settings.ACCESS_TOKEN_MINUTES)
    return access, new_raw


def revoke_refresh_token(db: Session, raw_refresh: str) -> None:
    rec = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh)))
    if rec and not rec.revoked_at:
        rec.revoked_at = utcnow()
        db.commit()


def request_password_reset(db: Session, email: str) -> None:
    """Always generic — never reveal whether the email exists."""
    user = get_user_by_email(db, email)
    if user and user.is_active:
        token = new_opaque_token()
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(hours=1),
        ))
        db.commit()
        mailer.send_email(email, "Reset your password", mailer.password_reset_email_body(token))


def reset_password(db: Session, token: str, new_password: str) -> bool:
    rec = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
    )
    if not rec or rec.used_at or rec.expires_at < utcnow():
        return False
    user = db.get(User, rec.user_id)
    if not user or not user.is_active:
        return False
    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    rec.used_at = utcnow()
    # Revoke all refresh tokens on password reset.
    for rt in db.scalars(select(RefreshToken).where(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    )):
        rt.revoked_at = utcnow()
    db.commit()
    return True


def verify_email(db: Session, token: str) -> bool:
    rec = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_token(token))
    )
    if not rec or rec.used_at or rec.expires_at < utcnow():
        return False
    user = db.get(User, rec.user_id)
    if not user:
        return False
    user.is_verified = True
    rec.used_at = utcnow()
    db.commit()
    return True


def change_password(db: Session, user: User, current_password: str, new_password: str) -> bool:
    if not verify_password(current_password, user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    db.commit()
    return True
