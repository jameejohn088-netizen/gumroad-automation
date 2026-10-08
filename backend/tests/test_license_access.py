"""Tests for Gumroad buyer license verification + gated APK download.

All Gumroad HTTP is faked by monkeypatching
app.services.license_service.verify_license_noauth — no network, no real keys.
"""
import os

import pytest

from app.core.config import get_settings
from app.gumroad.exceptions import GumroadClientError, GumroadError
from app.models.models import LicenseGrant
from app.security.encryption import decrypt_token


@pytest.fixture(autouse=True)
def _clean_grants(db):
    for g in db.query(LicenseGrant).all():
        db.delete(g)
    db.commit()
    yield
    for g in db.query(LicenseGrant).all():
        db.delete(g)
    db.commit()


@pytest.fixture()
def fake_verify(monkeypatch):
    """Control Gumroad license-verify responses via fake_verify.response."""
    state = {"mode": "ok"}

    def _fake(product_permalink, license_key, increment_uses_count=False, transport=None):
        mode = state["mode"]
        if mode == "transport_error":
            raise GumroadError("could not reach Gumroad")
        if mode == "invalid":
            raise GumroadClientError("That license key is invalid", 400)
        purchase = {
            "id": "pur_123",
            "product_name": "Test App",
            "email": "buyer@example.com",
            "refunded": False,
            "disputed": False,
            "dispute_won": False,
            "chargebacked": False,
            "subscription_ended_at": None,
        }
        if mode == "refunded":
            purchase["refunded"] = True
        if mode == "success_false":
            return {"success": False, "message": "disabled"}
        return {"success": True, "uses": 3, "purchase": purchase}

    monkeypatch.setattr("app.services.license_service.verify_license_noauth", _fake)
    return state


@pytest.fixture()
def apk_file(tmp_path, monkeypatch):
    p = tmp_path / "test.apk"
    p.write_bytes(b"FAKE-APK-BYTES")
    settings = get_settings()
    old = settings.APK_DOWNLOAD_PATH
    settings.APK_DOWNLOAD_PATH = str(p)
    yield p
    settings.APK_DOWNLOAD_PATH = old


def _grants(db):
    return db.query(LicenseGrant).all()


# ------------------------------------------------------------ verify -----

def test_verify_success_grants_download(client, db, fake_verify):
    r = client.post("/api/v1/gumroad/licenses/verify",
                    json={"product_permalink": "test-app", "license_key": "KEY-123"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] is True
    assert body["product_name"] == "Test App"
    assert body["download_token"]
    assert body["download_url"].endswith("/api/v1/gumroad/apk/download?token=" + body["download_token"])
    # Raw key must never appear in the response.
    assert "KEY-123" not in r.text

    grants = _grants(db)
    assert len(grants) == 1
    g = grants[0]
    assert g.status == "active"
    assert g.gumroad_purchase_id == "pur_123"
    # Key stored encrypted, never plaintext; hash stored for lookup.
    assert "KEY-123" not in (g.license_key_enc or "")
    assert decrypt_token(g.license_key_enc, g.key_version) == "KEY-123"
    from app.gumroad.licenses import license_key_hash
    assert g.license_key_hash == license_key_hash("KEY-123")
    # Buyer email stored masked only.
    assert g.buyer_email_masked != "buyer@example.com"
    assert "buyer@example.com" not in (g.buyer_email_masked or "")


def test_verify_invalid_license_denied(client, db, fake_verify):
    fake_verify["mode"] = "invalid"
    r = client.post("/api/v1/gumroad/licenses/verify",
                    json={"product_permalink": "test-app", "license_key": "BAD-KEY"})
    assert r.status_code == 403
    grants = _grants(db)
    assert len(grants) == 1 and grants[0].status == "invalid"


def test_verify_refunded_denied(client, db, fake_verify):
    fake_verify["mode"] = "refunded"
    r = client.post("/api/v1/gumroad/licenses/verify",
                    json={"product_permalink": "test-app", "license_key": "KEY-456"})
    assert r.status_code == 403
    assert "refunded" in r.json()["detail"]
    grants = _grants(db)
    assert grants[0].status == "refunded"


def test_verify_gumroad_down_fails_closed(client, db, fake_verify):
    fake_verify["mode"] = "transport_error"
    r = client.post("/api/v1/gumroad/licenses/verify",
                    json={"product_permalink": "test-app", "license_key": "KEY-789"})
    assert r.status_code == 503
    assert _grants(db) == []


def test_verify_rate_limited(client, db, fake_verify):
    for _ in range(20):
        r = client.post("/api/v1/gumroad/licenses/verify",
                        json={"product_permalink": "xx", "license_key": "key-1"})
        assert r.status_code in (200, 403)
    r = client.post("/api/v1/gumroad/licenses/verify",
                    json={"product_permalink": "xx", "license_key": "key-1"})
    assert r.status_code == 429


# ------------------------------------------------------------ download ----

def _verified_token(client, fake_verify, key="KEY-123"):
    r = client.post("/api/v1/gumroad/licenses/verify",
                    json={"product_permalink": "test-app", "license_key": key})
    assert r.status_code == 200, r.text
    return r.json()["download_token"]


def test_download_serves_apk_after_reverify(client, db, fake_verify, apk_file):
    token = _verified_token(client, fake_verify)
    r = client.get("/api/v1/gumroad/apk/download", params={"token": token})
    assert r.status_code == 200, r.text
    assert r.content == b"FAKE-APK-BYTES"
    assert "package-archive" in r.headers["content-type"]


def test_download_denied_after_refund(client, db, fake_verify, apk_file):
    token = _verified_token(client, fake_verify)
    fake_verify["mode"] = "refunded"  # refund happens between verify and download
    r = client.get("/api/v1/gumroad/apk/download", params={"token": token})
    assert r.status_code == 403
    assert "refunded" in r.json()["detail"]
    assert _grants(db)[0].status == "refunded"


def test_download_denied_when_gumroad_down(client, db, fake_verify, apk_file):
    token = _verified_token(client, fake_verify)
    fake_verify["mode"] = "transport_error"
    r = client.get("/api/v1/gumroad/apk/download", params={"token": token})
    assert r.status_code == 503  # fail closed


def test_download_bad_token(client, db):
    r = client.get("/api/v1/gumroad/apk/download", params={"token": "bogus-token-value"})
    assert r.status_code == 401


def test_download_token_wrong_type_rejected(client, db, auth_headers):
    # A login access token must not work as a download token.
    (headers, _user) = auth_headers()
    login_token = headers["Authorization"].split(" ", 1)[1]
    r = client.get("/api/v1/gumroad/apk/download", params={"token": login_token})
    assert r.status_code == 401


# ------------------------------------------------------------ oauth ------

def test_oauth_start_requires_client_id(client, db, auth_headers, account_factory):
    headers, user = auth_headers()
    acct = account_factory(user=user)
    settings = get_settings()
    old = settings.GUMROAD_CLIENT_ID
    settings.GUMROAD_CLIENT_ID = ""
    try:
        r = client.get(f"/api/v1/gumroad-accounts/{acct.id}/oauth/start", headers=headers)
    finally:
        settings.GUMROAD_CLIENT_ID = old
    assert r.status_code == 400


def test_oauth_start_returns_exact_redirect_uri(client, db, auth_headers, account_factory):
    headers, user = auth_headers()
    acct = account_factory(user=user)
    settings = get_settings()
    old = settings.GUMROAD_CLIENT_ID
    settings.GUMROAD_CLIENT_ID = "test-client-id"
    try:
        r = client.get(f"/api/v1/gumroad-accounts/{acct.id}/oauth/start", headers=headers)
    finally:
        settings.GUMROAD_CLIENT_ID = old
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["redirect_uri"].endswith("/api/v1/gumroad-accounts/oauth/callback")
    assert "redirect_uri=" in body["authorize_url"]
    assert "test-client-id" in body["authorize_url"]
    # No secret in the authorize URL.
    assert "secret" not in body["authorize_url"].lower()


def test_oauth_config_status(client, auth_headers):
    headers, _user = auth_headers()
    r = client.get("/api/v1/gumroad-accounts/oauth/config-status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["redirect_uri"].endswith("/api/v1/gumroad-accounts/oauth/callback")
    # Only boolean flags + public URLs — no secret values ever exposed.
    assert set(body.keys()) == {"client_id_configured", "client_secret_configured",
                                "redirect_uri", "authorize_url"}
    assert isinstance(body["client_secret_configured"], bool)


def test_app_credentials_wrong_password(client, tmp_path, monkeypatch):
    import app.api.license_access as la
    monkeypatch.setattr(la, "ENV_PATH", str(tmp_path / ".env"))
    r = client.post("/api/v1/gumroad-accounts/oauth/app-credentials", json={
        "email": "nobody@example.com", "password": "wrong",
        "client_id": "test-client-id", "client_secret": "test-client-secret",
    })
    assert r.status_code == 401
    assert not os.path.exists(str(tmp_path / ".env"))


def test_setup_page_renders(client):
    r = client.get("/gumroad-setup")
    assert r.status_code == 200
    assert "Gumroad Application Secret" in r.text
