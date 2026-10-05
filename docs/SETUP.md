# Setup

## 0. Get a Gumroad token (never paste it into chat)

**Option A — manual token (recommended for personal use):**
1. Log in to Gumroad → create an OAuth application (Gumroad help article "creating an API application").
2. On the application page click **Generate access token**.
3. Paste it later in the app UI (Gumroad Accounts → Add → Connect manual) or `backend/.env`.

**Option B — OAuth 2.0:** register the app, set `GUMROAD_CLIENT_ID` / `GUMROAD_CLIENT_SECRET` /
`GUMROAD_REDIRECT_URI` in `backend/.env`. Confirm the authorize/token paths in your Gumroad
app settings if the defaults don't match.

## 1. Backend (local, $0)

```bash
cd backend
cp ../.env.example .env        # then edit: SECRET_KEY, TOKEN_MASTER_KEY, mail settings
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# API docs: http://127.0.0.1:8000/docs
# Tests: .venv/bin/python -m pytest -q
```

PostgreSQL later: set `DATABASE_URL=postgresql+psycopg://...` and add `psycopg[binary]`
to requirements.

## 2. Website

```bash
cd web
npm install
npm run dev        # → http://localhost:5173 (talks to http://localhost:8000/api/v1)
# production: npm run build  → dist/
# point elsewhere: VITE_API_URL=https://your-backend/api/v1 npm run dev
```

## 3. Android app → backend connection

- Emulator: default base URL `http://10.0.2.2:8000/api/v1` works out of the box.
- Real device: Settings → Backend URL → your PC's LAN IP, e.g. `http://192.168.1.5:8000/api/v1`
  (backend must listen on `0.0.0.0`), or use `adb reverse tcp:8000 tcp:8000`.

## 4. Debug APK

Push to GitHub → Actions tab → **CI** workflow → download the `app-debug-apk` artifact.
Install on a real device (allow "install unknown apps" for your browser/files app).

## 5. Connect your first Gumroad account

Website or Android: **Accounts → Add account → Connect** → paste the token from step 0 →
**Sync**. Dashboard fills with real aggregates. Automations → create a rule (dry-run is default).

## 6. Webhooks (optional upgrade)

Needs a public HTTPS URL for the backend (free tunnel, e.g. Cloudflare Tunnel) →
register `resource_subscriptions` in the app. Until then, polling sync is the mechanism.

## 7. Later: cloud 24/7

`backend/Dockerfile` + `docker-compose.yml` are ready — deploy to any free container host
without rewriting the app.
