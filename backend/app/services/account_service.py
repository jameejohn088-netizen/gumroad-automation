"""Gumroad account management: add / connect / disconnect / reconnect /
enable / disable / remove (cascade). Tokens encrypted at rest (AES-GCM).

401 from Gumroad -> account marked 'needs_reconnect' + user notified.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gumroad.client import GumroadClient
from app.gumroad.exceptions import GumroadAuthError, GumroadError
from app.models.models import GumroadAccount, GumroadCredential
from app.security.encryption import decrypt_token, encrypt_token, token_last4
from app.services.notify_service import log_activity, notify

log = logging.getLogger(__name__)


def _get_account(db: Session, user_id: str, account_id: str) -> GumroadAccount | None:
    """Account-scoped fetch: never returns another user's account."""
    return db.scalar(
        select(GumroadAccount).where(
            GumroadAccount.id == account_id, GumroadAccount.user_id == user_id
        )
    )


def user_accounts(db: Session, user_id: str) -> list[GumroadAccount]:
    return list(db.scalars(
        select(GumroadAccount).where(GumroadAccount.user_id == user_id)
        .order_by(GumroadAccount.created_at)
    ))


def create_account(db: Session, user_id: str, name: str, auth_mode: str = "manual") -> GumroadAccount:
    acct = GumroadAccount(user_id=user_id, name=name, auth_mode=auth_mode, status="connected")
    db.add(acct)
    db.commit()
    db.refresh(acct)
    log_activity(db, "gumroad_account.created", user_id=user_id, account_id=acct.id,
                 detail={"name": name, "auth_mode": auth_mode})
    return acct


def store_token(db: Session, account: GumroadAccount, access_token: str) -> None:
    """Encrypt + store (replace) the account's token."""
    ciphertext, key_version = encrypt_token(access_token)
    cred = account.credential
    if cred is None:
        cred = GumroadCredential(account_id=account.id)
        db.add(cred)
    cred.encrypted_token = ciphertext
    cred.key_version = key_version
    cred.token_last4 = token_last4(access_token)
    db.commit()


def get_client(db: Session, account: GumroadAccount, transport=None) -> GumroadClient:
    """Build a Gumroad client with the decrypted token. Raises if none stored."""
    cred = account.credential
    if cred is None:
        raise GumroadError("no credentials stored for this account")
    token = decrypt_token(cred.encrypted_token, cred.key_version)
    return GumroadClient(access_token=token, account_id=account.id, transport=transport)


def connect_manual(db: Session, user_id: str, account_id: str, access_token: str,
                   transport=None) -> GumroadAccount:
    """Validate a manual token via GET /v2/user, then store it encrypted."""
    acct = _get_account(db, user_id, account_id)
    if acct is None:
        raise LookupError("account not found")
    client = GumroadClient(access_token=access_token, account_id=acct.id, transport=transport)
    try:
        user_info = client.get_user()
    except GumroadAuthError as exc:
        acct.status = "needs_reconnect"
        db.commit()
        raise exc
    finally:
        client.close()
    store_token(db, acct, access_token)
    acct.auth_mode = "manual"
    acct.status = "connected"
    user_block = user_info.get("user") or {}
    acct.gumroad_user_name = user_block.get("name") or user_block.get("display_name")
    acct.gumroad_user_id = str(user_block.get("user_id") or user_block.get("id") or "")
    db.commit()
    db.refresh(acct)
    log_activity(db, "gumroad_account.connected", user_id=user_id, account_id=acct.id)
    return acct


def mark_needs_reconnect(db: Session, account: GumroadAccount, reason: str = "401 from Gumroad") -> None:
    if account.status != "needs_reconnect":
        account.status = "needs_reconnect"
        db.commit()
        notify(db, account.user_id,
               title=f"Gumroad account '{account.name}' needs reconnecting",
               body=f"Gumroad rejected the stored token ({reason}). Reconnect the account to resume syncing.",
               kind="warning", account_id=account.id)
        log_activity(db, "gumroad_account.needs_reconnect", user_id=account.user_id,
                     account_id=account.id, detail={"reason": reason})


def record_error(db: Session, account: GumroadAccount, message: str) -> None:
    """Store the last Gumroad API error on the account for the dashboard."""
    account.status = "error"
    account.last_error = message[:500]
    account.last_error_at = datetime.now(timezone.utc)
    db.commit()
    log_activity(db, "gumroad_account.error", user_id=account.user_id,
                 account_id=account.id, detail={"error": message[:200]})


def clear_error(db: Session, account: GumroadAccount) -> None:
    """Clear the stored error after a successful Gumroad call."""
    if account.last_error or account.status == "error":
        account.last_error = None
        account.last_error_at = None
        if account.status == "error":
            account.status = "connected" if account.credential else "needs_reconnect"
        db.commit()


def test_connection(db: Session, user_id: str, account_id: str,
                    transport=None) -> dict:
    """Validate the stored token with GET /v2/user (read-only, no test data touched).

    Returns {"ok": True, "gumroad_user": ...} on success, or
    {"ok": False, "error": ...} on failure. Updates the account's
    status/last_error so the dashboard reflects the result.
    """
    acct = _get_account(db, user_id, account_id)
    if acct is None:
        raise LookupError("account not found")
    if acct.credential is None:
        record_error(db, acct, "no credentials stored for this account")
        return {"ok": False, "error": "no credentials stored for this account"}
    try:
        client = get_client(db, acct, transport=transport)
    except GumroadError as exc:
        record_error(db, acct, str(exc))
        return {"ok": False, "error": str(exc)}
    try:
        user_info = client.get_user()
    except GumroadAuthError as exc:
        mark_needs_reconnect(db, acct, f"401 during connection test: {exc}")
        record_error(db, acct, f"Gumroad rejected the token: {exc}")
        return {"ok": False, "error": f"Gumroad rejected the token: {exc}"}
    except GumroadError as exc:
        record_error(db, acct, str(exc))
        return {"ok": False, "error": str(exc)}
    finally:
        client.close()
    clear_error(db, acct)
    user_block = user_info.get("user") or {}
    acct.gumroad_user_name = user_block.get("name") or user_block.get("display_name")
    acct.gumroad_user_id = str(user_block.get("user_id") or user_block.get("id") or "")
    db.commit()
    db.refresh(acct)
    log_activity(db, "gumroad_account.test_connection", user_id=user_id,
                 account_id=acct.id, detail={"ok": True})
    return {"ok": True, "gumroad_user": acct.gumroad_user_name}


def disconnect(db: Session, user_id: str, account_id: str) -> GumroadAccount:
    acct = _get_account(db, user_id, account_id)
    if acct is None:
        raise LookupError("account not found")
    # Disconnect = remove stored token, keep synced data. Status -> disabled.
    if acct.credential:
        db.delete(acct.credential)
    acct.status = "disabled"
    db.commit()
    db.refresh(acct)
    log_activity(db, "gumroad_account.disconnected", user_id=user_id, account_id=acct.id)
    return acct


def reconnect(db: Session, user_id: str, account_id: str, access_token: str,
              transport=None) -> GumroadAccount:
    """Same validation as connect; re-enables the account."""
    acct = connect_manual(db, user_id, account_id, access_token, transport=transport)
    return acct


def set_enabled(db: Session, user_id: str, account_id: str, enabled: bool) -> GumroadAccount:
    acct = _get_account(db, user_id, account_id)
    if acct is None:
        raise LookupError("account not found")
    if enabled and acct.status == "disabled":
        acct.status = "connected" if acct.credential else "needs_reconnect"
    elif not enabled:
        acct.status = "disabled"
    db.commit()
    db.refresh(acct)
    log_activity(db, "gumroad_account.enabled" if enabled else "gumroad_account.disabled",
                 user_id=user_id, account_id=acct.id)
    return acct


def remove_account(db: Session, user_id: str, account_id: str) -> None:
    """Cascade delete the account and ALL its data (products, sales, jobs, logs...)."""
    acct = _get_account(db, user_id, account_id)
    if acct is None:
        raise LookupError("account not found")
    name = acct.name
    db.delete(acct)  # FK cascades handle the rest
    db.commit()
    log_activity(db, "gumroad_account.removed", user_id=user_id, detail={"name": name})
