"""Gumroad API error types. Mapped from HTTP responses by the client."""
from __future__ import annotations


class GumroadError(Exception):
    """Base error. Never carries tokens or raw emails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GumroadAuthError(GumroadError):
    """401 — token invalid/revoked. Caller must mark the account needs_reconnect."""


class GumroadRateLimitError(GumroadError):
    """429 that persisted past retries."""


class GumroadNotFoundError(GumroadError):
    """404."""


class GumroadServerError(GumroadError):
    """5xx that persisted past retries."""


class GumroadClientError(GumroadError):
    """Other 4xx."""
