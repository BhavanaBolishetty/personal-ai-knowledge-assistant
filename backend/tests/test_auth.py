import io

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app

client = TestClient(app)


@pytest.fixture
def real_auth():
    """Temporarily disables the default-test-user override (see
    conftest.py) so a test can exercise the real get_current_user flow
    against a real bearer token, instead of implicitly running as the
    shared default test user."""
    original = app.dependency_overrides.pop(get_current_user, None)
    yield
    if original is not None:
        app.dependency_overrides[get_current_user] = original


def _signup(email, password="a-real-password"):
    return client.post("/auth/signup", json={"email": email, "password": password})


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_signup_creates_account_and_returns_token(real_auth):
    response = _signup("new-user@example.com")
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "new-user@example.com"
    assert "id" in body["user"]
    assert body["token"]
    # The hashed password must never be echoed back in any response.
    assert "password" not in body["user"]
    assert "hashed_password" not in body["user"]


def test_signup_rejects_duplicate_email(real_auth):
    _signup("dup@example.com")
    response = _signup("dup@example.com")
    assert response.status_code == 409


def test_signup_rejects_short_password(real_auth):
    response = client.post("/auth/signup", json={"email": "short@example.com", "password": "short"})
    assert response.status_code == 422


def test_signup_rejects_invalid_email(real_auth):
    response = client.post("/auth/signup", json={"email": "not-an-email", "password": "a-real-password"})
    assert response.status_code == 422


def test_login_with_correct_credentials_succeeds(real_auth):
    _signup("login-ok@example.com", "correct-password")
    response = client.post("/auth/login", json={"email": "login-ok@example.com", "password": "correct-password"})
    assert response.status_code == 200
    assert response.json()["token"]


def test_login_with_wrong_password_fails(real_auth):
    _signup("login-bad@example.com", "correct-password")
    response = client.post("/auth/login", json={"email": "login-bad@example.com", "password": "wrong-password"})
    assert response.status_code == 401


def test_login_with_unknown_email_fails(real_auth):
    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(real_auth):
    token = _signup("me-check@example.com").json()["token"]
    response = client.get("/auth/me", headers=_auth_headers(token))
    assert response.status_code == 200
    assert response.json()["email"] == "me-check@example.com"


def test_me_rejects_missing_token(real_auth):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_rejects_invalid_token(real_auth):
    response = client.get("/auth/me", headers=_auth_headers("not-a-real-token"))
    assert response.status_code == 401


def test_documents_are_isolated_between_users(real_auth):
    token_a = _signup("doc-owner-a@example.com").json()["token"]
    token_b = _signup("doc-owner-b@example.com").json()["token"]

    upload = client.post(
        "/documents",
        files={"file": ("private-to-a.txt", io.BytesIO(b"Only user A should ever see this."), "text/plain")},
        headers=_auth_headers(token_a),
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]

    # User A can see and fetch their own document.
    assert client.get("/documents", headers=_auth_headers(token_a)).json()
    assert client.get(f"/documents/{document_id}", headers=_auth_headers(token_a)).status_code == 200

    # User B sees an empty list and gets a clean 404 for the same id — not
    # a 403 (which would confirm the document exists under someone else).
    assert client.get("/documents", headers=_auth_headers(token_b)).json() == []
    assert client.get(f"/documents/{document_id}", headers=_auth_headers(token_b)).status_code == 404
    assert client.delete(f"/documents/{document_id}", headers=_auth_headers(token_b)).status_code == 404

    # User A's document must still exist after B's failed delete attempt.
    assert client.get(f"/documents/{document_id}", headers=_auth_headers(token_a)).status_code == 200


def test_conversations_are_isolated_between_users(real_auth):
    token_a = _signup("conv-owner-a@example.com").json()["token"]
    token_b = _signup("conv-owner-b@example.com").json()["token"]

    created = client.post("/conversations", headers=_auth_headers(token_a))
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    assert client.get(f"/conversations/{conversation_id}", headers=_auth_headers(token_a)).status_code == 200
    assert client.get("/conversations", headers=_auth_headers(token_b)).json() == []
    assert client.get(f"/conversations/{conversation_id}", headers=_auth_headers(token_b)).status_code == 404
    assert client.delete(f"/conversations/{conversation_id}", headers=_auth_headers(token_b)).status_code == 404


def test_search_does_not_return_another_users_documents(real_auth):
    token_a = _signup("search-owner-a@example.com").json()["token"]
    token_b = _signup("search-owner-b@example.com").json()["token"]

    client.post(
        "/documents",
        files={
            "file": (
                "a-secret-recipe.txt",
                io.BytesIO(b"This document about sourdough starters belongs only to user A."),
                "text/plain",
            )
        },
        headers=_auth_headers(token_a),
    )

    response = client.post(
        "/search", json={"query": "sourdough starters"}, headers=_auth_headers(token_b)
    )
    assert response.status_code == 200
    assert response.json()["results"] == []
