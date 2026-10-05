# Test report — 2026-10-05

## Automated (run here, verified by the lead, not just reported)

| Suite | Command | Result |
|---|---|---|
| Backend pytest | `.venv/bin/python -m pytest -q` (run twice) | **57/57 passed**, exit 0 |
| Alembic | `alembic upgrade head` on fresh DB | clean, 26 tables |
| Backend boot | `uvicorn app.main:app` + curl | `/health` → `{"status":"ok","version":"1.0.0"}`; `POST /api/v1/auth/signup` → 201 with user object |
| Web build | `npm run build` (`tsc -b && vite build`) | **zero TS errors**, `dist/` emitted |
| Web dev server | `npm run dev` smoke | HTTP 200, HTML served |

Coverage includes: signup/login/logout/refresh, forgot/reset password, token rotation,
add/remove/disconnect/reconnect account, **>10 accounts**, cross-user account isolation,
Gumroad client pagination / 429+Retry-After / 401 / log redaction, sync idempotency,
scheduler once/recurring/retry/dead-letter/restart-recovery, automation dry-run /
idempotency / rate-cap. Gumroad HTTP only via clearly-labeled test fixtures.

## Not yet run (manual checklist — open)

- [ ] Install the debug APK on a **real Android device**, full flow with a **real Gumroad account**.
- [ ] Open the website in a browser against the running backend; multi-account switching.
- [ ] Opt-in **live** Gumroad test with a real token from env (fixtures only so far).
- [ ] Android `assembleDebug` in CI (no JDK/SDK on this machine).
- [ ] Docker image build.
- [ ] PostgreSQL run (schema designed portable; SQLite executed).

## Honest status

Working end-to-end **locally**: backend API (auth, accounts, sync engine, automations,
scheduler, export) + website build + Android source. The real-Gumroad loop and the APK
binary are the two pieces still awaiting their first real run — both are wired for it
(CI builds the APK; connect-manual validates a token against `GET /v2/user`).
