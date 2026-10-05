"""Automation engine tests: triggers, conditions, actions, dry-run,
idempotency, rate caps, and honest rejection of unsupported features."""
from sqlalchemy import func, select

from app.automation import engine
from app.models.models import AutomationExecution, Notification, Sale
from app.services.sync_service import sync_account


def _seed(db, connected_account_factory, user, mock_gumroad):
    acct = connected_account_factory(user, "Auto Store")
    sync_account(db, acct.id, fire_events=False)
    return acct


def _rule(client, headers, **kw):
    body = {"name": "R1", "trigger": "new_sale", "dry_run": True,
            "conditions": [], "actions": [], **kw}
    r = client.post("/api/v1/automation-rules", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_new_sale_notify_dry_run_logs_without_side_effects(client, auth_headers,
                                                           connected_account_factory, mock_gumroad, db):
    headers, user = auth_headers()
    acct = _seed(db, connected_account_factory, user, mock_gumroad)
    _rule(client, headers, account_id=acct.id,
          actions=[{"action_type": "notify",
                    "params": {"title": "New sale!", "body": "cha-ching"}}])
    sale = db.scalars(select(Sale).where(Sale.account_id == acct.id)).first()

    execs = engine.handle_event(db, acct, "new_sale", {"sale_id": sale.id})
    assert len(execs) == 1
    assert execs[0].status == "dry_run"
    assert execs[0].steps[0]["status"] == "dry_run"
    # Dry run created no notification.
    assert db.scalar(select(func.count(Notification.id))) == 0


def test_live_notify_creates_notification(client, auth_headers, connected_account_factory,
                                          mock_gumroad, db):
    headers, user = auth_headers()
    acct = _seed(db, connected_account_factory, user, mock_gumroad)
    _rule(client, headers, account_id=acct.id, dry_run=False,
          actions=[{"action_type": "notify", "params": {"title": "Sold!"}}])
    sale = db.scalars(select(Sale).where(Sale.account_id == acct.id)).first()
    execs = engine.handle_event(db, acct, "new_sale", {"sale_id": sale.id})
    assert execs[0].status == "completed"
    notes = db.scalars(select(Notification)).all()
    assert len(notes) == 1 and notes[0].title == "Sold!"


def test_conditions_filter_events(client, auth_headers, connected_account_factory,
                                  mock_gumroad, db):
    headers, user = auth_headers()
    acct = _seed(db, connected_account_factory, user, mock_gumroad)
    # Only fire for sales >= 50000 cents; fixture sales are 1000/2000.
    _rule(client, headers, account_id=acct.id, dry_run=False,
          conditions=[{"field": "amount_min", "operator": "gte", "value": "50000"}],
          actions=[{"action_type": "notify", "params": {"title": "Big sale"}}])
    sale = db.scalars(select(Sale).where(Sale.account_id == acct.id)).first()
    execs = engine.handle_event(db, acct, "new_sale", {"sale_id": sale.id})
    assert execs == []
    assert db.scalar(select(func.count(Notification.id))) == 0


def test_idempotency_same_event_runs_once(client, auth_headers, connected_account_factory,
                                          mock_gumroad, db):
    headers, user = auth_headers()
    acct = _seed(db, connected_account_factory, user, mock_gumroad)
    _rule(client, headers, account_id=acct.id, dry_run=False,
          actions=[{"action_type": "notify", "params": {"title": "Hi"}}])
    sale = db.scalars(select(Sale).where(Sale.account_id == acct.id)).first()
    engine.handle_event(db, acct, "new_sale", {"sale_id": sale.id})
    engine.handle_event(db, acct, "new_sale", {"sale_id": sale.id})  # duplicate delivery
    assert db.scalar(select(func.count(AutomationExecution.id))) == 1
    assert db.scalar(select(func.count(Notification.id))) == 1


def test_per_rule_rate_cap(client, auth_headers, connected_account_factory, mock_gumroad, db):
    headers, user = auth_headers()
    acct = _seed(db, connected_account_factory, user, mock_gumroad)
    _rule(client, headers, account_id=acct.id, dry_run=False, max_actions_per_hour=1,
          actions=[{"action_type": "notify", "params": {"title": "Capped"}}])
    sales = db.scalars(select(Sale).where(Sale.account_id == acct.id)).all()
    engine.handle_event(db, acct, "new_sale", {"sale_id": sales[0].id})
    engine.handle_event(db, acct, "new_sale", {"sale_id": sales[1].id})
    assert db.scalar(select(func.count(Notification.id))) == 1


def test_refund_action_needs_confirm(client, auth_headers, connected_account_factory,
                                     mock_gumroad, db):
    headers, user = auth_headers()
    acct = _seed(db, connected_account_factory, user, mock_gumroad)
    # Without confirm -> skipped even when not dry_run.
    _rule(client, headers, account_id=acct.id, dry_run=False,
          actions=[{"action_type": "refund", "params": {}}])
    sale = db.scalars(select(Sale).where(Sale.account_id == acct.id)).first()
    execs = engine.handle_event(db, acct, "new_sale", {"sale_id": sale.id})
    assert execs[0].steps[0]["status"] == "skipped"
    assert mock_gumroad.instances[-1].calls == []

    # With confirm=true -> calls Gumroad.
    r = client.post("/api/v1/automation-rules", headers=headers, json={
        "name": "R2", "trigger": "new_sale", "account_id": acct.id, "dry_run": False,
        "actions": [{"action_type": "refund",
                     "params": {"confirm": True}}]})
    assert r.status_code == 201
    sale2 = db.scalars(select(Sale).where(Sale.account_id == acct.id)
                       .offset(1)).first()
    engine.handle_event(db, acct, "new_sale", {"sale_id": sale2.id})
    calls = mock_gumroad.instances[-1].calls
    assert ("refund_sale", sale2.gumroad_id) in calls


def test_unsupported_trigger_rejected_honestly(client, auth_headers):
    headers, _ = auth_headers()
    r = client.post("/api/v1/automation-rules", headers=headers, json={
        "name": "Bad", "trigger": "subscription_cancelled", "actions": []})
    assert r.status_code == 400
    assert "Not supported by Gumroad API" in r.json()["detail"]


def test_unsupported_action_rejected_honestly(client, auth_headers):
    headers, _ = auth_headers()
    r = client.post("/api/v1/automation-rules", headers=headers, json={
        "name": "Bad", "trigger": "new_sale",
        "actions": [{"action_type": "email_customer_via_gumroad"}]})
    assert r.status_code == 400
    assert "Not supported by Gumroad API" in r.json()["detail"]


def test_sales_threshold_trigger(client, auth_headers, connected_account_factory,
                                 mock_gumroad, db):
    headers, user = auth_headers()
    acct = _seed(db, connected_account_factory, user, mock_gumroad)
    _rule(client, headers, account_id=acct.id, trigger="sales_threshold",
          dry_run=False,
          conditions=[{"field": "revenue_cents", "operator": "gte", "value": "100"},
                      {"field": "window_hours", "operator": "eq", "value": "87600"}],
          actions=[{"action_type": "notify", "params": {"title": "Threshold hit"}}])
    execs = engine.check_threshold_rules(db, acct)
    assert len(execs) == 1
    # Second check in the same hour bucket is idempotent: same execution
    # returned, no duplicate row created.
    execs2 = engine.check_threshold_rules(db, acct)
    assert len(execs2) == 1
    assert execs2[0].id == execs[0].id
    assert db.scalar(select(func.count(AutomationExecution.id))) == 1


def test_rule_crud(client, auth_headers):
    headers, _ = auth_headers()
    rule = _rule(client, headers,
                 actions=[{"action_type": "notify", "params": {"title": "T"}}])
    rule_id = rule["id"]
    r = client.get("/api/v1/automation-rules", headers=headers)
    assert len(r.json()) == 1
    r = client.patch(f"/api/v1/automation-rules/{rule_id}", headers=headers,
                     json={"enabled": False})
    assert r.json()["enabled"] is False
    r = client.delete(f"/api/v1/automation-rules/{rule_id}", headers=headers)
    assert r.status_code == 200
    r = client.get(f"/api/v1/automation-rules/{rule_id}", headers=headers)
    assert r.status_code == 404
