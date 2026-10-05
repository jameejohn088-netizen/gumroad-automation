"""Notifications, activity logs, error logs (all user-scoped)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.models import ActivityLog, ErrorLog, Notification, User
from app.schemas.schemas import ActivityLogOut, ErrorLogOut, NotificationOut

router = APIRouter(tags=["notifications", "logs"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db),
                       user: User = Depends(get_current_user),
                       unread_only: bool = Query(default=False),
                       limit: int = Query(default=50, ge=1, le=200)):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    rows = db.scalars(q.order_by(Notification.created_at.desc()).limit(limit)).all()
    return rows


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    from app.core.security import utcnow
    n.read_at = utcnow()
    db.commit()
    return {"ok": True}


@router.get("/notifications/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == user.id, Notification.read_at.is_(None))) or 0
    return {"unread": n}


@router.get("/activity-logs", response_model=list[ActivityLogOut])
def activity_logs(db: Session = Depends(get_db),
                  user: User = Depends(get_current_user),
                  limit: int = Query(default=100, ge=1, le=500)):
    rows = db.scalars(select(ActivityLog).where(ActivityLog.user_id == user.id)
                      .order_by(ActivityLog.created_at.desc()).limit(limit)).all()
    return rows


@router.get("/error-logs", response_model=list[ErrorLogOut])
def error_logs(db: Session = Depends(get_db),
               user: User = Depends(get_current_user),
               limit: int = Query(default=100, ge=1, le=500)):
    rows = db.scalars(select(ErrorLog).where(ErrorLog.user_id == user.id)
                      .order_by(ErrorLog.created_at.desc()).limit(limit)).all()
    return rows
