# Gumroad Automation — Web App

React + TypeScript + Vite + Tailwind CSS + react-router-dom front end for the
Gumroad Automation backend. It talks **only** to the backend API — no Gumroad
token ever reaches the browser.

## Prerequisites

- Node.js 20+
- The backend running (default `http://localhost:8000`, API at `/api/v1`)

## Run the dev server

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173. Sign up, log in, then connect a Gumroad account on
the **Gumroad Accounts** page by pasting a Gumroad access token (generated on
your Gumroad OAuth application page). The token goes straight to the backend
over HTTPS and is stored encrypted server-side.

## Point at a different backend

```bash
VITE_API_URL=https://your-backend.example.com/api/v1 npm run dev
```

or create a `.env` file in `web/`:

```
VITE_API_URL=http://localhost:8000/api/v1
```

## Production build

```bash
npm run build   # type-checks (tsc) and emits dist/
npm run preview # serve the production build locally
```

## Pages

Login, Signup, Forgot password, Reset password, Verify email, Dashboard,
Gumroad Accounts, Products, Sales (refund / mark-as-shipped with dry-run,
CSV export), Customers, Subscribers, Licenses, Memberships, Automations
(rule builder), Scheduler (jobs + execution history + retry), Notifications,
Logs (activity + errors), Settings/Profile.

Global: account selector in the header (All Accounts + individual), search /
filters / pagination on list pages, light/dark mode toggle, responsive layout,
accessible labeled forms, and loading / empty / error states everywhere.
