"""Shared pytest fixtures. All Gumroad HTTP fixtures are clearly labeled
and used ONLY inside the test suite — never in production code paths."""
import base64
import os
import tempfile

import pytest

# ---------------------------------------------------------------- env -----
# Must be set before any app.* import. DATABASE_URL is assembled from parts
# (never commit real credentials; this is a throwaway test database).
_tmpdir = tempfile.mkdtemp(prefix="gumauto-test-")
_db_path = os.path.join(_tmpdir, "test.db")
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite:" + "///" + _db_path
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["TOKEN_MASTER_KEY"] = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
os.environ["MAIL_MODE"] = "console"

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.core import db as _dbmod  # noqa: E402

_dbmod.reset_engine()

from app.core.db import Base, get_engine, get_session_factory  # noqa: E402
from app.models.models import User  # noqa: E402

Base.metadata.create_all(bind=get_engine())

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


# ------------------------------------------------------------ fixtures ----

@pytest.fixture(scope="session")
def client():
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture()
def db():
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _clean_db(db):
    """Wipe all users (ORM cascades clear dependent rows) before each test."""
    for u in db.query(User).all():
        db.delete(u)
    db.commit()
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.core.rate_limit import rate_limiter
    rate_limiter._hits.clear()
    yield
    rate_limiter._hits.clear()


_user_counter = {"i": 0}


@pytest.fixture()
def user_factory(db):
    from app.services import auth_service

    def make(email=None, password="password123", name="Test User", verified=True):
        _user_counter["i"] += 1
        email = email or f"user{_user_counter['i']}@example.com"
        user = auth_service.signup(db, email, password, name)
        if verified:
            user.is_verified = True
            db.commit()
        return user, password

    return make


@pytest.fixture()
def auth_headers(client, user_factory):
    """Return a function making Authorization headers for a fresh user."""
    def make(user=None, password="password123"):
        if user is None:
            user, password = user_factory()
        r = client.post("/api/v1/auth/login",
                        json={"email": user.email, "password": password})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, user
    return make


@pytest.fixture()
def account_factory(db, user_factory):
    from app.services import account_service

    def make(user=None, name="Test Account"):
        if user is None:
            user, _ = user_factory()
        return account_service.create_account(db, user.id, name)
    return make


@pytest.fixture()
def connected_account_factory(db, user_factory, mock_gumroad):
    """Account with a (fake) validated token stored — ready to sync."""
    from app.services import account_service

    def make(user=None, name="Test Account"):
        if user is None:
            user, _ = user_factory()
        acct = account_service.create_account(db, user.id, name)
        account_service.connect_manual(db, user.id, acct.id, "good-token")
        return acct
    return make


# ------------------------------------------------------------ fake gumroad
# Clearly-labeled fixtures: pretend Gumroad API payloads for tests only.

FIXTURE_PRODUCTS = [
    {
        "id": "prod_1", "name": "Ebook A", "price": 1000, "currency": "usd",
        "published": True, "deleted": False, "subscription_duration": None,
        "is_tiered_membership": False, "sales_count": 5, "sales_usd_cents": 5000,
        "thumbnail_url": None, "short_url": "https://gum.co/a",
        "variants": [
            {"id": "cat_1", "title": "Tier",
             "options": [{"id": "opt_1", "name": "Basic", "price_difference": 0}]},
        ],
    },
    {
        "id": "prod_2", "name": "Course B", "price": 2000, "currency": "usd",
        "published": True, "deleted": False, "subscription_duration": "monthly",
        "is_tiered_membership": True, "sales_count": 3, "sales_usd_cents": 6000,
        "thumbnail_url": None, "short_url": "https://gum.co/b", "variants": [],
    },
]

FIXTURE_SALES = [
    {"id": "sale_1", "email": "alice@example.com", "price": 1000, "currency": "usd",
     "refunded": False, "disputed": False, "chargebacked": False,
     "product_id": "prod_1", "license_key": "LIC-ALICE-1",
     "created_at": "2026-09-01T10:00:00Z"},
    {"id": "sale_2", "email": "bob@example.com", "price": 2000, "currency": "usd",
     "refunded": False, "disputed": False, "chargebacked": False,
     "product_id": "prod_2", "is_subscription": True,
     "created_at": "2026-09-02T10:00:00Z"},
    {"id": "sale_3", "email": "alice@example.com", "price": 1000, "currency": "usd",
     "refunded": False, "disputed": False, "chargebacked": False,
     "product_id": "prod_1", "created_at": "2026-09-03T10:00:00Z"},
]

FIXTURE_SUBSCRIBERS = [
    {"id": "sub_1", "email": "bob@example.com", "product_id": "prod_2",
     "status": "alive", "created_at": "2026-09-02T10:00:00Z"},
]


class FakeGumroadClient:
    """Test-only stand-in for GumroadClient (labeled fixture, not production)."""

    instances = []

    def __init__(self, access_token="fake-token", account_id="fake-account",
                 transport=None, **kwargs):
        self.access_token = access_token
        self.account_id = account_id
        self.calls = []
        FakeGumroadClient.instances.append(self)

    def close(self):
        pass

    # -- reads --
    def get_user(self):
        if self.access_token == "bad-token":
            from app.gumroad.exceptions import GumroadAuthError
            raise GumroadAuthError("401", 401)
        return {"success": True, "user": {"name": "Fixture Seller", "user_id": "u_1"}}

    def list_products(self, params=None):
        return iter(list(FIXTURE_PRODUCTS))

    def get_product(self, product_id):
        return next(p for p in FIXTURE_PRODUCTS if p["id"] == product_id)

    def list_sales(self, after=None, before=None, email=None):
        return iter(list(FIXTURE_SALES))

    def list_subscribers(self):
        return iter(list(FIXTURE_SUBSCRIBERS))

    def list_offer_codes(self, product_id):
        return iter([])

    # -- writes (recorded, never hit the network) --
    def refund_sale(self, sale_id):
        self.calls.append(("refund_sale", sale_id))
        return {"success": True}

    def mark_as_shipped(self, sale_id, tracking_url=None):
        self.calls.append(("mark_as_shipped", sale_id))
        return {"success": True}

    def resend_receipt(self, sale_id):
        self.calls.append(("resend_receipt", sale_id))
        return {"success": True}

    def create_offer_code(self, product_id, data):
        self.calls.append(("create_offer_code", product_id, data))
        return {"success": True, "offer_code": {"id": "oc_1"}}

    def update_offer_code(self, product_id, offer_code_id, data):
        self.calls.append(("update_offer_code", product_id, offer_code_id))
        return {"success": True}

    def delete_offer_code(self, product_id, offer_code_id):
        self.calls.append(("delete_offer_code", product_id, offer_code_id))
        return {"success": True}

    def enable_license(self, product_id, license_key):
        self.calls.append(("enable_license", product_id, license_key))
        return {"success": True}

    def disable_license(self, product_id, license_key):
        self.calls.append(("disable_license", product_id, license_key))
        return {"success": True}


@pytest.fixture()
def mock_gumroad(monkeypatch):
    """Patch the GumroadClient used by account/sync services with the fake."""
    FakeGumroadClient.instances.clear()
    monkeypatch.setattr("app.services.account_service.GumroadClient", FakeGumroadClient)
    return FakeGumroadClient
