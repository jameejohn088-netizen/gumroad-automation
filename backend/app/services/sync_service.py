"""Synchronization: pull Gumroad data into the local DB.

- Idempotent upserts keyed by (account_id, gumroad_id).
- Incremental sales sync via the documented `after` filter where supported.
- Every run records a sync_history row.
- Customers are DERIVED from sales (deduplicated by email per account).
- Licenses are DERIVED from sales carrying a license_key
  (the API has no license-list endpoint — documented limitation).
- Memberships are DERIVED at read time (subscription products + subscribers).
- Detected events (new sale, refund, new subscriber, product change) are
  forwarded to the automation engine.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.gumroad.exceptions import GumroadAuthError, GumroadError
from app.models.models import (
    Customer,
    GumroadAccount,
    License,
    OfferCode,
    Product,
    Sale,
    Subscriber,
    SyncHistory,
    Variant,
)

log = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _upsert_product(db: Session, account: GumroadAccount, p: dict) -> tuple[Product, bool, bool]:
    """Return (product, created, changed)."""
    gid = str(p.get("id"))
    prod = db.scalar(select(Product).where(
        Product.account_id == account.id, Product.gumroad_id == gid))
    created = prod is None
    changed = False
    if created:
        prod = Product(account_id=account.id, gumroad_id=gid)
        db.add(prod)
    before = (prod.name, prod.price_cents, prod.published)
    prod.name = p.get("name") or gid
    prod.price_cents = int(p.get("price") or 0)
    prod.currency = (p.get("currency") or "usd").lower()
    prod.published = bool(p.get("published", True))
    prod.deleted = bool(p.get("deleted", False))
    sub_dur = p.get("subscription_duration")
    prod.subscription_duration = sub_dur
    prod.is_subscription = bool(sub_dur) or bool(p.get("is_tiered_membership"))
    prod.is_tiered_membership = bool(p.get("is_tiered_membership"))
    prod.sales_count = int(p.get("sales_count") or 0)
    prod.sales_usd_cents = int(p.get("sales_usd_cents") or 0)
    prod.thumbnail_url = p.get("thumbnail_url")
    prod.short_url = p.get("short_url")
    prod.raw = p
    changed = before != (prod.name, prod.price_cents, prod.published)
    return prod, created, changed


def _sync_variants(db: Session, account: GumroadAccount, prod: Product, p: dict) -> int:
    count = 0
    for cat in p.get("variants") or []:
        cat_title = cat.get("title")
        cat_id = cat.get("id")
        for opt in cat.get("options") or []:
            gid = str(opt.get("id") or f"{prod.gumroad_id}:{cat_title}:{opt.get('name')}")
            var = db.scalar(select(Variant).where(
                Variant.account_id == account.id, Variant.gumroad_id == gid))
            if var is None:
                var = Variant(account_id=account.id, gumroad_id=gid, product_id=prod.id)
                db.add(var)
            var.product_id = prod.id
            var.category_title = cat_title
            var.name = opt.get("name") or gid
            pd = opt.get("price_difference")
            var.price_difference_cents = int(pd) if pd is not None else None
            raw = dict(opt)
            raw["_variant_category_id"] = cat_id
            var.raw = raw
            count += 1
    return count


def _sync_offer_codes(db: Session, account: GumroadAccount, prod: Product, client) -> int:
    count = 0
    try:
        codes = list(client.list_offer_codes(prod.gumroad_id))
    except GumroadError as exc:
        log.warning("offer-code sync failed product=%s err=%s", prod.gumroad_id, exc)
        return 0
    for oc in codes:
        gid = str(oc.get("id"))
        row = db.scalar(select(OfferCode).where(
            OfferCode.account_id == account.id, OfferCode.gumroad_id == gid))
        if row is None:
            row = OfferCode(account_id=account.id, gumroad_id=gid, product_id=prod.id)
            db.add(row)
        row.product_id = prod.id
        row.name = oc.get("name") or gid
        row.code = oc.get("code")
        row.max_purchase_count = oc.get("max_purchase_count")
        row.raw = oc
        count += 1
    return count


def _upsert_sale(db: Session, account: GumroadAccount, s: dict) -> tuple[Sale, bool, bool]:
    """Return (sale, created, refund_transitioned)."""
    gid = str(s.get("id"))
    sale = db.scalar(select(Sale).where(
        Sale.account_id == account.id, Sale.gumroad_id == gid))
    created = sale is None
    refund_transition = False
    if created:
        sale = Sale(account_id=account.id, gumroad_id=gid)
        db.add(sale)
    was_refunded = sale.refunded
    sale.email = (s.get("email") or "").lower() or None
    sale.price_cents = int(s.get("price") or s.get("gumroad_fee") or 0)
    # Gumroad sale payloads use several price-ish fields; prefer explicit ones.
    for key in ("price", "amount_cents", "total_cents"):
        if s.get(key) is not None:
            try:
                sale.price_cents = int(s[key])
                break
            except (TypeError, ValueError):
                pass
    sale.currency = (s.get("currency") or "usd").lower()
    sale.refunded = bool(s.get("refunded"))
    sale.disputed = bool(s.get("disputed"))
    sale.chargebacked = bool(s.get("chargebacked"))
    prod_gid = s.get("product_id") or (s.get("product") or {}).get("id")
    if prod_gid:
        prod = db.scalar(select(Product).where(
            Product.account_id == account.id, Product.gumroad_id == str(prod_gid)))
        sale.product_id = prod.id if prod else None
    sale.is_subscription = bool(s.get("is_subscription") or s.get("subscription_id"))
    sale.license_key = s.get("license_key")
    sale.gumroad_created_at = _parse_dt(s.get("created_at") or s.get("sale_created_at"))
    sale.raw = s
    if not created and not was_refunded and sale.refunded:
        refund_transition = True
    return sale, created, refund_transition


def _rebuild_customers(db: Session, account: GumroadAccount) -> int:
    """Aggregate customers from the account's sales (dedupe by email)."""
    rows = db.execute(
        select(
            Sale.email,
            func.min(Sale.gumroad_created_at).label("first"),
            func.sum(Sale.price_cents).label("total"),
            func.count(Sale.id).label("cnt"),
        )
        .where(Sale.account_id == account.id, Sale.email.is_not(None),
               Sale.refunded.is_(False))
        .group_by(Sale.email)
    ).all()
    seen = set()
    for email, first, total, cnt in rows:
        email = email.lower()
        seen.add(email)
        cust = db.scalar(select(Customer).where(
            Customer.account_id == account.id, Customer.email == email))
        if cust is None:
            cust = Customer(account_id=account.id, email=email)
            db.add(cust)
        cust.first_purchase_at = first
        cust.total_spent_cents = int(total or 0)
        cust.purchase_count = int(cnt or 0)
    # Drop customers with no remaining (non-refunded) sales.
    for cust in db.scalars(select(Customer).where(Customer.account_id == account.id)):
        if cust.email not in seen:
            db.delete(cust)
    return len(seen)


def _sync_licenses_from_sales(db: Session, account: GumroadAccount) -> int:
    count = 0
    sales = db.scalars(select(Sale).where(
        Sale.account_id == account.id, Sale.license_key.is_not(None)))
    for sale in sales:
        lic = db.scalar(select(License).where(
            License.account_id == account.id, License.key == sale.license_key))
        if lic is None:
            lic = License(account_id=account.id, key=sale.license_key)
            db.add(lic)
        lic.email = sale.email
        lic.product_id = sale.product_id
        count += 1
    return count


def _upsert_subscriber(db: Session, account: GumroadAccount, s: dict) -> tuple[Subscriber, bool]:
    gid = str(s.get("id"))
    sub = db.scalar(select(Subscriber).where(
        Subscriber.account_id == account.id, Subscriber.gumroad_id == gid))
    created = sub is None
    if created:
        sub = Subscriber(account_id=account.id, gumroad_id=gid)
        db.add(sub)
    sub.email = (s.get("email") or "").lower() or None
    sub.status = s.get("status")
    prod_gid = s.get("product_id") or (s.get("product") or {}).get("id")
    if prod_gid:
        prod = db.scalar(select(Product).where(
            Product.account_id == account.id, Product.gumroad_id == str(prod_gid)))
        sub.product_id = prod.id if prod else None
    sub.gumroad_created_at = _parse_dt(s.get("created_at"))
    sub.raw = s
    return sub, created


def sync_account(
    db: Session,
    account_id: str,
    sync_type: str = "full",
    transport=None,
    fire_events: bool = True,
) -> dict:
    """Run a sync for one account. Returns a summary dict. Never raises
    GumroadAuthError to the caller — it marks the account needs_reconnect."""
    from app.services.account_service import (
        clear_error, get_client, mark_needs_reconnect, record_error,
    )

    account = db.get(GumroadAccount, account_id)
    if account is None:
        raise LookupError("account not found")

    hist = SyncHistory(account_id=account.id, sync_type=sync_type, status="running",
                       started_at=_utcnow())
    db.add(hist)
    db.commit()

    items = 0
    events: list[tuple[str, dict]] = []
    try:
        if account.status == "disabled":
            raise GumroadError("account is disabled")
        client = get_client(db, account, transport=transport)
        try:
            if sync_type in ("full", "products"):
                for p in client.list_products():
                    prod, created, changed = _upsert_product(db, account, p)
                    db.flush()
                    items += 1 + _sync_variants(db, account, prod, p)
                    items += _sync_offer_codes(db, account, prod, client)
                    if changed and not created:
                        events.append(("product_change", {"product_id": prod.id}))
                db.commit()
            if sync_type in ("full", "sales"):
                after = None
                if account.last_sync_at:
                    after = account.last_sync_at.date().isoformat()
                for s in client.list_sales(after=after):
                    sale, created, refunded = _upsert_sale(db, account, s)
                    db.flush()
                    items += 1
                    if created:
                        events.append(("new_sale", {"sale_id": sale.id}))
                    elif refunded:
                        events.append(("refund", {"sale_id": sale.id}))
                db.commit()
                items += _rebuild_customers(db, account)
                items += _sync_licenses_from_sales(db, account)
                db.commit()
            if sync_type in ("full", "subscribers"):
                try:
                    for s in client.list_subscribers():
                        sub, created = _upsert_subscriber(db, account, s)
                        db.flush()
                        items += 1
                        if created:
                            events.append(("new_subscriber", {"subscriber_id": sub.id}))
                    db.commit()
                except GumroadError as exc:
                    # /subscribers is not available on all Gumroad accounts (404).
                    # Don't fail the whole sync — products/sales already saved.
                    db.rollback()
                    log.warning("subscribers sync skipped account=%s: %s", account.id, exc)
        finally:
            client.close()

        account.last_sync_at = _utcnow()
        hist.status = "success"
        hist.items_synced = items
        hist.finished_at = _utcnow()
        db.commit()
        clear_error(db, account)
    except GumroadAuthError as exc:
        db.rollback()
        hist.status = "failed"
        hist.error = str(exc)
        hist.finished_at = _utcnow()
        db.commit()
        mark_needs_reconnect(db, account, "401 during sync")
        return {"status": "failed", "error": "needs_reconnect", "items_synced": 0}
    except Exception as exc:
        db.rollback()
        hist.status = "failed"
        hist.error = str(exc)[:500]
        hist.finished_at = _utcnow()
        db.commit()
        record_error(db, account, f"sync failed: {exc}")
        log.exception("sync failed account=%s", account.id)
        return {"status": "failed", "error": str(exc)[:500], "items_synced": items}

    if fire_events and events:
        # Lazy import to avoid a cycle (engine imports services).
        from app.automation.engine import handle_event, check_threshold_rules

        for event_type, payload in events:
            try:
                handle_event(db, account, event_type, payload)
            except Exception:
                log.exception("automation event failed type=%s", event_type)
        try:
            check_threshold_rules(db, account)
        except Exception:
            log.exception("threshold check failed")

    return {"status": "success", "items_synced": items, "events": len(events)}
