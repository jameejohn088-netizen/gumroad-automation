# Architecture

## Overview

Three clients, one backend, one real Gumroad integration:

```
┌──────────────┐      ┌──────────────┐
│  Web (React) │      │ Android app  │
│  Vite + TS   │      │ Kotlin/      │
│  + Tailwind  │      │ Compose      │
└──────┬───────┘      └──────┬───────┘
       │  HTTPS / JSON       │  HTTPS / JSON
       │  /api/v1            │  /api/v1
       └──────────┬──────────┘
                  ▼
        ┌──────────────────┐
        │  Backend (FastAPI)│
        │  Python 3.12      │
        │  SQLite (dev) /   │
        │  PostgreSQL (prod)│
        └────────┬─────────┘
                 │  OAuth 2.0 / access_token
                 │  https://api.gumroad.com/v2
                 ▼
        ┌──────────────────┐
        │  Gumroad API v2   │
        └──────────────────┘
```

**The Gumroad token never reaches the browser or the Android WebView.** Only the backend
talks to Gumroad. Web and Android authenticate to the backend with short-lived access
tokens + rotating refresh tokens.

## Backend layers

- `app/api/` — FastAPI routers under `/api/v1` (auth, accounts, dashboard, data, automation, jobs, notifications, logs, export, webhooks).
- `app/core/` — config (env-only), SQLAlchemy engine/session, argon2id + JWT auth, rate limiter + lockout, mailer (console/file/SMTP).
- `app/models/` — 26 SQLAlchemy entities. UUID PKs, `created_at`/`updated_at`, FK cascades,
  `UNIQUE(account_id, gumroad_id)`, indexes on `(account_id, created_at)` / `(status, next_run_at)`.
- `app/security/` — AES-GCM token encryption, master key from env, `key_version` for rotation.
- `app/gumroad/` — typed httpx client: per-account rate limiter, 429 + Retry-After, exponential
  backoff with jitter, cursor pagination, 401 → `needs_reconnect`, redacted logging.
- `app/services/` — auth, account lifecycle, sync (idempotent upserts, `sync_history`).
- `app/automation/` — TRIGGER → CONDITION → ACTION → JOB → EXECUTION → RESULT → LOG.
  Idempotency keys, per-rule rate caps, dry-run default.
- `app/scheduler/` — APScheduler + SQLAlchemy job store: jobs survive restarts, retry with
  backoff, dead-letter + manual re-run, run-once-on-resume missed-run policy.

## Data isolation

Every synced row carries `account_id`; every query is scoped by it. "All Accounts" is a
union of the logged-in user's own accounts only. Tests prove cross-account reads are impossible.

## Web

React 18/19 + TypeScript + Vite + Tailwind. `api/client.ts` handles Bearer auth + silent
refresh. All pages render loading/empty/error states. Dark/light mode, responsive layout,
account selector in the header.

## Android

Kotlin + Compose Material 3, MVVM + Hilt, Retrofit/OkHttp (+ Authenticator refresh),
Room offline read cache, DataStore + EncryptedSharedPreferences, WorkManager periodic sync
(≥15 min, OS may delay — disclosed in UI), local notifications.

## CI

`.github/workflows/ci.yml`: gitleaks secret scan → backend pytest → web `npm run build`
(+ `dist/` artifact) → Android `assembleDebug` (+ APK artifact download).
