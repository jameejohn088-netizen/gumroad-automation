"""Job functions executed by APScheduler. Each creates its own DB session
(the scheduler runs outside request scope).

Retry policy: exponential backoff (2^attempt minutes), max_retries from the
job row, then dead-letter state. Manual re-run via the API calls
run_scheduled_job() directly.
"""
import logging
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.db import get_session_factory
from app.core.security import utcnow
from app.models.models import JobExecution, ScheduledJob

log = logging.getLogger(__name__)

RETRY_BASE_MINUTES = 2


def _utcnow():
    return datetime.now(timezone.utc)


def run_scheduled_job(job_id: str, _attempt: int = 1) -> dict:
    """Main entry point. Returns a result dict; never raises to APScheduler."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    execution = None
    try:
        job = db.get(ScheduledJob, job_id)
        if job is None:
            return {"status": "error", "error": "job not found"}
        if job.status not in ("active",):
            return {"status": "skipped", "reason": f"job status={job.status}"}

        execution = JobExecution(job_id=job.id, status="running",
                                 started_at=_utcnow(), attempt=_attempt)
        db.add(execution)
        db.commit()

        result = _dispatch(db, job)

        execution.status = "success"
        execution.finished_at = _utcnow()
        execution.result = result
        job.last_run_at = _utcnow()
        job.retry_count = 0
        job.last_error = None
        if job.job_type == "once":
            job.status = "completed"
        db.commit()
        log.info("job success id=%s type=%s", job.id, job.job_type)
        return {"status": "success", "result": result}
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"[:1000]
        log.warning("job failed id=%s attempt=%d err=%s", job_id, _attempt, err)
        try:
            if execution is not None:
                execution.status = "failed"
                execution.finished_at = _utcnow()
                execution.error = err + "\n" + traceback.format_exc()[-2000:]
            job = db.get(ScheduledJob, job_id)
            if job is not None:
                job.last_run_at = _utcnow()
                job.last_error = err
                job.retry_count = _attempt
                if _attempt > job.max_retries:
                    job.status = "dead"
                    if execution is not None:
                        execution.status = "dead"
                    log.error("job dead-lettered id=%s", job_id)
                else:
                    delay = timedelta(minutes=RETRY_BASE_MINUTES * (2 ** (_attempt - 1)))
                    job.next_run_at = _utcnow() + delay
                    _schedule_retry(job.id, _attempt + 1, delay)
            db.commit()
        except Exception:
            log.exception("job failure bookkeeping failed")
            db.rollback()
        return {"status": "failed", "error": err}
    finally:
        db.close()


def _dispatch(db, job: ScheduledJob) -> dict:
    cfg = job.schedule_config or {}
    payload = job.payload or {}
    kind = payload.get("kind", job.job_type)

    if job.job_type == "sync" or kind == "sync":
        from app.services.sync_service import sync_account

        account_id = job.account_id or cfg.get("account_id") or payload.get("account_id")
        if not account_id:
            raise ValueError("sync job needs an account_id")
        return sync_account(db, account_id, sync_type=cfg.get("sync_type", "full"),
                            fire_events=True)

    if job.job_type == "automation" or kind == "automation":
        from app.automation.engine import run_scheduled_rule

        rule_id = payload.get("rule_id") or cfg.get("rule_id")
        if not rule_id:
            raise ValueError("automation job needs payload.rule_id")
        ex = run_scheduled_rule(db, rule_id)
        return {"execution_id": ex.id if ex else None,
                "status": ex.status if ex else "skipped"}

    if kind == "daily_summary":
        return _daily_summary(db, job)

    raise ValueError(f"unsupported job kind/type: {kind}/{job.job_type}")


def _daily_summary(db, job: ScheduledJob) -> dict:
    from app.services import account_service
    from app.services.notify_service import notify

    accounts = account_service.user_accounts(db, job.user_id)
    lines = []
    for acct in accounts:
        if job.account_id and acct.id != job.account_id:
            continue
        from sqlalchemy import func
        from app.models.models import Sale
        revenue = db.scalar(select(func.coalesce(func.sum(Sale.price_cents), 0)).where(
            Sale.account_id == acct.id, Sale.refunded.is_(False))) or 0
        count = db.scalar(select(func.count(Sale.id)).where(Sale.account_id == acct.id)) or 0
        lines.append(f"{acct.name}: {count} sales, {revenue / 100:.2f} revenue")
    notify(db, job.user_id, title="Daily summary",
           body="\n".join(lines) or "No accounts.", kind="summary",
           account_id=job.account_id)
    return {"accounts": len(lines)}


def _schedule_retry(job_id: str, next_attempt: int, delay: timedelta) -> None:
    """Ask the running scheduler to retry later. No-op if scheduler is down
    (the persisted next_run_at still documents intent)."""
    try:
        from app.scheduler.scheduler import get_scheduler

        sched = get_scheduler()
        if sched and sched.running:
            run_at = datetime.now(timezone.utc) + delay
            sched.add_job(
                "app.scheduler.tasks:run_scheduled_job",
                trigger="date", run_date=run_at,
                args=[job_id, next_attempt],
                id=f"{job_id}:retry:{next_attempt}",
                replace_existing=True,
                misfire_grace_time=3600, coalesce=True,
            )
    except Exception:
        log.warning("could not schedule retry; next_run_at persisted", exc_info=True)


def retry_execution(execution_id: str) -> dict:
    """Manual re-run of a failed/dead execution (API: POST /executions/{id}/retry)."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        execution = db.get(JobExecution, execution_id)
        if execution is None:
            return {"status": "error", "error": "execution not found"}
        job = db.get(ScheduledJob, execution.job_id)
        if job is None:
            return {"status": "error", "error": "job not found"}
        if job.status == "dead":
            job.status = "active"
            job.retry_count = 0
        db.commit()
        return run_scheduled_job(job.id, _attempt=execution.attempt + 1)
    finally:
        db.close()
