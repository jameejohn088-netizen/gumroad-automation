"""Self-diagnostics: backend health, DB, migrations, Gumroad auth, sync, env config.

All checks are read-only and never expose secrets — only present/missing and
counts. This powers the Diagnostics page in the web dashboard.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.models.models import ErrorLog, GumroadAccount, SyncHistory, User

router = APIRouter(tags=["diagnostics"])


def _ok(ok: bool, detail: str = "") -> dict:
    return {"status": "PASS" if ok else "FAIL", "detail": detail}


@router.get("/diagnostics")
def diagnostics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    settings = get_settings()
    checks: dict[str, dict] = {}

    # 1. Database connectivity.
    try:
        db.execute(text("SELECT 1"))
        table_count = db.scalar(text(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'")) or 0
        checks["database"] = _ok(True, f"connected, {table_count} tables")
    except Exception as e:  # noqa: BLE001
        checks["database"] = _ok(False, f"{type(e).__name__}")

    # 2. Migration status.
    try:
        ver = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        checks["migrations"] = _ok(bool(ver), f"alembic head: {ver or 'not stamped'}")
    except Exception:  # noqa: BLE001
        checks["migrations"] = _ok(False, "alembic_version table missing")

    # 3. Environment config (presence only, never values).
    required = {"SECRET_KEY": bool(settings.SECRET_KEY and settings.SECRET_KEY != "change-me-to-a-long-random-string"),
                "TOKEN_MASTER_KEY": bool(settings.TOKEN_MASTER_KEY),
                "DATABASE_URL": bool(settings.DATABASE_URL)}
    missing = [k for k, v in required.items() if not v]
    checks["env_config"] = _ok(not missing,
                               "all present" if not missing else f"missing: {', '.join(missing)}")

    # 4. Gumroad accounts: authorized vs error state (no live API calls here).
    accounts = db.scalars(select(GumroadAccount).where(
        GumroadAccount.user_id == user.id)).all()
    with_creds = sum(1 for a in accounts if a.credential is not None)
    errored = [{"account_id": a.id, "label": a.label, "last_error": a.last_error}
               for a in accounts if a.last_error]
    checks["gumroad_auth"] = _ok(
        with_creds > 0 or not accounts,
        f"{with_creds}/{len(accounts)} accounts have stored credentials"
        + (f"; {len(errored)} in error" if errored else ""))
    checks["gumroad_auth"]["errored_accounts"] = errored

    # 5. Sync engine: recent history.
    recent = db.scalars(select(SyncHistory).where(
        SyncHistory.user_id == user.id).order_by(
        SyncHistory.created_at.desc()).limit(5)).all()
    failed = sum(1 for s in recent if s.status == "failed")
    checks["sync"] = _ok(failed == 0,
                         f"{len(recent)} recent syncs, {failed} failed" if recent
                         else "no syncs run yet")
    checks["sync"]["recent"] = [
        {"account_id": s.account_id, "status": s.status,
         "items_synced": s.items_synced,
         "created_at": s.created_at.isoformat() if s.created_at else None}
        for s in recent]

    # 6. Scheduler: is the background scheduler thread alive?
    try:
        from app.scheduler.scheduler import is_running as sched_running
        running = sched_running()
    except Exception:  # noqa: BLE001
        running = False
    checks["scheduler"] = _ok(running, "running" if running else "not running")

    # 7. Recent error log entries (last 24h count).
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    err_count = db.scalar(select(func.count(ErrorLog.id)).where(
        ErrorLog.user_id == user.id, ErrorLog.created_at >= since)) or 0
    checks["error_log"] = _ok(err_count == 0, f"{err_count} errors in last 24h")

    overall = "PASS" if all(c["status"] == "PASS" for c in checks.values()) else "FAIL"
    return {"overall": overall, "checks": checks}
