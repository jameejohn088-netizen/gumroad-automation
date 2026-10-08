"""httpx client factory for outgoing Gumroad API calls in this runtime.

Why not plain httpx.Client():
- trust_env=True crashes: this httpx version cannot parse the IPv6 entries
  in no_proxy (e.g. all://[::1]) -> "Invalid port: ':1]'".
- Outgoing traffic must go through the egress proxy (https_proxy env), whose
  TLS interception needs its CA bundle (SSL_CERT_FILE env).

So: trust_env=False, proxy taken explicitly from the env, verify pointed at
the CA bundle when present. Pass transport=... in tests to bypass all of it.
"""
from __future__ import annotations

import os

import httpx

TIMEOUT = 30.0


def _proxy_url() -> str | None:
    return (
        os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("HTTP_PROXY")
    )


def _verify() -> str | bool:
    ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if ca and os.path.isfile(ca):
        return ca
    return True


def gumroad_http_client(timeout: float = TIMEOUT,
                        transport: httpx.BaseTransport | None = None,
                        **kwargs) -> httpx.Client:
    """Extra kwargs are passed straight to httpx.Client (e.g. base_url)."""
    if transport is not None:
        return httpx.Client(timeout=timeout, transport=transport, **kwargs)
    all_kwargs: dict = {"timeout": timeout, "trust_env": False, "verify": _verify()}
    proxy = _proxy_url()
    if proxy:
        all_kwargs["proxy"] = proxy
    all_kwargs.update(kwargs)
    return httpx.Client(**all_kwargs)
