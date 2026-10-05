"""Automation engine: TRIGGER -> CONDITION -> ACTION -> EXECUTION -> LOG.

Supported triggers (only what the Gumroad API + polling can really detect):
  new_sale, refund, new_subscriber, product_change  (from sync diffs)
  schedule                                          (from the scheduler)
  sales_threshold                                   (revenue in a window, checked after sync)

NOT supported by the Gumroad API (rejected at rule creation, never faked):
  subscription_cancelled, email_customer_via_gumroad, product_create, ...

Supported conditions: product, amount_min, amount_max, currency,
  buyer_email_domain, is_subscription, account, time_window, first_time_buyer.

Supported actions (only real ones): notify, offer_code_create/update/delete,
  license_enable/disable, refund, mark_shipped, csv_export, outbound_webhook,
  smtp_email.

Safety: idempotency key (rule + event), per-rule hourly rate cap, dry-run by
default, refund/mark_shipped require explicit confirm, per-step execution log.
"""
import csv
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import mailer
from app.core.security import utcnow
from app.gumroad.exceptions import GumroadError
from app.models.models import (
    AutomationAction,
    AutomationCondition,
    AutomationExecution,
    AutomationRule,
    Customer,
    GumroadAccount,
    Product,
    Sale,
    Subscriber,
)

log = logging.getLogger(__name__)

SUPPORTED_TRIGGERS = {
    "new_sale", "refund", "new_subscriber", "product_change",
    "schedule", "sales_threshold",
}

# Triggers/actions we explicitly refuse because the Gumroad API cannot do them.
UNSUPPORTED = {
    "subscription_cancelled": "Not supported by Gumroad API (no subscription-cancel endpoint)",
    "email_customer_via_gumroad": "Not supported by Gumroad API (no customer-email endpoint)",
    "product_create": "Not supported by Gumroad API (no product-create endpoint)",
    "product_update": "Not supported by Gumroad API (no product-update endpoint)",
    "cancel_subscription": "Not supported by Gumroad API (no subscription-cancel endpoint)",
}

SUPPORTED_ACTIONS = {
    "notify", "offer_code_create", "offer_code_update", "offer_code_delete",
    "license_enable", "license_disable", "refund", "mark_shipped",
    "csv_export", "outbound_webhook", "smtp_email",
}

CONDITION_FIELDS = {
    "product", "amount_min", "amount_max", "currency", "buyer_email_domain",
    "is_subscription", "account", "time_window", "first_time_buyer",
    # sales_threshold trigger only:
    "revenue_cents", "window_hours",
}


# ------------------------------------------------------------ context -----

def _build_context(db: Session, account: GumroadAccount, event_type: str,
                   payload: dict) -> dict:
    ctx: dict = {
        "event_type": event_type,
        "account_id": account.id,
        "account_name": account.name,
        "source": "sync",
        "depth": 0,
    }
    sale = None
    if payload.get("sale_id"):
        sale = db.get(Sale, payload["sale_id"])
    if sale:
        product = db.get(Product, sale.product_id) if sale.product_id else None
        ctx.update({
            "sale_id": sale.id,
            "sale_gumroad_id": sale.gumroad_id,
            "product": (product.gumroad_id if product else None),
            "product_id": sale.product_id,
            "product_gumroad_id": product.gumroad_id if product else None,
            "amount_cents": sale.price_cents,
            "currency": sale.currency,
            "buyer_email": sale.email,
            "buyer_email_domain": (sale.email or "").split("@")[-1] if sale.email else "",
            "is_subscription": sale.is_subscription,
            "license_key": sale.license_key,
        })
        if sale.email:
            cust = db.scalar(select(Customer).where(
                Customer.account_id == account.id, Customer.email == sale.email))
            ctx["first_time_buyer"] = bool(cust and cust.purchase_count <= 1)
    if payload.get("subscriber_id"):
        sub = db.get(Subscriber, payload["subscriber_id"])
        if sub:
            ctx.update({
                "subscriber_id": sub.id,
                "buyer_email": sub.email,
                "buyer_email_domain": (sub.email or "").split("@")[-1] if sub.email else "",
                "product_id": sub.product_id,
            })
    if payload.get("product_id"):
        product = db.get(Product, payload["product_id"])
        if product:
            ctx.update({"product": product.gumroad_id, "product_id": product.id,
                        "product_gumroad_id": product.gumroad_id})
    ctx.update({k: v for k, v in payload.items() if k not in ctx})
    return ctx


# ------------------------------------------------------------ conditions --

def _eval_condition(cond: AutomationCondition, ctx: dict) -> bool:
    field, op, raw = cond.field, cond.operator, cond.value
    if field == "product":
        actual = ctx.get("product") or ctx.get("product_gumroad_id")
        return _compare(str(actual or ""), op, raw or "")
    if field == "amount_min":
        return (ctx.get("amount_cents") or 0) >= int(raw or 0)
    if field == "amount_max":
        return (ctx.get("amount_cents") or 0) <= int(raw or 0)
    if field == "currency":
        return _compare((ctx.get("currency") or "").lower(), op, (raw or "").lower())
    if field == "buyer_email_domain":
        return _compare((ctx.get("buyer_email_domain") or "").lower(), op, (raw or "").lower())
    if field == "is_subscription":
        want = (raw or "").lower() in ("true", "1", "yes")
        return bool(ctx.get("is_subscription")) == want
    if field == "account":
        return _compare(ctx.get("account_id") or "", op, raw or "")
    if field == "time_window":
        # raw like "9-17" (hours, UTC)
        try:
            start_h, end_h = (raw or "0-24").split("-")
            h = utcnow().hour
            return int(start_h) <= h < int(end_h)
        except Exception:
            return False  # fail closed on malformed window
    if field == "first_time_buyer":
        want = (raw or "").lower() in ("true", "1", "yes")
        return bool(ctx.get("first_time_buyer")) == want
    if field == "revenue_cents":
        # Used by the sales_threshold trigger; ctx carries the computed value.
        try:
            actual = int(ctx.get("revenue_cents") or 0)
            expected = int(raw or 0)
        except (TypeError, ValueError):
            return False
        return _compare_num(actual, op, expected)
    if field == "window_hours":
        return True  # applied when the threshold window was computed
    return False


def _compare(actual: str, op: str, expected: str) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "contains":
        return expected in actual
    if op == "gt":
        return actual > expected
    if op == "lt":
        return actual < expected
    return False


def _compare_num(actual: int, op: str, expected: int) -> bool:
    if op in ("eq",):
        return actual == expected
    if op == "ne":
        return actual != expected
    if op in ("gte", "ge"):
        return actual >= expected
    if op in ("lte", "le"):
        return actual <= expected
    if op == "gt":
        return actual > expected
    if op == "lt":
        return actual < expected
    return False


def conditions_pass(rule: AutomationRule, ctx: dict) -> bool:
    return all(_eval_condition(c, ctx) for c in rule.conditions)


# ------------------------------------------------------------ actions -----

def _execute_action(db: Session, account: GumroadAccount, action: AutomationAction,
                    ctx: dict, dry_run: bool) -> dict:
    """Execute one action. Returns a step dict for the execution log."""
    atype = action.action_type
    params = dict(action.params or {})
    step = {"action": atype, "dry_run": dry_run, "status": "ok", "detail": {}}

    if atype not in SUPPORTED_ACTIONS:
        step.update(status="skipped",
                    detail={"reason": UNSUPPORTED.get(atype, "Not supported by Gumroad API")})
        return step

    if dry_run:
        step.update(status="dry_run", detail={"would_execute": params})
        return step

    try:
        if atype == "notify":
            from app.services.notify_service import notify
            notify(db, account.user_id,
                   title=params.get("title", "Automation"),
                   body=params.get("body", ""),
                   kind="automation", account_id=account.id)
        elif atype in ("offer_code_create", "offer_code_update", "offer_code_delete",
                       "license_enable", "license_disable"):
            _gumroad_mutation(db, account, atype, params, ctx)
        elif atype in ("refund", "mark_shipped"):
            if not params.get("confirm"):
                step.update(status="skipped",
                            detail={"reason": "explicit confirm=true required"})
                return step
            _gumroad_mutation(db, account, atype, params, ctx)
        elif atype == "csv_export":
            path = _export_csv(db, account, params.get("entity", "sales"))
            step["detail"] = {"csv_path": path}
        elif atype == "outbound_webhook":
            url = params.get("url")
            if not url:
                raise ValueError("outbound_webhook needs params.url")
            with httpx.Client(timeout=15) as http:
                r = http.post(url, json={"event": ctx.get("event_type"), "context": ctx})
                step["detail"] = {"http_status": r.status_code}
        elif atype == "smtp_email":
            ok = mailer.send_email(params.get("to", ""), params.get("subject", "Automation"),
                                   params.get("body", ""))
            step["detail"] = {"sent": ok}
    except Exception as exc:
        step.update(status="failed", detail={"error": str(exc)[:300]})
        log.warning("automation action failed type=%s err=%s", atype, exc)
    return step


def _gumroad_mutation(db: Session, account: GumroadAccount, atype: str,
                      params: dict, ctx: dict) -> None:
    from app.services.account_service import get_client

    client = get_client(db, account)
    try:
        if atype == "offer_code_create":
            product_gid = _resolve_product_gid(db, account, params, ctx)
            client.create_offer_code(product_gid, {k: v for k, v in params.items()
                                                  if k not in ("product_id",)})
        elif atype == "offer_code_update":
            product_gid = _resolve_product_gid(db, account, params, ctx)
            client.update_offer_code(product_gid, params["offer_code_id"],
                                     {k: v for k, v in params.items()
                                      if k not in ("product_id", "offer_code_id")})
        elif atype == "offer_code_delete":
            product_gid = _resolve_product_gid(db, account, params, ctx)
            client.delete_offer_code(product_gid, params["offer_code_id"])
        elif atype == "license_enable":
            client.enable_license(_resolve_product_gid(db, account, params, ctx),
                                  params.get("license_key") or ctx.get("license_key"))
        elif atype == "license_disable":
            client.disable_license(_resolve_product_gid(db, account, params, ctx),
                                   params.get("license_key") or ctx.get("license_key"))
        elif atype == "refund":
            sale_gid = _resolve_sale_gid(db, account, params, ctx)
            client.refund_sale(sale_gid)
        elif atype == "mark_shipped":
            sale_gid = _resolve_sale_gid(db, account, params, ctx)
            client.mark_as_shipped(sale_gid, params.get("tracking_url"))
    finally:
        client.close()


def _resolve_product_gid(db: Session, account: GumroadAccount, params: dict, ctx: dict) -> str:
    pid = params.get("product_id") or ctx.get("product_id")
    if pid:
        prod = db.get(Product, pid)
        if prod and prod.account_id == account.id:
            return prod.gumroad_id
    gid = params.get("product_gumroad_id") or ctx.get("product_gumroad_id")
    if not gid:
        raise GumroadError("no product specified for action")
    return gid


def _resolve_sale_gid(db: Session, account: GumroadAccount, params: dict, ctx: dict) -> str:
    sid = params.get("sale_id") or ctx.get("sale_id")
    if sid:
        sale = db.get(Sale, sid)
        if sale and sale.account_id == account.id:
            return sale.gumroad_id
    raise GumroadError("no sale specified for action")


def _export_csv(db: Session, account: GumroadAccount, entity: str) -> str:
    os.makedirs("exports", exist_ok=True)
    path = os.path.join("exports", f"{account.id}_{entity}_{utcnow():%Y%m%d%H%M%S}.csv")
    if entity == "sales":
        rows = db.scalars(select(Sale).where(Sale.account_id == account.id)).all()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "email", "price_cents", "currency", "refunded", "created"])
            for s in rows:
                w.writerow([s.gumroad_id, s.email, s.price_cents, s.currency,
                            s.refunded, s.gumroad_created_at])
    else:
        raise ValueError(f"csv_export: unsupported entity '{entity}'")
    return path


# ------------------------------------------------------------ engine ------

def _matching_rules(db: Session, account: GumroadAccount, trigger: str) -> list[AutomationRule]:
    return list(db.scalars(select(AutomationRule).where(
        AutomationRule.trigger == trigger,
        AutomationRule.enabled.is_(True),
        AutomationRule.user_id == account.user_id,
    )).all())


def _rate_cap_ok(db: Session, rule: AutomationRule) -> bool:
    since = utcnow() - timedelta(hours=1)
    n = db.scalar(select(func.count(AutomationExecution.id)).where(
        AutomationExecution.rule_id == rule.id,
        AutomationExecution.created_at >= since,
    ))
    return (n or 0) < rule.max_actions_per_hour


def run_rule(db: Session, rule: AutomationRule, account: GumroadAccount,
             event_type: str, event_id: str, ctx: dict) -> AutomationExecution | None:
    """Run one rule against an event. Returns the execution or None if skipped."""
    if ctx.get("depth", 0) > 0:
        return None  # loop prevention
    if not conditions_pass(rule, ctx):
        return None
    if not _rate_cap_ok(db, rule):
        log.warning("automation rate cap hit rule=%s", rule.id)
        return None

    key = f"{rule.id}:{event_type}:{event_id}"
    existing = db.scalar(select(AutomationExecution).where(
        AutomationExecution.idempotency_key == key))
    if existing:
        return existing  # idempotent: already handled

    steps = []
    dry_run = rule.dry_run
    for action in sorted(rule.actions, key=lambda a: a.order):
        steps.append(_execute_action(db, account, action, ctx, dry_run))

    failed = any(s["status"] == "failed" for s in steps)
    execution = AutomationExecution(
        rule_id=rule.id, idempotency_key=key, event_type=event_type,
        event_id=event_id,
        status="failed" if failed else ("dry_run" if dry_run else "completed"),
        steps=steps,
    )
    db.add(execution)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # raced with another worker; treat as handled
        return db.scalar(select(AutomationExecution).where(
            AutomationExecution.idempotency_key == key))
    db.refresh(execution)
    return execution


def handle_event(db: Session, account: GumroadAccount, event_type: str,
                 payload: dict) -> list[AutomationExecution]:
    """Entry point for sync-diff triggers."""
    if event_type not in SUPPORTED_TRIGGERS:
        return []
    ctx = _build_context(db, account, event_type, payload)
    event_id = str(payload.get("sale_id") or payload.get("subscriber_id")
                   or payload.get("product_id") or "")
    out = []
    for rule in _matching_rules(db, account, event_type):
        if rule.account_id and rule.account_id != account.id:
            continue
        ex = run_rule(db, rule, account, event_type, event_id, ctx)
        if ex:
            out.append(ex)
    return out


def check_threshold_rules(db: Session, account: GumroadAccount) -> list[AutomationExecution]:
    """Fire sales_threshold rules once per hour bucket when revenue >= threshold."""
    out = []
    for rule in _matching_rules(db, account, "sales_threshold"):
        if rule.account_id and rule.account_id != account.id:
            continue
        threshold = None
        window_hours = 24
        for c in rule.conditions:
            if c.field == "revenue_cents" and c.operator in ("gte", "gt"):
                threshold = int(c.value or 0)
            if c.field == "window_hours":
                window_hours = int(c.value or 24)
        if threshold is None:
            continue
        since = utcnow() - timedelta(hours=window_hours)
        revenue = db.scalar(select(func.coalesce(func.sum(Sale.price_cents), 0)).where(
            Sale.account_id == account.id,
            Sale.refunded.is_(False),
            Sale.gumroad_created_at >= since,
        )) or 0
        if revenue >= threshold:
            bucket = utcnow().strftime("%Y%m%d%H")
            ctx = {"event_type": "sales_threshold", "account_id": account.id,
                   "revenue_cents": revenue, "threshold_cents": threshold,
                   "window_hours": window_hours, "source": "sync", "depth": 0}
            ex = run_rule(db, rule, account, "sales_threshold", f"bucket:{bucket}", ctx)
            if ex:
                out.append(ex)
    return out


def run_scheduled_rule(db: Session, rule_id: str) -> AutomationExecution | None:
    """Entry point for the schedule/time trigger (called by the scheduler)."""
    rule = db.get(AutomationRule, rule_id)
    if not rule or not rule.enabled or rule.trigger != "schedule":
        return None
    account = db.get(GumroadAccount, rule.account_id) if rule.account_id else None
    if account is None:
        # Rule without account: needs an account to act on; skip honestly.
        log.warning("scheduled rule %s has no account; skipping", rule.id)
        return None
    ctx = {"event_type": "schedule", "account_id": account.id,
           "account_name": account.name, "source": "scheduler", "depth": 0}
    bucket = utcnow().strftime("%Y%m%d%H%M")
    return run_rule(db, rule, account, "schedule", f"at:{bucket}", ctx)
