# Gumroad API Capabilities (verified against official docs)

**Source:** Official Gumroad API documentation at https://gumroad.com/api (also https://app.gumroad.com/api),
read directly on 2026-10-05. Cross-checked with the official CLI repo github.com/antiwork/gumroad-cli.
Do not rely on old tutorials — this document reflects the current official docs.

## Base

- Base URL: `https://api.gumroad.com/v2/`
- Style: REST, JSON for every request including errors.
- Current version: v2.

## Authentication

- **OAuth 2.0.** Register an OAuth application (Gumroad help article / app settings page);
  you receive a unique **application id** and **application secret**.
- **Manual access token (personal use):** on the application page, click **"Generate access token"**
  and use that token with the API. The app's own token can also be used directly.
- The token is sent as the `access_token` parameter (docs' cURL examples use `-d "access_token=..."`).
- The **Verify License** endpoint does **not** require an OAuth application.

> Our system supports BOTH modes: full OAuth 2.0 authorization-code flow AND manual
> access-token mode (validated by calling the user endpoint). We never ask for or store
> Gumroad passwords.

## Scopes (exact wording from official docs)

- `account` — full access to most API endpoints. Endpoints with a narrower security boundary
  (e.g. media) refuse an account-only token and require the specific scope noted on the endpoint.
- `view_profile` — read-only access to the user's public information and products.
- `edit_profile` — write access to the user's profile name and bio.
- `edit_products` — read/write access to the user's products and their variants, offer codes,
  custom fields, and files.
- `edit_emails` — read/write access to the user's audience emails and read access to the
  user's workflows.
- `view_sales` — read access to the user's products' sales information, including sales counts.
  Also required in order to subscribe to the user's sales.
- `view_payouts` — read access to the user's payouts information.
- `view_tax_data` — read access to tax forms (1099-K, 1099-MISC) and annual earnings summary.
- `mark_sales_as_shipped` — write access to mark the user's products' sales as shipped.
- `edit_sales` — write access to **refund** the user's products' sales, **revoke or restore
  buyer access**, and **resend purchase receipts** to customers.

## Endpoints actually available (verified in official docs)

| Endpoint | Method | Scope | Notes |
|---|---|---|---|
| `/v2/user` | GET | account/view_profile | Validate token / public user info |
| `/v2/products` | GET | account/view_profile (+view_sales for sales_count) | Cursor pagination via `page_key` / `next_page_key` |
| `/v2/products/:id` | GET | account/view_profile | Full product incl. variants, files |
| Variants | POST/PUT/DELETE | `edit_products` | Add, edit, delete variants |
| Offer codes | POST/PUT/DELETE/GET | `edit_products` | Add, edit, delete offer codes |
| Custom fields | POST/PUT/DELETE | `edit_products` | Add, edit, delete custom fields |
| `/v2/sales` | GET | `view_sales` | List sales; cursor pagination |
| `/v2/sales/:id/refund` | POST | `edit_sales` | Refund a sale |
| `/v2/sales/:id/mark_as_shipped` | POST | `mark_sales_as_shipped` | Mark sale as shipped |
| Resend receipt | POST | `edit_sales` | Resend purchase receipt to customer |
| Revoke/restore buyer access | POST | `edit_sales` | Revoke or restore access |
| `/v2/subscribers` | GET | account | Subscriber details |
| `/v2/licenses/verify` | POST | none (no OAuth app needed) | Verify a license key |
| `/v2/licenses/enable` | POST | account | Enable a license |
| `/v2/licenses/disable` | POST | account | Disable a license |
| `/v2/licenses/decrement_uses_count` | POST | account | Decrement uses count |
| `/v2/licenses/rotate` | POST | account | Rotate a license key |
| `/v2/resource_subscriptions` | GET/POST/DELETE | account (+view_sales to subscribe to sales) | Webhook subscriptions: create, list, delete |
| Payouts | GET | `view_payouts` | Read-only payouts info |

## Pagination and filters

- Cursor-based: responses include `next_page_key`; pass it as `page_key` for the next page.
  (Also `next_page_url` is provided.)
- Sales support filters (verified pattern: query params on list endpoints); exact filter set
  taken from the official docs at implementation time.

## Webhooks (`resource_subscriptions`)

- Real webhook mechanism: create/list/delete subscriptions via `/v2/resource_subscriptions`.
- Subscribe to **sales** events requires the `view_sales` scope.
- Event dedupe is our responsibility (store event ids).
- Webhooks need a **public HTTPS URL**, so they are an optional upgrade; **polling is the
  primary mechanism** and is never presented as a webhook.

## Rate limits

**Not documented** in the official docs. Our client implements its own per-account rate
limiter, honors `429` + `Retry-After`, and uses exponential backoff with jitter regardless.

## Feature classification (per Phase-0 verification rules)

**SUPPORTED** (documented endpoint exists):
products list/get, variants CRUD, offer codes CRUD, custom fields CRUD, sales list,
refund sale, resend receipt, revoke/restore buyer access, mark as shipped, subscribers list,
licenses verify/enable/disable/decrement/rotate, resource_subscriptions (webhooks),
user info, payouts read.

**PARTIALLY SUPPORTED** (requires alternative approach):
- **Customers** — no dedicated endpoint; derived from sales, deduplicated by email.
- **Memberships** — derived from subscription products + subscribers.
- **Workflows** — `edit_emails` gives read access to workflows only (no write documented).

**NOT SUPPORTED** (no documented endpoint — do not offer, do not fake):
- Product creation / update / enable / disable / delete (docs only document offer-code,
  variant, and custom-field mutations — not product lifecycle).
- Subscription cancellation.
- Emailing customers *through Gumroad* (no such endpoint).
- Anything else not listed in the table above.

## Restrictions relevant to automation

- Token is per-account; multi-account = one token per Gumroad account, all encrypted at rest.
- `401 Unauthorized` means the token is invalid → mark account "needs reconnect".
- Webhooks require public HTTPS; local/dev setups must use polling.
- `account` scope is broad but some endpoints refuse it and demand their narrow scope —
  request least-privilege scopes per feature.
