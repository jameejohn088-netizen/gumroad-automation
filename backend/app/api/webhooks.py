"""Webhooks.

- Receiver: POST /api/v1/webhooks/gumroad — accepts Gumroad event posts,
  dedupes by event id, stores them, and forwards sale events to the
  automation engine. Requires a PUBLIC HTTPS URL (optional upgrade);
  polling remains the primary mechanism.
- Management: CRUD for Gumroad resource_subscriptions (the real webhook
  mechanism in the Gumroad API).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.security import utcnow
from app.gumroad.exceptions import GumroadAuthError, GumroadError
from app.models.models import GumroadAccount, User, WebhookEvent, WebhookSubscription
from app.services import account_service
from app.services.notify_service import log_activity

log = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/gumroad")
async def gumroad_receiver(request: Request, db: Session = Depends(get_db)):
    """Public receiver. Event shape follows Gumroad's resource_subscriptions
    payloads; unknown shapes are stored raw and marked unprocessed."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"raw": str(payload)}

    event_id = str(payload.get("id") or payload.get("event_id") or "")
    resource = str(payload.get("resource_name") or payload.get("resource") or "unknown")
    account_id = payload.get("account_id")  # our account id, if the sender included it

    if not event_id:
        return {"ok": False, "reason": "no event id"}

    account = db.get(GumroadAccount, account_id) if account_id else None
    if account is None:
        # Can't attribute it — store under nothing? We require account linkage,
        # so we acknowledge but skip processing honestly.
        log.info("webhook event without attributable account; acknowledged only")
        return {"ok": True, "processed": False, "reason": "unknown account"}

    event = WebhookEvent(account_id=account.id, event_id=event_id,
                         resource_name=resource, payload=payload)
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # duplicate delivery — deduped
        return {"ok": True, "processed": False, "reason": "duplicate"}
    db.refresh(event)

    # Forward sale-ish events to the automation engine.
    try:
        from app.automation.engine import handle_event

        sale_gid = (payload.get("sale") or {}).get("id") if isinstance(payload.get("sale"), dict) else None
        if resource == "sale" and sale_gid:
            from app.models.models import Sale
            sale = db.scalar(select(Sale).where(
                Sale.account_id == account.id, Sale.gumroad_id == str(sale_gid)))
            if sale:
                handle_event(db, account, "new_sale", {"sale_id": sale.id})
        event.processed_at = utcnow()
        db.commit()
    except Exception:
        log.exception("webhook processing failed")
    return {"ok": True, "processed": True}


@router.get("/gumroad-accounts/{account_id}/webhook-subscriptions")
def list_subscriptions(account_id: str, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    acct = account_service._get_account(db, user.id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    rows = db.scalars(select(WebhookSubscription).where(
        WebhookSubscription.account_id == acct.id)).all()
    return [{"id": r.id, "gumroad_id": r.gumroad_id, "resource_name": r.resource_name,
             "webhook_url": r.webhook_url} for r in rows]


@router.post("/gumroad-accounts/{account_id}/webhook-subscriptions")
def create_subscription(account_id: str, body: dict, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """Create a real Gumroad resource_subscription. Needs a public HTTPS URL."""
    from app.core.config import get_settings

    acct = account_service._get_account(db, user.id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    resource_name = body.get("resource_name", "sale")
    webhook_url = body.get("webhook_url") or (
        get_settings().PUBLIC_BASE_URL.rstrip("/") + "/api/v1/webhooks/gumroad"
        if get_settings().PUBLIC_BASE_URL else None)
    if not webhook_url or not webhook_url.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Webhooks need a public HTTPS URL. Set PUBLIC_BASE_URL or pass webhook_url. "
                   "Polling remains the primary mechanism.")
    try:
        client = account_service.get_client(db, acct)
        try:
            resp = client.create_resource_subscription(resource_name, webhook_url)
        finally:
            client.close()
    except GumroadAuthError:
        account_service.mark_needs_reconnect(db, acct, "401 creating webhook subscription")
        raise HTTPException(status_code=409, detail="Account needs reconnecting")
    except GumroadError as exc:
        raise HTTPException(status_code=502, detail=f"Gumroad error: {exc}")
    sub = resp.get("resource_subscription") or resp
    row = WebhookSubscription(account_id=acct.id, gumroad_id=str(sub.get("id")),
                              resource_name=resource_name, webhook_url=webhook_url)
    db.add(row)
    db.commit()
    log_activity(db, "webhook.subscribed", user_id=user.id, account_id=acct.id,
                 detail={"resource": resource_name})
    return {"ok": True, "gumroad_id": row.gumroad_id}


@router.delete("/gumroad-accounts/{account_id}/webhook-subscriptions/{sub_id}")
def delete_subscription(account_id: str, sub_id: str, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    acct = account_service._get_account(db, user.id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    row = db.get(WebhookSubscription, sub_id)
    if not row or row.account_id != acct.id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    try:
        client = account_service.get_client(db, acct)
        try:
            client.delete_resource_subscription(row.gumroad_id)
        finally:
            client.close()
    except GumroadError as exc:
        raise HTTPException(status_code=502, detail=f"Gumroad error: {exc}")
    db.delete(row)
    db.commit()
    return {"ok": True}
