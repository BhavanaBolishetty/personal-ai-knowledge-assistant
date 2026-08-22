"""Exercises the real rate limiters (see app/core/rate_limit.py).

Every other test file runs against the no-op override installed by
conftest.py's _default_rate_limit_override — this file is the one place
that pops it (mirrors test_auth.py's real_auth fixture for
get_current_user) to confirm the real limiting behavior actually works.
"""
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.rate_limit import limit_ask, limit_login, limit_signup
from app.main import app

client = TestClient(app)


@pytest.fixture
def real_rate_limits():
    originals = {}
    for dependency in (limit_login, limit_signup, limit_ask, get_current_user):
        originals[dependency] = app.dependency_overrides.pop(dependency, None)
    yield
    for dependency, override in originals.items():
        if override is not None:
            app.dependency_overrides[dependency] = override


def _forwarded_for(ip):
    return {"X-Forwarded-For": ip}


def test_login_is_rate_limited_per_ip(real_rate_limits):
    headers = _forwarded_for("203.0.113.10")
    for _ in range(10):
        client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"}, headers=headers)

    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"}, headers=headers)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_login_rate_limit_is_scoped_per_ip(real_rate_limits):
    exhausted_ip = _forwarded_for("203.0.113.11")
    fresh_ip = _forwarded_for("203.0.113.12")
    for _ in range(10):
        client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"}, headers=exhausted_ip)

    # A different source IP has its own, untouched budget.
    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"}, headers=fresh_ip)
    assert response.status_code == 401


def test_signup_is_rate_limited_per_ip(real_rate_limits):
    headers = _forwarded_for("203.0.113.20")
    for i in range(5):
        client.post(
            "/auth/signup",
            json={"email": f"rate-limit-signup-{i}@example.com", "password": "A-real-Password1!"},
            headers=headers,
        )

    response = client.post(
        "/auth/signup",
        json={"email": "rate-limit-signup-overflow@example.com", "password": "A-real-Password1!"},
        headers=headers,
    )
    assert response.status_code == 429


def test_ask_is_rate_limited_per_user(real_rate_limits):
    # A random query against a brand-new account with no uploaded
    # documents retrieves zero chunks and short-circuits to the
    # no-context answer (see app/synthesis/service.py) without ever
    # calling Gemini — this test exercises the /ask rate limit itself,
    # not the answer-generation pipeline, so it stays fast and free of
    # any live API call.
    signup = client.post(
        "/auth/signup",
        json={"email": "rate-limit-asker@example.com", "password": "A-real-Password1!"},
        headers=_forwarded_for("203.0.113.30"),
    )
    token = signup.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(30):
        client.post("/ask", json={"query": "rate limit probe query with no matching documents"}, headers=headers)

    response = client.post(
        "/ask", json={"query": "rate limit probe query with no matching documents"}, headers=headers
    )
    assert response.status_code == 429


def test_ask_rate_limit_is_scoped_per_user(real_rate_limits):
    exhausted_signup = client.post(
        "/auth/signup",
        json={"email": "rate-limit-asker-a@example.com", "password": "A-real-Password1!"},
        headers=_forwarded_for("203.0.113.31"),
    )
    exhausted_headers = {"Authorization": f"Bearer {exhausted_signup.json()['token']}"}
    for _ in range(30):
        client.post("/ask", json={"query": "probe"}, headers=exhausted_headers)

    fresh_signup = client.post(
        "/auth/signup",
        json={"email": "rate-limit-asker-b@example.com", "password": "A-real-Password1!"},
        headers=_forwarded_for("203.0.113.32"),
    )
    fresh_headers = {"Authorization": f"Bearer {fresh_signup.json()['token']}"}

    # A different user has their own, untouched budget even though both
    # requests arrive from wherever the test client's default IP is.
    response = client.post("/ask", json={"query": "probe"}, headers=fresh_headers)
    assert response.status_code == 200
