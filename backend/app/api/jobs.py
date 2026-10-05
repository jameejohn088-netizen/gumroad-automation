"""Scheduler API: jobs CRUD, executions, run-now, retry."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.models import JobExecution, ScheduledJob, User
from app.schemas.schemas import JobCreate, JobExecutionOut, JobOut, JobUpdate
from app.scheduler import tasks as job_tasks
from app.scheduler.scheduler import schedule_job, unschedule_job
from app.services import account_service
from app.services.notify_service import log_activity

router = APIRouter(prefix="/jobs", tags=["scheduler"])

VALID_JOB_TYPES = {"once", "interval", "daily", "weekly", "sync", "automation"}


def _get_job(db: Session, user: User, job_id: str) -> ScheduledJob:
    job = db.get(ScheduledJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _out(job: ScheduledJob) -> JobOut:
    return JobOut(
        id=job.id, name=job.name, job_type=job.job_type, account_id=job.account_id,
        schedule_config=job.schedule_config, status=job.status,
        next_run_at=job.next_run_at, last_run_at=job.last_run_at,
        last_error=job.last_error, retry_count=job.retry_count,
        max_retries=job.max_retries,
    )


@router.get("", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(ScheduledJob).where(ScheduledJob.user_id == user.id)
                      .order_by(ScheduledJob.created_at)).all()
    return [_out(j) for j in rows]


@router.post("", response_model=JobOut, status_code=201)
def create_job(body: JobCreate, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if body.job_type not in VALID_JOB_TYPES:
        raise HTTPException(status_code=400, detail="Invalid job_type")
    if body.account_id and not account_service._get_account(db, user.id, body.account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    if body.job_type == "sync" and not (body.account_id or (body.schedule_config or {}).get("account_id")):
        raise HTTPException(status_code=400, detail="sync jobs need an account_id")
    job = ScheduledJob(
        user_id=user.id, account_id=body.account_id, name=body.name,
        job_type=body.job_type, schedule_config=body.schedule_config,
        payload=body.payload, max_retries=body.max_retries, status="active",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        schedule_job(job)
    except ValueError as exc:
        db.delete(job)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc))
    log_activity(db, "scheduler.job_created", user_id=user.id, detail={"name": body.name})
    return _out(job)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    return _out(_get_job(db, user, job_id))


@router.patch("/{job_id}", response_model=JobOut)
def update_job(job_id: str, body: JobUpdate, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    job = _get_job(db, user, job_id)
    if body.name is not None:
        job.name = body.name
    if body.status is not None:
        job.status = body.status
    if body.schedule_config is not None:
        job.schedule_config = body.schedule_config
    if body.max_retries is not None:
        job.max_retries = body.max_retries
    db.commit()
    try:
        schedule_job(job)  # re-registers or unschedules based on status
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.refresh(job)
    return _out(job)


@router.delete("/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    job = _get_job(db, user, job_id)
    unschedule_job(job.id)
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.get("/{job_id}/executions", response_model=list[JobExecutionOut])
def job_executions(job_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user),
                   limit: int = Query(default=50, ge=1, le=200)):
    job = _get_job(db, user, job_id)
    rows = db.scalars(select(JobExecution).where(JobExecution.job_id == job.id)
                      .order_by(JobExecution.created_at.desc()).limit(limit)).all()
    return rows


@router.post("/{job_id}/run-now")
def run_now(job_id: str, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    job = _get_job(db, user, job_id)
    log_activity(db, "scheduler.job_run_now", user_id=user.id,
                 detail={"job_id": job.id})
    # Synchronous run in dev; production deployments may queue this instead.
    return job_tasks.run_scheduled_job(job.id)


@router.post("/executions/{execution_id}/retry")
def retry_execution(execution_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    execution = db.get(JobExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    _get_job(db, user, execution.job_id)  # ownership check
    if execution.status not in ("failed", "dead"):
        raise HTTPException(status_code=400, detail="Only failed/dead executions can be retried")
    return job_tasks.retry_execution(execution.id)
