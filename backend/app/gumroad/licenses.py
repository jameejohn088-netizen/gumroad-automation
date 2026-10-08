"""Buyer license verification WITHOUT any OAuth token.

Per the official Gumroad docs, POST /v2/licenses/verify does not require an
OAuth application, so the seller's access token is never involved in the buyer
flow. The license key is sent to Gumroad only over HTTPS and is never logged.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

from app.gumroad.exceptions import GumroadClientError, GumroadError, GumroadServerError
from app.gumroad.http import TIMEOUT, gumroad_http_client

log = logging.getLogger("gumroad.licenses")

VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"


def license_key_hash(license_key: str) -> str:
    """SHA-256 of the key: used for DB lookup, never reversible."""
    return hashlib.sha256(license_key.encode("utf-8")).hexdigest()


def _key_prefix(license_key: str) -> str:
    return license_key_hash(license_key)[:8]


def verify_license_noauth(
    product_permalink: str,
    license_key: str,
    increment_uses_count: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Verify a buyer's license key with Gumroad. No OAuth token needed.

    Raises GumroadClientError (invalid key / bad request), GumroadServerError
    (Gumroad 5xx), or GumroadError (transport / bad JSON). Callers must fail
    closed: any exception means "do NOT grant access".
    """
    prefix = _key_prefix(license_key)
    # Accept either a Gumroad product id or a permalink slug / full URL.
    data: dict[str, str] = {"license_key": license_key,
                            "increment_uses_count": str(bool(increment_uses_count)).lower()}
    candidate = product_permalink.strip()
    if "gumroad.com" in candidate or "/" in candidate:
        candidate = candidate.rstrip("/").rsplit("/", 1)[-1]
    if "=" in candidate or (len(candidate) > 30 and "-" in candidate and "/" not in product_permalink):
        data["product_id"] = candidate
    else:
        data["product_permalink"] = candidate

    try:
        with gumroad_http_client(timeout=TIMEOUT, transport=transport) as http:
            resp = http.post(VERIFY_URL, data=data)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        log.warning("license verify transport error key=%s err=%s", prefix, type(exc).__name__)
        raise GumroadError(f"could not reach Gumroad: {type(exc).__name__}") from exc

    if 500 <= resp.status_code <= 599:
        log.warning("license verify gumroad %d key=%s", resp.status_code, prefix)
        raise GumroadServerError("Gumroad server error", resp.status_code)
    try:
        body = resp.json()
    except Exception as exc:
        raise GumroadError("invalid JSON from Gumroad license verify") from exc
    if resp.status_code >= 400 and not body.get("success"):
        message = str(body.get("message") or "license verification failed")
        log.info("license verify rejected key=%s http=%d", prefix, resp.status_code)
        raise GumroadClientError(message, resp.status_code)
    log.info("license verify ok=%s key=%s", body.get("success"), prefix)
    return body


def purchase_is_good(purchase: dict[str, Any] | None) -> tuple[bool, str]:
    """Decide whether a verified purchase still grants access.

    Returns (ok, reason). Deny on refunded / chargebacked / lost disputes /
    ended subscriptions. A seller-disabled license fails verification itself
    (success=false), which is handled before this is called.
    """
    if not purchase:
        return False, "no_purchase"
    if purchase.get("refunded"):
        return False, "purchase_refunded"
    if purchase.get("chargebacked"):
        return False, "purchase_chargebacked"
    if purchase.get("disputed") and not purchase.get("dispute_won"):
        return False, "purchase_disputed"
    if purchase.get("subscription_ended_at"):
        return False, "subscription_ended"
    return True, "ok"
