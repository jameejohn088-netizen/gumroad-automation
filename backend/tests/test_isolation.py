"""Account isolation: one account can never read another account's data.
'All accounts' = union of the logged-in user's own accounts only."""
from sqlalchemy import func, select

from app.models.models import Product, Sale
from app.services.sync_service import sync_account


def _sync(db, account_id):
    return sync_account(db, account_id, fire_events=False)


def test_cross_user_isolation(client, auth_headers, connected_account_factory, mock_gumroad, db):
    headers_a, user_a = auth_headers()
    headers_b, user_b = auth_headers()
    acct_a = connected_account_factory(user_a, "A's Store")
    _sync(db, acct_a.id)
    assert db.scalar(select(func.count(Sale.id))) == 3

    # User B sees nothing of A's accounts or data.
    r = client.get("/api/v1/gumroad-accounts", headers=headers_b)
    assert r.json() == []
    r = client.get(f"/api/v1/gumroad-accounts/{acct_a.id}", headers=headers_b)
    assert r.status_code == 404
    r = client.get("/api/v1/sales", headers=headers_b)
    assert r.json()["total"] == 0
    r = client.get("/api/v1/dashboard", headers=headers_b)
    assert r.json()["sales_count"] == 0
    # B cannot act on A's sale either (404, not 403 — no leak).
    sale = db.scalars(select(Sale)).first()
    r = client.post(f"/api/v1/sales/{sale.id}/refund", headers=headers_b,
                    json={"dry_run": True})
    assert r.status_code == 404


def test_all_accounts_is_union_of_own_accounts(client, auth_headers, connected_account_factory,
                                               mock_gumroad, db):
    headers, user = auth_headers()
    a1 = connected_account_factory(user, "Store 1")
    a2 = connected_account_factory(user, "Store 2")
    _sync(db, a1.id)
    _sync(db, a2.id)
    r = client.get("/api/v1/sales", headers=headers)
    assert r.json()["total"] == 6  # 3 + 3
    r = client.get(f"/api/v1/sales?account_id={a1.id}", headers=headers)
    assert r.json()["total"] == 3
    r = client.get("/api/v1/dashboard", headers=headers)
    assert r.json()["sales_count"] == 6


def test_more_than_ten_accounts(client, auth_headers, db):
    # No artificial account limit: 11 accounts all work.
    headers, user = auth_headers()
    from app.services import account_service
    for i in range(11):
        account_service.create_account(db, user.id, f"Store {i}")
    r = client.get("/api/v1/gumroad-accounts", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 11


def test_forged_account_id_rejected(client, auth_headers, account_factory, db):
    headers, user = auth_headers()
    acct = account_factory(user)
    r = client.get("/api/v1/sales?account_id=00000000-0000-0000-0000-000000000000",
                   headers=headers)
    assert r.status_code == 404
    # Unknown but well-formed id that is not theirs:
    r = client.get(f"/api/v1/gumroad-accounts/{acct.id}/sync-history",
                   headers=headers)
    assert r.status_code == 200  # own account works
