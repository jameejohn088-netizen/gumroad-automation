"""APScheduler manager: DB-persisted jobs (SQLAlchemyJobStore) that survive
restarts. Missed-run policy: misfire_grace_time + coalesce => run once on resume.

Honest execution notes (also in docs/KNOWN_LIMITATIONS.md):
- Local PC: jobs run while this process is alive.
- Cloud 24/7: needs a continuously running server (Docker image provided).
- Android background (WorkManager ~15 min minimum, OS may delay/kill) is NOT
  a substitute — the Android app calls this backend's API instead.
"""
import logging
from datetime import datetime, timezone

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

#: Reference APScheduler calls for DB-persisted jobs.
JOB_FUNC = "app.scheduler.tasks:run_scheduled_job"


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.SCHEDULER_ENABLED:
        log.info("scheduler disabled by config")
        return None
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    jobstores = {"default": SQLAlchemyJobStore(url=settings.DATABASE_URL)}
    _scheduler = BackgroundScheduler(jobstores=jobstores, timezone="UTC")
    _scheduler.start()
    log.info("scheduler started (DB-persisted job store)")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None


def _trigger_for(job) -> dict:
    """Map our job_type + schedule_config to an APScheduler trigger."""
    from app.models.models import ScheduledJob  # noqa: F401  (type hint only)

    cfg = job.schedule_config or {}
    jt = job.job_type
    if jt == "once":
        run_at = cfg.get("run_at")
        dt = datetime.fromisoformat(run_at) if run_at else datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return {"trigger": "date", "run_date": dt}
    if jt == "interval":
        return {"trigger": "interval", "seconds": int(cfg.get("seconds", 3600))}
    if jt == "daily":
        return {"trigger": "cron", "hour": int(cfg.get("hour", 9)),
                "minute": int(cfg.get("minute", 0))}
    if jt == "weekly":
        return {"trigger": "cron", "day_of_week": cfg.get("day_of_week", "mon"),
                "hour": int(cfg.get("hour", 9)), "minute": int(cfg.get("minute", 0))}
    if jt == "sync":
        return {"trigger": "interval",
                "seconds": int(cfg.get("interval_seconds", 900))}
    if jt == "automation":
        # cron string like "0 9 * * *"
        cron = cfg.get("cron", "0 9 * * *").split()
        if len(cron) != 5:
            raise ValueError("automation schedule_config.cron must be 5-field cron")
        minute, hour, day, month, dow = cron
        return {"trigger": "cron", "minute": minute, "hour": hour, "day": day,
                "month": month, "day_of_week": dow}
    raise ValueError(f"unknown job_type: {jt}")


def schedule_job(job) -> None:
    """(Re)register a ScheduledJob row with APScheduler. Updates next_run_at."""
    sched = get_scheduler()
    if sched is None or not sched.running:
        return
    if job.status != "active":
        unschedule_job(job.id)
        return
    trigger_kwargs = _trigger_for(job)
    aps_job = sched.add_job(
        JOB_FUNC,
        id=f"job:{job.id}",
        args=[job.id],
        replace_existing=True,
        misfire_grace_time=3600,  # missed-run policy: run once on resume
        coalesce=True,
        **trigger_kwargs,
    )
    # Persist next_run_at on our row for the UI.
    from app.core.db import get_session_factory
    from app.models.models import ScheduledJob

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        row = db.get(ScheduledJob, job.id)
        if row and aps_job.next_run_time:
            row.next_run_at = aps_job.next_run_time
            db.commit()
    finally:
        db.close()


def unschedule_job(job_id: str) -> None:
    sched = get_scheduler()
    if sched is None or not sched.running:
        return
    try:
        sched.remove_job(f"job:{job_id}")
    except Exception:
        pass
