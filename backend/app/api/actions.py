"""Real Gumroad write actions: refund, mark-as-shipped, resend receipt.

All default to dry_run=true. Executing for real requires dry_run=false AND
confirm=true (explicit confirmation). Account-scoped: the sale must belong
to one of the caller's accounts.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.gumroad.exceptions import GumroadAuthError, GumroadError
from app.models.models import GumroadAccount, Sale, User
from app.schemas.schemas import ActionResultOut, DryRunIn
from app.services import account_service
from app.services.notify_service import log_activity

router = APIRouter(tags=["sale-actions"])


def _sale_for_user(db: Session, user: User, sale_id: str) -> tuple[Sale, GumroadAccount]:
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    acct = account_service._get_account(db, user.id, sale.account_id)
    if acct is None:
        # Either another user's data or a forged id — same 404, no leak.
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale, acct


def _run(db: Session, user: User, sale: Sale, acct: GumroadAccount,
         body: DryRunIn, verb: str, fn_name: str) -> ActionResultOut:
    if body.dry_run:
        log_activity(db, f"sale.{verb}.dry_run", user_id=user.id, account_id=acct.id,
                     detail={"sale_id": sale.id})
        return ActionResultOut(dry_run=True, executed=False,
                               message=f"Dry run: {verb} would be sent to Gumroad for this sale.")
    if not body.confirm:
        raise HTTPException(status_code=400,
                            detail="Set confirm=true to execute this action for real")
    try:
        client = account_service.get_client(db, acct)
        try:
            result = getattr(client, fn_name)(sale.gumroad_id)
        finally:
            client.close()
    except GumroadAuthError:
        account_service.mark_needs_reconnect(db, acct, f"401 during {verb}")
        raise HTTPException(status_code=409,
                            detail="Gumroad rejected the token; account marked needs_reconnect")
    except GumroadError as exc:
        raise HTTPException(status_code=502, detail=f"Gumroad error: {exc}")
    log_activity(db, f"sale.{verb}", user_id=user.id, account_id=acct.id,
                 detail={"sale_id": sale.id, "gumroad": result})
    return ActionResultOut(dry_run=False, executed=True,
                           message=f"{verb} executed on Gumroad.", detail={"gumroad": result})


@router.post("/sales/{sale_id}/refund", response_model=ActionResultOut)
def refund_sale(sale_id: str, body: DryRunIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    sale, acct = _sale_for_user(db, user, sale_id)
    return _run(db, user, sale, acct, body, "refund", "refund_sale")


@router.post("/sales/{sale_id}/mark-shipped", response_model=ActionResultOut)
def mark_shipped(sale_id: str, body: DryRunIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    sale, acct = _sale_for_user(db, user, sale_id)
    return _run(db, user, sale, acct, body, "mark_as_shipped", "mark_as_shipped")


@router.post("/sales/{sale_id}/resend-receipt", response_model=ActionResultOut)
def resend_receipt(sale_id: str, body: DryRunIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    sale, acct = _sale_for_user(db, user, sale_id)
    return _run(db, user, sale, acct, body, "resend_receipt", "resend_receipt")
