"""GumroadClient tests with httpx.MockTransport: pagination, 429/Retry-After,
401 mapping, and log redaction. No real network."""
import logging

import httpx
import pytest

from app.gumroad.client import GumroadClient
from app.gumroad.exceptions import GumroadAuthError, GumroadRateLimitError

# Clearly-labeled fixture payloads (tests only).
FIXTURE_PAGE_1 = {"success": True, "products": [{"id": "p1", "name": "One"}],
                  "next_page_key": "key-2"}
FIXTURE_PAGE_2 = {"success": True, "products": [{"id": "p2", "name": "Two"}]}


def _client(handler, account_id="acct-test"):
    return GumroadClient(access_token="super-secret-token", account_id=account_id,
                         transport=httpx.MockTransport(handler), min_interval=0)


def test_cursor_pagination_follows_page_key():
    seen = []

    def handler(request):
        seen.append(request.url.params.get("page_key"))
        if request.url.params.get("page_key") == "key-2":
            return httpx.Response(200, json=FIXTURE_PAGE_2)
        return httpx.Response(200, json=FIXTURE_PAGE_1)

    items = list(_client(handler).list_products())
    assert [i["id"] for i in items] == ["p1", "p2"]
    assert seen[0] is None and seen[1] == "key-2"


def test_429_retry_after_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"success": True, "user": {"name": "S"}})

    body = _client(handler).get_user()
    assert body["success"] is True
    assert calls["n"] == 2


def test_429_persists_raises_rate_limit_error():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "0"})

    with pytest.raises(GumroadRateLimitError):
        _client(handler).get_user()


def test_401_maps_to_auth_error():
    def handler(request):
        return httpx.Response(401, json={"success": False, "message": "bad token"})

    with pytest.raises(GumroadAuthError):
        _client(handler).get_user()


def test_logs_redact_token_and_mask_email(caplog):
    def handler(request):
        return httpx.Response(200, json={"success": True, "sales": []})

    with caplog.at_level(logging.INFO, logger="gumroad"):
        list(_client(handler).list_sales(email="alice@example.com"))
    text = caplog.text
    assert "super-secret-token" not in text  # token never logged
    assert "alice@example.com" not in text    # email masked
    assert "al***@example.com" in text       # masked form present


def test_per_account_limiters_are_independent():
    # Two accounts get separate limiter instances (no cross-account throttling).
    from app.gumroad.client import _limiters
    c1 = _client(lambda r: httpx.Response(200, json={}), account_id="a1")
    c2 = _client(lambda r: httpx.Response(200, json={}), account_id="a2")
    assert c1._limiter is not c2._limiter
    assert _limiters["a1"] is not _limiters["a2"]
