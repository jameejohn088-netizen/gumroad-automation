"""Typed Gumroad API v2 client.

Endpoints used here are ONLY those verified in docs/GUMROAD_API_CAPABILITIES.md
against the official docs (https://gumroad.com/api). Nothing is invented.

Features:
- per-account rate limiter (token bucket)
- 429 + Retry-After handling, exponential backoff with jitter
- cursor pagination via page_key / next_page_key
- timeouts, typed errors, redacted logging (no tokens, masked emails)
"""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any, Iterator

import httpx

from app.core.security import mask_email
from app.gumroad.http import gumroad_http_client
from app.gumroad.exceptions import (
    GumroadAuthError,
    GumroadClientError,
    GumroadError,
    GumroadNotFoundError,
    GumroadRateLimitError,
    GumroadServerError,
)

log = logging.getLogger("gumroad")

BASE_URL = "https://api.gumroad.com/v2"
TIMEOUT = 30.0
MAX_ATTEMPTS = 5

# Rate limits are NOT documented by Gumroad; we enforce our own conservative
# per-account bucket and always honor 429 + Retry-After.
DEFAULT_MIN_INTERVAL = 2.0  # seconds between requests per account


def _redact_params(params: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (params or {}).items():
        if k == "access_token":
            out[k] = "***REDACTED***"
        elif k == "email" and isinstance(v, str):
            out[k] = mask_email(v)
        else:
            out[k] = v
    return out


class _RateLimiter:
    """Per-account minimum-interval limiter (thread-safe)."""

    def __init__(self, min_interval: float = DEFAULT_MIN_INTERVAL):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next_allowed - now
            if delay > 0:
                time.sleep(delay)
                now = time.monotonic()
            self._next_allowed = max(now, self._next_allowed) + self.min_interval


# One limiter per account id (module-level registry).
_limiters: dict[str, _RateLimiter] = {}
_limiters_lock = threading.Lock()


def _limiter_for(account_id: str, min_interval: float) -> _RateLimiter:
    with _limiters_lock:
        lim = _limiters.get(account_id)
        if lim is None:
            lim = _RateLimiter(min_interval)
            _limiters[account_id] = lim
        return lim


class GumroadClient:
    """Synchronous typed client. Create one per account; it is thread-safe."""

    def __init__(
        self,
        access_token: str,
        account_id: str = "default",
        transport: httpx.BaseTransport | None = None,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        timeout: float = TIMEOUT,
    ):
        self._token = access_token
        self._account_id = account_id
        self._limiter = _limiter_for(account_id, min_interval)
        self._http = gumroad_http_client(timeout=timeout, transport=transport,
                                          base_url=BASE_URL)

    # ------------------------------------------------------------ core ----

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a request with retries. Raises typed GumroadError subclasses."""
        params = dict(params or {})
        params["access_token"] = self._token
        data = dict(data or {})
        if method.upper() in ("POST", "PUT", "DELETE"):
            data.setdefault("access_token", self._token)

        last_exc: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._limiter.wait()
            try:
                resp = self._http.request(method, path, params=params, data=data or None)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                log.warning(
                    "gumroad transport error method=%s path=%s attempt=%d err=%s",
                    method, path, attempt, type(exc).__name__,
                )
            else:
                if resp.status_code == 429:
                    retry_after = self._parse_retry_after(resp)
                    log.warning(
                        "gumroad 429 method=%s path=%s attempt=%d retry_after=%s",
                        method, path, attempt, retry_after,
                    )
                    if attempt == MAX_ATTEMPTS:
                        raise GumroadRateLimitError("rate limited by Gumroad", 429)
                    time.sleep(retry_after + random.uniform(0, 1))
                    continue
                if resp.status_code == 401:
                    log.warning("gumroad 401 method=%s path=%s", method, path)
                    raise GumroadAuthError("Gumroad rejected the access token (401)", 401)
                if resp.status_code == 404:
                    raise GumroadNotFoundError(self._err_message(resp, path), 404)
                if 500 <= resp.status_code <= 599:
                    log.warning(
                        "gumroad %d method=%s path=%s attempt=%d",
                        resp.status_code, method, path, attempt,
                    )
                    last_exc = GumroadServerError(self._err_message(resp, path), resp.status_code)
                    if attempt < MAX_ATTEMPTS:
                        time.sleep(self._backoff(attempt))
                        continue
                    raise last_exc
                if resp.status_code >= 400:
                    raise GumroadClientError(self._err_message(resp, path), resp.status_code)
                try:
                    body = resp.json()
                except Exception as exc:
                    raise GumroadError(f"invalid JSON from Gumroad for {path}") from exc
                log.info(
                    "gumroad ok method=%s path=%s status=%d params=%s",
                    method, path, resp.status_code, _redact_params({k: v for k, v in params.items() if k != "access_token"}),
                )
                return body
            if attempt < MAX_ATTEMPTS:
                time.sleep(self._backoff(attempt))
        raise GumroadError(f"request failed after {MAX_ATTEMPTS} attempts: {last_exc}")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(30.0, (2.0 ** attempt)) + random.uniform(0, 1.0)

    @staticmethod
    def _parse_retry_after(resp: httpx.Response) -> float:
        try:
            return max(1.0, float(resp.headers.get("Retry-After", "5")))
        except ValueError:
            return 5.0

    @staticmethod
    def _err_message(resp: httpx.Response, path: str) -> str:
        try:
            body = resp.json()
            msg = body.get("message")
            if msg:
                return str(msg)
        except Exception:
            pass
        return f"Gumroad request failed: {path} (HTTP {resp.status_code})"

    # ------------------------------------------------------------ pages ---

    def paginate(
        self, path: str, params: dict[str, Any] | None = None, item_key: str = "items"
    ) -> Iterator[dict[str, Any]]:
        """Yield items across cursor pages (page_key / next_page_key)."""
        params = dict(params or {})
        while True:
            body = self._request("GET", path, params=params)
            items = body.get(item_key, []) or []
            for item in items:
                yield item
            next_key = body.get("next_page_key")
            if not next_key:
                break
            params["page_key"] = next_key

    # ------------------------------------------------------------ user ----

    def get_user(self) -> dict[str, Any]:
        """GET /v2/user — validates the token. Scope: account/view_profile."""
        return self._request("GET", "/user")

    # ------------------------------------------------------------ products

    def list_products(self, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        """GET /v2/products — cursor paginated."""
        yield from self.paginate("/products", params, item_key="products")

    def get_product(self, product_id: str) -> dict[str, Any]:
        """GET /v2/products/:id — full product incl. variants and files."""
        body = self._request("GET", f"/products/{product_id}")
        return body.get("product", {})

    # ------------------------------------------------------------ variants
    # Docs: POST /v2/products/:product_id/variant_categories/:category_id/variants
    #       PUT/DELETE .../variants/:id   (scope: edit_products)

    def create_variant(self, product_id: str, category_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/products/{product_id}/variant_categories/{category_id}/variants", data=data)

    def update_variant(self, product_id: str, category_id: str, variant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/products/{product_id}/variant_categories/{category_id}/variants/{variant_id}", data=data)

    def delete_variant(self, product_id: str, category_id: str, variant_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/products/{product_id}/variant_categories/{category_id}/variants/{variant_id}")

    # ------------------------------------------------------------ offer codes
    # Docs: GET/POST /v2/products/:product_id/offer_codes
    #       GET/PUT/DELETE /v2/products/:product_id/offer_codes/:id  (scope: edit_products)

    def list_offer_codes(self, product_id: str) -> Iterator[dict[str, Any]]:
        yield from self.paginate(f"/products/{product_id}/offer_codes", item_key="offer_codes")

    def create_offer_code(self, product_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/products/{product_id}/offer_codes", data=data)

    def update_offer_code(self, product_id: str, offer_code_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/products/{product_id}/offer_codes/{offer_code_id}", data=data)

    def delete_offer_code(self, product_id: str, offer_code_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/products/{product_id}/offer_codes/{offer_code_id}")

    # ------------------------------------------------------------ sales ---
    # Docs: GET /v2/sales (filters: before, after, email; cursor page_key)
    #       GET /v2/sales/:id   (scope: view_sales)

    def list_sales(
        self,
        after: str | None = None,
        before: str | None = None,
        email: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {}
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if email:
            params["email"] = email
        yield from self.paginate("/sales", params, item_key="sales")

    def get_sale(self, sale_id: str) -> dict[str, Any]:
        body = self._request("GET", f"/sales/{sale_id}")
        return body.get("sale", {})

    # Docs: POST /v2/sales/:id/refund  (scope: edit_sales)
    def refund_sale(self, sale_id: str) -> dict[str, Any]:
        return self._request("POST", f"/sales/{sale_id}/refund")

    # Docs: POST /v2/sales/:id/mark_as_shipped  (scope: mark_sales_as_shipped)
    def mark_as_shipped(self, sale_id: str, tracking_url: str | None = None) -> dict[str, Any]:
        data = {"tracking_url": tracking_url} if tracking_url else {}
        return self._request("POST", f"/sales/{sale_id}/mark_as_shipped", data=data)

    # Docs: POST /v2/sales/:id/revoke_access and /undo_revoke_access  (scope: edit_sales)
    def revoke_access(self, sale_id: str) -> dict[str, Any]:
        return self._request("POST", f"/sales/{sale_id}/revoke_access")

    def undo_revoke_access(self, sale_id: str) -> dict[str, Any]:
        return self._request("POST", f"/sales/{sale_id}/undo_revoke_access")

    # Docs: POST /v2/sales/:id/resend_receipt  (scope: edit_sales)
    def resend_receipt(self, sale_id: str) -> dict[str, Any]:
        return self._request("POST", f"/sales/{sale_id}/resend_receipt")

    # ------------------------------------------------------------ subscribers
    # Docs: GET /v2/subscribers  (scope: account)

    def list_subscribers(self) -> Iterator[dict[str, Any]]:
        yield from self.paginate("/subscribers", item_key="subscribers")

    # ------------------------------------------------------------ licenses
    # Docs: POST /v2/licenses/verify (no OAuth app needed), /enable, /disable,
    #       /decrement_uses_count, /rotate  (scope: account except verify)

    def verify_license(self, product_permalink: str, license_key: str, increment_uses_count: bool = True) -> dict[str, Any]:
        return self._request("POST", "/licenses/verify", data={
            "product_permalink": product_permalink,
            "license_key": license_key,
            "increment_uses_count": str(increment_uses_count).lower(),
        })

    def enable_license(self, product_id: str, license_key: str) -> dict[str, Any]:
        return self._request("POST", "/licenses/enable", data={
            "product_id": product_id, "license_key": license_key,
        })

    def disable_license(self, product_id: str, license_key: str) -> dict[str, Any]:
        return self._request("POST", "/licenses/disable", data={
            "product_id": product_id, "license_key": license_key,
        })

    def decrement_license_uses(self, product_id: str, license_key: str) -> dict[str, Any]:
        return self._request("POST", "/licenses/decrement_uses_count", data={
            "product_id": product_id, "license_key": license_key,
        })

    def rotate_license(self, product_id: str, license_key: str) -> dict[str, Any]:
        return self._request("POST", "/licenses/rotate", data={
            "product_id": product_id, "license_key": license_key,
        })

    # ------------------------------------------------------------ webhooks
    # Docs: GET/POST/DELETE /v2/resource_subscriptions
    # (subscribe to sales requires view_sales scope; needs public HTTPS URL)

    def list_resource_subscriptions(self) -> Iterator[dict[str, Any]]:
        yield from self.paginate("/resource_subscriptions", item_key="resource_subscriptions")

    def create_resource_subscription(self, resource_name: str, webhook_url: str) -> dict[str, Any]:
        return self._request("POST", "/resource_subscriptions", data={
            "resource_name": resource_name, "webhook_url": webhook_url,
        })

    def delete_resource_subscription(self, subscription_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/resource_subscriptions/{subscription_id}")

    def close(self) -> None:
        self._http.close()
