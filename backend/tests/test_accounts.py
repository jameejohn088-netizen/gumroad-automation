"""Gumroad account lifecycle: add, connect, disconnect, reconnect,
enable/disable, remove (cascade). Uses the labeled FakeGumroadClient."""
from sqlalchemy import func, select

from app.models.models import GumroadAccount, Product


def _create(client, headers, name="My Store"):
    r = client.post("/api/v1/gumroad-accounts", headers=headers,
                    json={"name": name, "auth_mode": "manual"})
    assert r.status_code == 201, r.text
    return r.json()


def test_add_and_list_accounts(client, auth_headers):
    headers, _ = auth_headers()
    _create(client, headers, "Store A")
    _create(client, headers, "Store B")
    r = client.get("/api/v1/gumroad-accounts", headers=headers)
    assert r.status_code == 200
    names = [a["name"] for a in r.json()]
    assert names == ["Store A", "Store B"]


def test_connect_manual_validates_token(client, auth_headers, mock_gumroad, db):
    headers, _ = auth_headers()
    acct = _create(client, headers)
    r = client.post(f"/api/v1/gumroad-accounts/{acct['id']}/connect-manual",
                    headers=headers, json={"access_token": "good-token"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "connected"
    assert body["token_last4"] == "oken"  # last 4 of "good-token"
    # Token stored encrypted, never plaintext.
    row = db.get(GumroadAccount, acct["id"])
    assert row.credential is not None
    assert "good-token" not in row.credential.encrypted_token
    assert row.credential.key_version == 1


def test_connect_manual_bad_token_rejected(client, auth_headers, mock_gumroad):
    headers, _ = auth_headers()
    acct = _create(client, headers)
    r = client.post(f"/api/v1/gumroad-accounts/{acct['id']}/connect-manual",
                    headers=headers, json={"access_token": "bad-token"})
    assert r.status_code == 400
    assert "rejected" in r.json()["detail"]


def test_disconnect_enable_disable(client, auth_headers, mock_gumroad):
    headers, _ = auth_headers()
    acct = _create(client, headers)
    client.post(f"/api/v1/gumroad-accounts/{acct['id']}/connect-manual",
                headers=headers, json={"access_token": "good-token"})

    r = client.post(f"/api/v1/gumroad-accounts/{acct['id']}/disconnect", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"
    assert r.json()["token_last4"] is None  # token removed

    r = client.post(f"/api/v1/gumroad-accounts/{acct['id']}/disable", headers=headers)
    assert r.json()["status"] == "disabled"
    r = client.post(f"/api/v1/gumroad-accounts/{acct['id']}/enable", headers=headers)
    # No token stored -> needs_reconnect, honestly reported.
    assert r.json()["status"] == "needs_reconnect"


def test_reconnect(client, auth_headers, mock_gumroad):
    headers, _ = auth_headers()
    acct = _create(client, headers)
    client.post(f"/api/v1/gumroad-accounts/{acct['id']}/disconnect", headers=headers)
    r = client.post(f"/api/v1/gumroad-accounts/{acct['id']}/reconnect",
                    headers=headers, json={"access_token": "good-token"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "connected"


def test_remove_requires_confirm_and_cascades(client, auth_headers, mock_gumroad, db):
    headers, user = auth_headers()
    acct = _create(client, headers)
    client.post(f"/api/v1/gumroad-accounts/{acct['id']}/connect-manual",
                headers=headers, json={"access_token": "good-token"})
    # Seed some synced data through the sync service.
    from app.services.sync_service import sync_account
    sync_account(db, acct["id"], transport=None)
    assert db.scalar(select(func.count(Product.id))) > 0

    r = client.delete(f"/api/v1/gumroad-accounts/{acct['id']}", headers=headers)
    assert r.status_code == 400  # confirm required
    r = client.delete(f"/api/v1/gumroad-accounts/{acct['id']}?confirm=true",
                      headers=headers)
    assert r.status_code == 200
    assert db.get(GumroadAccount, acct["id"]) is None
    assert db.scalar(select(func.count(Product.id))) == 0  # cascade wiped data


def test_sync_history_recorded(client, auth_headers, mock_gumroad, db):
    headers, _ = auth_headers()
    acct = _create(client, headers)
    client.post(f"/api/v1/gumroad-accounts/{acct['id']}/connect-manual",
                headers=headers, json={"access_token": "good-token"})
    from app.services.sync_service import sync_account
    result = sync_account(db, acct["id"])
    assert result["status"] == "success"
    r = client.get(f"/api/v1/gumroad-accounts/{acct['id']}/sync-history", headers=headers)
    assert r.status_code == 200
    hist = r.json()
    assert len(hist) == 1
    assert hist[0]["status"] == "success"
    assert hist[0]["items_synced"] > 0
