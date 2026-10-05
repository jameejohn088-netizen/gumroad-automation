# Known Limitations (honest list)

## Gumroad API limits (from official docs — see GUMROAD_API_CAPABILITIES.md)

- **No product create/update/delete** in the API. The UI never offers it.
- **No subscription cancellation** endpoint. Shown as "Not supported by Gumroad API".
- **No emailing customers through Gumroad**. Outbound email in automations uses the
  user's own SMTP, never Gumroad.
- **No customers endpoint** — customers are derived from sales (dedupe by email).
- **No memberships endpoint** — derived from subscription products + subscribers.
- **Workflows**: read-only via API.
- **Rate limits are not documented** — we self-limit + honor 429/Retry-After.
- Webhooks (`resource_subscriptions`) need a **public HTTPS URL**; local/dev uses polling.
  Polling is never presented as a webhook.

## This build

- **No live Gumroad test yet** — sync/actions verified against fixtures only. Needs a real
  token (entered in app UI or `.env`, never in chat) for the opt-in live test.
- **OAuth 2.0 authorization-code flow**: backend has start/callback endpoints, but the exact
  Gumroad authorize/token paths default to `gumroad.com/oauth/authorize` + `/oauth/token`
  (env-configurable) — confirm in your Gumroad app settings. Manual access-token mode is
  fully working and is the recommended path for personal use.
- **Android APK not compiled here** — this machine has no JDK/Android SDK. CI
  (`android` job) builds `app-debug.apk` and uploads it as an artifact. First CI build may
  surface minor Compose/Material3 API issues (flagged in code review).
- **PostgreSQL** schema is designed portable, but only SQLite was executed here.
- **Docker** files written, image not built here.
- **Web frontend tests** (component/E2E) not written yet; contract-tested manually via build.
- **Android background sync**: WorkManager minimum ~15 minutes; the OS may delay or kill it.
  True 24/7 automation needs a continuously running server (later phase — Docker-ready).
- FastAPI `on_event` deprecation warnings present (functional; migrate to lifespan later).
