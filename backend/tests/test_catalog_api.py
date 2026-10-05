"""Catalog, dashboard, and export API tests against real synced fixture data."""
from app.services.sync_service import sync_account


def _seed(db, connected_account_factory, user, mock_gumroad):
    acct = connected_account_factory(user, "Seed Store")
    result = sync_account(db, acct.id, fire_events=False)
    assert result["status"] == "success"
    return acct


def test_dashboard_aggregates(client, auth_headers, connected_account_factory, mock_gumroad, db):
    headers, user = auth_headers()
    _seed(db, connected_account_factory, user, mock_gumroad)
    r = client.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["revenue_cents"] == 4000
    assert d["sales_count"] == 3
    assert d["customers_count"] == 2  # alice + bob
    assert d["subscribers_count"] == 1
    assert d["products_count"] == 2
    assert len(d["recent_sales"]) == 3


def test_catalog_lists(client, auth_headers, connected_account_factory, mock_gumroad, db):
    headers, user = auth_headers()
    _seed(db, connected_account_factory, user, mock_gumroad)

    r = client.get("/api/v1/products", headers=headers)
    assert r.json()["total"] == 2
    r = client.get("/api/v1/products?q=ebook", headers=headers)
    assert r.json()["total"] == 1

    r = client.get("/api/v1/sales", headers=headers)
    assert r.json()["total"] == 3
    r = client.get("/api/v1/sales?q=alice", headers=headers)
    assert r.json()["total"] == 2

    r = client.get("/api/v1/customers", headers=headers)
    body = r.json()
    assert body["total"] == 2
    alice = next(c for c in body["items"] if c["email"] == "alice@example.com")
    assert alice["purchase_count"] == 2
    assert alice["total_spent_cents"] == 2000

    r = client.get("/api/v1/subscribers", headers=headers)
    assert r.json()["total"] == 1

    r = client.get("/api/v1/licenses", headers=headers)
    body = r.json()
    assert body["total"] == 1  # derived from sale_1's license_key
    assert body["items"][0]["key"] == "LIC-ALICE-1"

    r = client.get("/api/v1/memberships", headers=headers)
    body = r.json()
    assert body["total"] == 1  # bob's subscription to Course B
    assert body["items"][0]["product_name"] == "Course B"

    # Pagination shape.
    r = client.get("/api/v1/sales?page=1&per_page=2", headers=headers)
    body = r.json()
    assert body["total"] == 3 and body["page"] == 1 and body["per_page"] == 2
    assert len(body["items"]) == 2


def test_export_sales_csv(client, auth_headers, connected_account_factory, mock_gumroad, db):
    headers, user = auth_headers()
    _seed(db, connected_account_factory, user, mock_gumroad)
    r = client.get("/api/v1/export/sales.csv", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    text = r.text
    assert "sale_1" in text and "alice@example.com" in text
    assert text.count("\n") >= 4  # header + 3 rows


def test_refund_dry_run_and_confirm_required(client, auth_headers, connected_account_factory,
                                             mock_gumroad, db):
    from sqlalchemy import select
    from app.models.models import Sale
    headers, user = auth_headers()
    _seed(db, connected_account_factory, user, mock_gumroad)
    sale = db.scalars(select(Sale)).first()

    r = client.post(f"/api/v1/sales/{sale.id}/refund", headers=headers,
                    json={"dry_run": True})
    assert r.status_code == 200
    assert r.json()["dry_run"] is True and r.json()["executed"] is False

    # Real execution without confirm -> 400.
    r = client.post(f"/api/v1/sales/{sale.id}/refund", headers=headers,
                    json={"dry_run": False})
    assert r.status_code == 400

    # With confirm -> executes via the (fake) Gumroad client.
    r = client.post(f"/api/v1/sales/{sale.id}/refund", headers=headers,
                    json={"dry_run": False, "confirm": True})
    assert r.status_code == 200, r.text
    assert r.json()["executed"] is True
