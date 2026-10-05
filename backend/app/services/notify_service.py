"""In-app notifications + activity logging helpers."""
from sqlalchemy.orm import Session

from app.models.models import ActivityLog, Notification


def notify(
    db: Session,
    user_id: str,
    title: str,
    body: str | None = None,
    kind: str = "info",
    account_id: str | None = None,
) -> Notification:
    n = Notification(user_id=user_id, account_id=account_id, title=title, body=body, kind=kind)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def log_activity(
    db: Session,
    action: str,
    user_id: str | None = None,
    account_id: str | None = None,
    detail: dict | None = None,
) -> None:
    db.add(ActivityLog(user_id=user_id, account_id=account_id, action=action, detail=detail or {}))
    db.commit()
