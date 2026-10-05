"""Gumroad account management routes. No artificial account limit."""
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.gumroad.exceptions import GumroadAuthError, GumroadError
from app.models.models import GumroadAccount, SyncHistory, User
from app.schemas.schemas import (
    ConnectManualIn,
    GumroadAccountCreate,
    GumroadAccountOut,
    GumroadAccountUpdate,
    SyncHistoryOut,
    SyncOut,
)
from app.services import account_service
from app.services.notify_service import log_activity

router = APIRouter(prefix="/gumroad-accounts", tags=["gumroad-accounts"])
settings = get_settings()


def _out(db: Session, acct: GumroadAccount) -> GumroadAccountOut:
    token_last4 = acct.credential.token_last4 if acct.credential else None
    return GumroadAccountOut(
        id=acct.id, name=acct.name, status=acct.status, auth_mode=acct.auth_mode,
        gumroad_user_name=acct.gumroad_user_name, last_sync_at=acct.last_sync_at,
        token_last4=token_last4, created_at=acct.created_at,
    )


@router.get("", response_model=list[GumroadAccountOut])
def list_accounts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [_out(db, a) for a in account_service.user_accounts(db, user.id)]


@router.post("", response_model=GumroadAccountOut, status_code=201)
def create_account(body: GumroadAccountCreate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    acct = account_service.create_account(db, user.id, body.name, body.auth_mode)
    return _out(db, acct)


@router.get("/{account_id}", response_model=GumroadAccountOut)
def get_account(account_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    acct = account_service._get_account(db, user.id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    return _out(db, acct)


@router.patch("/{account_id}", response_model=GumroadAccountOut)
def update_account(account_id: str, body: GumroadAccountUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    acct = account_service._get_account(db, user.id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    if body.name is not None:
        acct.name = body.name
    if body.settings is not None:
        acct.settings = body.settings
    db.commit()
    db.refresh(acct)
    log_activity(db, "gumroad_account.updated", user_id=user.id, account_id=acct.id)
    return _out(db, acct)


@router.delete("/{account_id}")
def delete_account(account_id: str, confirm: bool = Query(default=False),
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not confirm:
        raise HTTPException(status_code=400,
                            detail="Add ?confirm=true to delete the account and all its data")
    try:
        account_service.remove_account(db, user.id, account_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"ok": True}


@router.post("/{account_id}/connect-manual", response_model=GumroadAccountOut)
def connect_manual(account_id: str, body: ConnectManualIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """Validate a manual access token via GET /v2/user, then store it encrypted."""
    try:
        acct = account_service.connect_manual(db, user.id, account_id, body.access_token)
    except LookupError:
        raise HTTPException(status_code=404, detail="Account not found")
    except GumroadAuthError:
        raise HTTPException(status_code=400,
                            detail="Gumroad rejected that token. Check it and try again.")
    except GumroadError as exc:
        raise HTTPException(status_code=502, detail=f"Gumroad error: {exc}")
    return _out(db, acct)


@router.post("/{account_id}/disconnect", response_model=GumroadAccountOut)
def disconnect(account_id: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    try:
        acct = account_service.disconnect(db, user.id, account_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Account not found")
    return _out(db, acct)


@router.post("/{account_id}/reconnect", response_model=GumroadAccountOut)
def reconnect(account_id: str, body: ConnectManualIn, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    try:
        acct = account_service.reconnect(db, user.id, account_id, body.access_token)
    except LookupError:
        raise HTTPException(status_code=404, detail="Account not found")
    except GumroadAuthError:
        raise HTTPException(status_code=400, detail="Gumroad rejected that token.")
    return _out(db, acct)


@router.post("/{account_id}/enable", response_model=GumroadAccountOut)
def enable(account_id: str, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    try:
        acct = account_service.set_enabled(db, user.id, account_id, True)
    except LookupError:
        raise HTTPException(status_code=404, detail="Account not found")
    return _out(db, acct)


@router.post("/{account_id}/disable", response_model=GumroadAccountOut)
def disable(account_id: str, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    try:
        acct = account_service.set_enabled(db, user.id, account_id, False)
    except LookupError:
        raise HTTPException(status_code=404, detail="Account not found")
    return _out(db, acct)


@router.post("/{account_id}/sync", response_model=SyncOut)
def sync_now(account_id: str, sync_type: str = Query(default="full"),
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Queue a sync via the scheduler (runs in background, DB-persisted)."""
    acct = account_service._get_account(db, user.id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    if sync_type not in ("full", "products", "sales", "subscribers"):
        raise HTTPException(status_code=400, detail="Invalid sync_type")
    from app.models.models import ScheduledJob
    from app.scheduler.scheduler import schedule_job

    job = ScheduledJob(
        user_id=user.id, account_id=acct.id,
        name=f"Sync {acct.name} ({sync_type})", job_type="once",
        schedule_config={"run_at": None},
        payload={"kind": "sync", "account_id": acct.id, "sync_type": sync_type},
        status="active",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    # one-time job with run_at=None -> runs immediately (date trigger, now)
    schedule_job(job)
    log_activity(db, "sync.queued", user_id=user.id, account_id=acct.id,
                 detail={"sync_type": sync_type})
    return SyncOut(job_id=job.id)


@router.get("/{account_id}/sync-history", response_model=list[SyncHistoryOut])
def sync_history(account_id: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user),
                 limit: int = Query(default=20, ge=1, le=100)):
    acct = account_service._get_account(db, user.id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    rows = db.scalars(select(SyncHistory).where(SyncHistory.account_id == acct.id)
                      .order_by(SyncHistory.created_at.desc()).limit(limit)).all()
    return rows


# ------------------------------------------------------- OAuth ------------

@router.get("/{account_id}/oauth/start")
def oauth_start(account_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    """Begin OAuth 2.0 authorization-code flow. Token is exchanged server-side."""
    acct = account_service._get_account(db, user.id, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    if not settings.GUMROAD_CLIENT_ID:
        raise HTTPException(status_code=400,
                            detail="GUMROAD_CLIENT_ID is not configured; use manual token mode")
    state = secrets.token_urlsafe(24)
    acct.settings = {**(acct.settings or {}), "oauth_state": state}
    db.commit()
    params = urlencode({
        "client_id": settings.GUMROAD_CLIENT_ID,
        "redirect_uri": settings.GUMROAD_REDIRECT_URI,
        "response_type": "code",
        "scope": "account view_sales edit_sales mark_sales_as_shipped edit_products",
        "state": f"{acct.id}:{state}",
    })
    return {"authorize_url": f"{settings.GUMROAD_AUTHORIZE_URL}?{params}"}


@router.get("/oauth/callback")
def oauth_callback(code: str | None = None, state: str | None = None,
                   db: Session = Depends(get_db)):
    """Exchange the authorization code for a token (server-side only)."""
    import httpx

    if not code or not state or ":" not in state:
        raise HTTPException(status_code=400, detail="Invalid OAuth callback")
    account_id, state_token = state.split(":", 1)
    acct = db.get(GumroadAccount, account_id)
    if not acct or (acct.settings or {}).get("oauth_state") != state_token:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    try:
        with httpx.Client(timeout=30) as http:
            r = http.post(settings.GUMROAD_TOKEN_URL, data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.GUMROAD_CLIENT_ID,
                "client_secret": settings.GUMROAD_CLIENT_SECRET,
                "redirect_uri": settings.GUMROAD_REDIRECT_URI,
            })
            r.raise_for_status()
            token = r.json().get("access_token")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {exc}")
    if not token:
        raise HTTPException(status_code=502, detail="No access token in OAuth response")
    try:
        account_service.connect_manual(db, acct.user_id, acct.id, token)
    except GumroadAuthError:
        raise HTTPException(status_code=400, detail="Gumroad rejected the OAuth token")
    acct.auth_mode = "oauth"
    acct.settings = {k: v for k, v in (acct.settings or {}).items() if k != "oauth_state"}
    db.commit()
    log_activity(db, "gumroad_account.oauth_connected", user_id=acct.user_id,
                 account_id=acct.id)
    return {"ok": True, "account_id": acct.id}
