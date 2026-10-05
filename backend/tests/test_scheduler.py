"""Scheduler tests: success, retry, dead-letter, manual retry, restart recovery."""
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models.models import JobExecution, ScheduledJob
from app.scheduler import tasks as job_tasks


def _make_job(db, user, **kw):
    job = ScheduledJob(user_id=user.id, name="Test Job", job_type="once",
                       schedule_config={}, payload={"kind": "explode"},
                       status="active", max_retries=1, **kw)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_job_run_now_success_via_api(client, auth_headers, account_factory,
                                     mock_gumroad, db):
    headers, user = auth_headers()
    acct = account_factory(user, "Sched Store")
    r = client.post("/api/v1/jobs", headers=headers, json={
        "name": "sync job", "job_type": "sync", "account_id": acct.id,
        "schedule_config": {"account_id": acct.id}, "payload": {}})
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    r = client.post(f"/api/v1/jobs/{job_id}/run-now", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "success"

    r = client.get(f"/api/v1/jobs/{job_id}/executions", headers=headers)
    assert r.status_code == 200
    assert r.json()[0]["status"] == "success"


def test_job_retry_then_dead_letter(db, user_factory):
    user, _ = user_factory()
    job = _make_job(db, user)  # payload kind=explode -> ValueError

    out = job_tasks.run_scheduled_job(job.id)
    assert out["status"] == "failed"
    db.refresh(job)
    assert job.retry_count == 1
    assert job.next_run_at is not None  # retry scheduled
    assert job.status == "active"

    out = job_tasks.run_scheduled_job(job.id, _attempt=2)
    assert out["status"] == "failed"
    db.refresh(job)
    assert job.status == "dead"  # max_retries=1 exceeded -> dead-letter
    dead_exec = db.scalars(select(JobExecution).where(
        JobExecution.job_id == job.id).order_by(JobExecution.created_at.desc())).first()
    assert dead_exec.status == "dead"


def test_manual_retry_of_dead_execution(db, user_factory):
    user, _ = user_factory()
    job = _make_job(db, user)
    job_tasks.run_scheduled_job(job.id)
    job_tasks.run_scheduled_job(job.id, _attempt=2)
    db.refresh(job)
    assert job.status == "dead"
    dead_exec = db.scalars(select(JobExecution).where(
        JobExecution.job_id == job.id, JobExecution.status == "dead")).first()

    out = job_tasks.retry_execution(dead_exec.id)
    assert out["status"] == "failed"  # still explodes, but it RAN again
    db.refresh(job)
    assert job.status == "dead"
    n = db.scalar(select(func.count(JobExecution.id)).where(
        JobExecution.job_id == job.id))
    assert n == 3


def test_job_crud_and_pause_via_api(client, auth_headers):
    headers, _ = auth_headers()
    r = client.post("/api/v1/jobs", headers=headers, json={
        "name": "daily", "job_type": "daily",
        "schedule_config": {"hour": 9, "minute": 0}, "payload": {"kind": "daily_summary"}})
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    r = client.get("/api/v1/jobs", headers=headers)
    assert len(r.json()) == 1

    r = client.patch(f"/api/v1/jobs/{job_id}", headers=headers,
                     json={"status": "paused"})
    assert r.json()["status"] == "paused"

    r = client.delete(f"/api/v1/jobs/{job_id}", headers=headers)
    assert r.status_code == 200
    r = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert r.status_code == 404


def test_scheduler_restart_recovery_runs_missed_job_once(db, user_factory, tmp_path):
    """A job persisted in the DB job store whose run time passed while the
    scheduler was down fires exactly once when a NEW scheduler instance
    starts (missed-run policy: misfire_grace_time + coalesce).

    NOTE (APScheduler mechanics, verified in source): due-ness is decided by
    the jobstore's next_run_time COLUMN, but run times come from the pickled
    job's next_run_time attribute — so both must be backdated, which is what
    JobStore.update_job() does atomically.
    """
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.schedulers.background import BackgroundScheduler

    user, _ = user_factory()
    job = ScheduledJob(user_id=user.id, name="recovery", job_type="once",
                       schedule_config={}, payload={"kind": "explode"},
                       status="active", max_retries=0)
    db.add(job)
    db.commit()
    db.refresh(job)

    store_path = str(tmp_path / "jobs.db")
    store_url = "sqlite:" + "///" + store_path

    # Instance 1: persist a job 5 minutes in the future, then shut down
    # (simulates the process going away before the run).
    sched1 = BackgroundScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=store_url)}, timezone="UTC")
    sched1.start()
    sched1.add_job("app.scheduler.tasks:run_scheduled_job",
                   trigger="date",
                   run_date=datetime.now(timezone.utc) + timedelta(minutes=5),
                   args=[job.id], id=f"job:{job.id}",
                   misfire_grace_time=3600, coalesce=True,
                   replace_existing=True)
    time.sleep(1)  # let the jobstore persist
    sched1.shutdown(wait=True)

    # Simulate downtime passing: backdate the persisted job's next_run_time
    # (column + pickled state) via the jobstore's own API.
    store = SQLAlchemyJobStore(url=store_url)
    stored = store.lookup_job(f"job:{job.id}")
    assert stored is not None
    stored.next_run_time = datetime.now(timezone.utc) - timedelta(seconds=30)
    store.update_job(stored)

    # Instance 2: fresh start -> the missed job fires exactly once.
    sched2 = BackgroundScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=store_url)}, timezone="UTC")
    sched2.start()
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            db.expire_all()
            n = db.scalar(select(func.count(JobExecution.id)).where(
                JobExecution.job_id == job.id))
            if n and n >= 1:
                break
            time.sleep(0.3)
        db.expire_all()
        n = db.scalar(select(func.count(JobExecution.id)).where(
            JobExecution.job_id == job.id))
        assert n == 1, "missed job must run exactly once on resume"
    finally:
        sched2.shutdown(wait=False)
