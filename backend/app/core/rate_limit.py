"""Minimal in-process rate limiting for endpoints that are either
brute-forceable (login/signup, no auth yet to key off) or cost-bearing
(ask, one Gemini call per request).

In-memory, not Redis-backed: Render's free tier runs this service as one
instance (no horizontal scaling), so a single process's memory is a
complete and consistent view of recent request activity — a shared store
would be solving a problem this deployment doesn't have. If the app ever
scales to multiple instances, this stops being correct and would need to
move to a shared store at that point.
"""
import threading
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request

from app.api.deps import get_current_user
from app.db.models import User


class RateLimiter:
    """Fixed-window limiter: at most max_requests per key within any
    window_seconds-long window, keyed by whatever the caller passes in
    (a client IP or a user id)."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            # Dropping expired timestamps here (not in a separate cleanup
            # task) means a key that's gone quiet naturally shrinks back
            # to nothing on its next request — no unbounded growth from
            # one-off or abandoned keys.
            fresh = [hit for hit in self._hits[key] if hit > cutoff]
            if len(fresh) >= self.max_requests:
                self._hits[key] = fresh
                retry_after = fresh[0] + self.window_seconds - now
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again shortly.",
                    headers={"Retry-After": str(max(1, int(retry_after)))},
                )
            fresh.append(now)
            self._hits[key] = fresh


def _client_ip(request: Request) -> str:
    # Render terminates TLS and proxies requests to this container, so
    # request.client.host would be Render's internal proxy address, not
    # the real visitor — the actual client IP is the first entry of
    # X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# 10 attempts / 5 minutes per IP: generous for a real user who mistypes a
# password a few times, tight enough to make credential-stuffing
# impractical.
_login_limiter = RateLimiter(max_requests=10, window_seconds=300)
# 5 accounts / hour per IP: a real person signs up once; this just caps
# automated mass account creation from a single source.
_signup_limiter = RateLimiter(max_requests=5, window_seconds=3600)
# 30 questions / 5 minutes per user: well above any real chat session,
# but caps how fast a single account (or a leaked token) can burn through
# Gemini's free-tier quota.
_ask_limiter = RateLimiter(max_requests=30, window_seconds=300)


def limit_login(request: Request) -> None:
    _login_limiter.check(_client_ip(request))


def limit_signup(request: Request) -> None:
    _signup_limiter.check(_client_ip(request))


def limit_ask(current_user: User = Depends(get_current_user)) -> None:
    _ask_limiter.check(str(current_user.id))
