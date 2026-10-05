"""Gumroad account management: add / connect / disconnect / reconnect /
enable / disable / remove (cascade). Tokens encrypted at rest (AES-GCM).

401 from Gumroad -> account marked 'needs_reconnect' + user notified.
"""
import logging

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
