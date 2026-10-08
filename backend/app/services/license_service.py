"""Buyer license grants: verify with Gumroad, store minimal status, gate APK.

Security rules enforced here:
- The raw license key is never logged and never returned to callers.
- DB keeps only: permalink, key SHA-256, AES-GCM ciphertext of the key
  (needed for silent re-verification), status, purchase id, product name,
  masked buyer email, uses, timestamps.
- Any Gumroad/transport failure fails CLOSED (no access granted).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import mask_email
from app.gumroad.exceptions import GumroadClientError, GumroadError
from app.gumroad.licenses import license_key_hash, purchase_is_good, verify_license_noauth
from app.models.models import LicenseGrant
from app.security.encryption import decrypt_token, encrypt_token

log = logging.getLogger("license_service")


def _now():
    return datetime.now(timezone.utc)


def _upsert_grant(db: Session, product_permalink: str, license_key: str,
                  status: str, purchase: dict[str, Any] | None,
                  uses: int | None) -> LicenseGrant:
    key_hash = license_key_hash(license_key)
    grant = db.scalar(select(LicenseGrant).where(LicenseGrant.license_key_hash == key_hash))
    if grant is None:
        ciphertext, key_version = encrypt_token(license_key)
        grant = LicenseGrant(
            product_permalink=product_permalink,
            license_key_hash=key_hash,
            license_key_enc=ciphertext,
            key_version=key_version,
        )
        db.add(grant)
    else:
        # Refresh the stored ciphertext (keys don't change, but keep it simple).
        ciphertext, key_version = encrypt_token(license_key)
        grant.license_key_enc = ciphertext
        grant.key_version = key_version
        grant.product_permalink = product_permalink
    grant.status = status
    purchase = purchase or {}
    grant.gumroad_purchase_id = str(purchase.get("id") or "") or None
    grant.product_name = str(purchase.get("product_name") or "") or None
    grant.buyer_email_masked = mask_email(purchase.get("email"))
    if uses is not None:
        grant.uses = int(uses)
    grant.last_verified_at = _now()
    db.commit()
    db.refresh(grant)
    return grant


def verify_and_grant(db: Session, product_permalink: str, license_key: str,
                     transport: httpx.BaseTransport | None = None) -> tuple[bool, str, LicenseGrant | None]:
    """Verify a buyer's license with Gumroad and persist the grant.

    Returns (ok, reason, grant). Never raises for Gumroad-side rejections;
    raises GumroadError only when Gumroad could not be reached (fail closed).
    """
    prefix = license_key_hash(license_key)[:8]
    try:
        body = verify_license_noauth(product_permalink, license_key,
                                     increment_uses_count=True, transport=transport)
    except GumroadClientError as exc:
        grant = _upsert_grant(db, product_permalink, license_key, "invalid", None, None)
        log.info("license invalid key=%s", prefix)
        return False, "invalid_license", grant
    if not body.get("success"):
        grant = _upsert_grant(db, product_permalink, license_key, "invalid", None, None)
        return False, "invalid_license", grant
    purchase = body.get("purchase") or {}
    ok, reason = purchase_is_good(purchase)
    status = "active" if ok else {
        "purchase_refunded": "refunded",
        "purchase_chargebacked": "refunded",
        "purchase_disputed": "revoked",
        "subscription_ended": "revoked",
    }.get(reason, "invalid")
    grant = _upsert_grant(db, product_permalink, license_key, status, purchase,
                          body.get("uses"))
    if not ok:
        log.info("license denied key=%s reason=%s", prefix, reason)
        return False, reason, grant
    log.info("license granted key=%s product=%s", prefix, purchase.get("product_name"))
    return True, "ok", grant


def recheck_grant(db: Session, grant: LicenseGrant,
                  transport: httpx.BaseTransport | None = None) -> tuple[bool, str]:
    """Re-verify a stored grant against Gumroad (refund/revoke detection).

    Raises GumroadError when Gumroad is unreachable -> caller must fail closed.
    Returns (ok, reason) and persists the new status.
    """
    license_key = decrypt_token(grant.license_key_enc, grant.key_version)
    prefix = license_key_hash(license_key)[:8]
    try:
        body = verify_license_noauth(grant.product_permalink, license_key,
                                     increment_uses_count=False, transport=transport)
    except GumroadClientError:
        grant.status = "invalid"
        grant.last_verified_at = _now()
        db.commit()
        log.info("recheck: license now invalid key=%s", prefix)
        return False, "invalid_license"
    if not body.get("success"):
        grant.status = "invalid"
        grant.last_verified_at = _now()
        db.commit()
        return False, "invalid_license"
    purchase = body.get("purchase") or {}
    ok, reason = purchase_is_good(purchase)
    if not ok:
        grant.status = {
            "purchase_refunded": "refunded",
            "purchase_chargebacked": "refunded",
            "purchase_disputed": "revoked",
            "subscription_ended": "revoked",
        }.get(reason, "invalid")
        grant.last_verified_at = _now()
        db.commit()
        log.info("recheck: access revoked key=%s reason=%s", prefix, reason)
        return False, reason
    grant.status = "active"
    grant.uses = int(body.get("uses") or grant.uses)
    grant.last_verified_at = _now()
    db.commit()
    return True, "ok"
