"""FastAPI dependencies: auth, account scoping, pagination, rate limiting."""
import uuid

from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import rate_limiter
from app.core.security import decode_access_token
from app.models.models import GumroadAccount, User

settings = get_settings()


def get_correlation_id(request: Request) -> str:
    cid = request.headers.get("X-Correlation-ID") or request.state.correlation_id
    return cid


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated")
    payload = decode_access_token(authorization.split(" ", 1)[1], settings.SECRET_KEY)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token")
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token")
    return user


def get_account(user: User = Depends(get_current_user),
                db: Session = Depends(get_db),
                account_id: str = "") -> GumroadAccount:
    """Single account, strictly scoped to the logged-in user."""
    acct = db.scalar(select(GumroadAccount).where(
        GumroadAccount.id == account_id, GumroadAccount.user_id == user.id))
    if acct is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return acct


def resolve_accounts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    account_id: str | None = Query(default=None),
) -> list[GumroadAccount]:
    """?account_id= -> that account only; omitted -> union of user's accounts."""
    q = select(GumroadAccount).where(GumroadAccount.user_id == user.id)
    if account_id:
        q = q.where(GumroadAccount.id == account_id)
        acct = db.scalar(q)
        if acct is None:
            raise HTTPException(status_code=404, detail="Account not found")
        return [acct]
    return list(db.scalars(q.order_by(GumroadAccount.created_at)).all())


def pagination(page: int = Query(default=1, ge=1),
               per_page: int = Query(default=25, ge=1, le=200)) -> tuple[int, int]:
    return page, per_page


def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    allowed, retry_after = rate_limiter.check(key, limit, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:16]
