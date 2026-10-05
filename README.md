# Gumroad Automation

Real, working, production-quality Gumroad automation: **FastAPI backend** + **React website** +
**Android app**, all sharing one backend and one real Gumroad API v2 integration.

> Status: under active construction. See `docs/` for architecture, setup, capabilities,
> known limitations, and the test report.

## Structure

- `backend/` — FastAPI API (Python 3.12), SQLite by default, Alembic migrations, pytest.
- `web/` — React + TypeScript + Vite + Tailwind. Talks only to the backend API.
- `android/` — Kotlin + Jetpack Compose (Material 3) app. Debug APK built by CI.
- `docs/` — `GUMROAD_API_CAPABILITIES.md`, `ARCHITECTURE.md`, `SETUP.md`,
  `KNOWN_LIMITATIONS.md`, `TEST_REPORT.md`.
- `.github/workflows/` — CI: backend tests, web build, debug APK build + artifact upload.

## Quick start

See `docs/SETUP.md`. Never paste secrets into chat — put them in `backend/.env` or the app UI.
