"""In-memory sliding-window rate limiter with lockout support.

Process-local by design ($0 mode). For multi-worker production deployments,
replace the store with Redis — the interface stays the same.
"""
import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self):
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            dq = self._hits.setdefault(key, deque())
            while dq and dq[0] <= now - window_seconds:
                dq.popleft()
            if len(dq) >= limit:
                retry_after = int(dq[0] + window_seconds - now) + 1
                return False, max(retry_after, 1)
            dq.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


rate_limiter = RateLimiter()
