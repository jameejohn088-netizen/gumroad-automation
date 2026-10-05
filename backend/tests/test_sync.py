"""Sync idempotency + 401 handling tests."""
from sqlalchemy import func, select

from app.models.models import Customer, Product, Sale, SyncHistory
from app.services.sync_service import sync_account


def test_sync_idempotent_second_run_changes_nothing(db, connected_account_factory,
                                                    user_factory, mock_gumroad):
    user, _ = user_factory()
    acct = connected_account_factory(user)
    r1 = sync_account(db, acct.id, fire_events=False)
    assert r1["status"] == "success"
    n_products = db.scalar(select(func.count(Product.id)))
    n_sales = db.scalar(select(func.count(Sale.id)))
    n_customers = db.scalar(select(func.count(Customer.id)))

    r2 = sync_account(db, acct.id, fire_events=False)
    assert r2["status"] == "success"
    assert db.scalar(select(func.count(Product.id))) == n_products
    assert db.scalar(select(func.count(Sale.id))) == n_sales
    assert db.scalar(select(func.count(Customer.id))) == n_customers
    # Two history rows, both successful.
    assert db.scalar(select(func.count(SyncHistory.id))) == 2


def test_sync_401_marks_needs_reconnect_and_notifies(db, connected_account_factory,
                                                     user_factory, mock_gumroad,
                                                     monkeypatch):
    from app.services import account_service
    from app.models.models import Notification

    user, _ = user_factory()
    acct = connected_account_factory(user)

    class BadClient:
        def __init__(self, *a, **k):
            pass

        def list_products(self, params=None):
            from app.gumroad.exceptions import GumroadAuthError
            raise GumroadAuthError("bad", 401)

        def close(self):
            pass

    monkeypatch.setattr("app.services.account_service.GumroadClient", BadClient)
    result = sync_account(db, acct.id, fire_events=False)
    assert result["status"] == "failed"
    assert result["error"] == "needs_reconnect"
    db.refresh(acct)
    assert acct.status == "needs_reconnect"
    notes = db.scalars(select(Notification).where(Notification.user_id == user.id)).all()
    assert any("reconnect" in n.title.lower() for n in notes)
    hist = db.scalars(select(SyncHistory).where(
        SyncHistory.account_id == acct.id)).all()
    assert hist[-1].status == "failed"


def test_sync_detects_new_sale_events(db, connected_account_factory, user_factory, mock_gumroad):
    user, _ = user_factory()
    acct = connected_account_factory(user)
    # First sync with events enabled but no rules: returns event count.
    r = sync_account(db, acct.id, fire_events=True)
    assert r["status"] == "success"
    assert r["events"] == 4  # 3 new sales + 1 new subscriber
    # Second sync: no new events.
    r = sync_account(db, acct.id, fire_events=True)
    assert r["events"] == 0


def test_customer_aggregates_exclude_refunded(db, connected_account_factory, user_factory,
                                             mock_gumroad):
    user, _ = user_factory()
    acct = connected_account_factory(user)
    sync_account(db, acct.id, fire_events=False)
    alice = db.scalar(select(Customer).where(Customer.email == "alice@example.com"))
    assert alice.purchase_count == 2 and alice.total_spent_cents == 2000
    # Mark one sale refunded and rebuild via a fresh sync pass.
    sale = db.scalars(select(Sale).where(Sale.email == "alice@example.com")).first()
    sale.refunded = True
    db.commit()
    from app.services.sync_service import _rebuild_customers
    _rebuild_customers(db, acct)
    db.commit()
    db.refresh(alice)
    assert alice.purchase_count == 1 and alice.total_spent_cents == 1000
