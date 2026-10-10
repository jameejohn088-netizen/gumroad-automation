# Gumroad Automation — Deployment & Operations Guide

## Architecture

| Component | Technology | Location |
|---|---|---|
| Backend API | FastAPI (Python 3.12) | `backend/` |
| Database | SQLite (dev) / PostgreSQL-ready via `DATABASE_URL` | `backend/gumroad_app.db` |
| Web dashboard | React 19 + Vite (served by the backend) | `web/dist/` |
| Android app | Kotlin (built by GitHub Actions CI) | `android/` |
| Scheduler | APScheduler (DB-persisted jobs) | in-backend |
| Public tunnel | Pinggy (free tier, URL rotates ~hourly) | `backend/watchdog.sh` |

The backend serves the web dashboard at `/` (same origin → `/api/v1`),
so the web app survives tunnel URL rotations without a rebuild.

## Quick start (this VM)

```bash
cd backend
cp .env.example .env        # then fill in SECRET_KEY, TOKEN_MASTER_KEY
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
bash watchdog.sh            # starts tunnel, writes PUBLIC_URL.txt
```

The watchdog is also on cron (`gumroad-backend-watchdog`, every 15 min) and
keeps the backend + tunnel alive, updating the gist on URL rotation.

## Environment variables

See `backend/.env.example`. Required:

- `SECRET_KEY` — JWT signing (generate with `secrets.token_urlsafe(48)`)
- `TOKEN_MASTER_KEY` — base64 32 bytes; AES-GCM encryption of Gumroad tokens
- `DATABASE_URL` — defaults to local SQLite

Optional (tunnel auto-update): `GITHUB_PAT`, `GIST_ID`, `GIST_RAW_URL` —
set via the `/github-setup` page, never by hand in chat.

## Database

- Migrations: `backend/alembic/versions/`. Apply: `.venv/bin/alembic upgrade head`
- 25 tables: users, gumroad_accounts (+ encrypted credentials), products,
  sales, customers, subscribers, licenses, automation rules, jobs, sync history,
  notifications, activity/error logs.
- **Backup:** `bash backend/backup.sh` (online SQLite backup, keeps 7 newest).
  Restore: stop backend, `cp <backup> backend/gumroad_app.db`.
- Account-scoped unique constraints prevent duplicate products/sales.

## Gumroad integration

- OAuth 2.0 + manual token, per-account AES-GCM encrypted storage.
- Sync: products, sales (paginated, incremental), subscribers.
- Write actions (refund / mark-shipped / resend-receipt) are dry-run gated.
- **Limitation:** Gumroad API v2 does not expose product create/edit —
  create products at gumroad.com, then Sync in the app.

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests/   # 76 tests
```

## Diagnostics

Web: **Diagnostics** page, or `GET /api/v1/diagnostics` (auth required).
Checks: DB, migrations, env config, Gumroad auth, sync, scheduler, error log.

## Troubleshooting

| Symptom | Action |
|---|---|
| App "no connection" | Tunnel URL rotated — new APK auto-updates via gist; old APK: copy URL from `<url>/app-setup` |
| Sync fails 401 | Account → Reconnect (token expired) |
| 429 rate limit | Built-in per-account limiter backs off; wait, then Sync |
| Web 404 on refresh | Backend serves SPA fallback — restart backend if stale |
