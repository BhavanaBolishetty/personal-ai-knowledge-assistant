import pytest
from fastapi.testclient import TestClient

from app.ingestion.errors import InvalidURLError
from app.ingestion.url_fetcher import _validate_url
from app.main import app

client = TestClient(app)


def test_rejects_localhost():
    with pytest.raises(InvalidURLError):
        _validate_url("http://localhost/page")


def test_rejects_loopback_ip():
    with pytest.raises(InvalidURLError):
        _validate_url("http://127.0.0.1/page")


def test_rejects_private_ip_range():
    with pytest.raises(InvalidURLError):
        _validate_url("http://192.168.1.1/page")


def test_rejects_link_local_address():
    with pytest.raises(InvalidURLError):
        _validate_url("http://169.254.169.254/latest/meta-data/")


def test_rejects_non_http_scheme():
    with pytest.raises(InvalidURLError):
        _validate_url("ftp://example.com/file")


def test_rejects_file_scheme():
    with pytest.raises(InvalidURLError):
        _validate_url("file:///etc/passwd")


def test_add_url_endpoint_rejects_private_address():
    response = client.post("/documents/url", json={"url": "http://127.0.0.1:8000/"})
    assert response.status_code == 400


def test_add_url_endpoint_success(monkeypatch):
    import app.ingestion.service as service_module

    fake_html = (
        "<html><head><title>Test Article</title></head><body><article>"
        "<p>Distinct URL ingestion test content about caching strategies "
        "and distributed systems that trafilatura should extract cleanly.</p>"
        "</article></body></html>"
    )
    monkeypatch.setattr(service_module, "fetch_url", lambda url: (fake_html.encode(), "text/html"))

    response = client.post("/documents/url", json={"url": "https://example.com/blog/article"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["source_url"] == "https://example.com/blog/article"
    assert body["original_filename"] == "Test Article"

    detail = client.get(f"/documents/{body['id']}").json()
    assert "caching strategies" in detail["extracted_text"]


def test_add_url_endpoint_handles_fetch_failure_cleanly(monkeypatch):
    import app.ingestion.service as service_module
    from app.ingestion.errors import URLFetchError

    def _broken_fetch(url):
        raise URLFetchError("Could not reach that webpage.")

    monkeypatch.setattr(service_module, "fetch_url", _broken_fetch)

    response = client.post("/documents/url", json={"url": "https://example.com/unreachable"})
    assert response.status_code == 502
    assert "Could not reach" in response.json()["detail"]


def test_add_url_endpoint_handles_blocked_page_cleanly(monkeypatch):
    # Simulates a page that exists but can't be legitimately accessed
    # (auth wall, robots restriction, etc.) — no bypass attempted, just a
    # clean user-facing failure.
    import app.ingestion.service as service_module
    from app.ingestion.errors import URLFetchError

    def _blocked_fetch(url):
        raise URLFetchError("The page could not be accessed (HTTP 999).")

    monkeypatch.setattr(service_module, "fetch_url", _blocked_fetch)

    response = client.post("/documents/url", json={"url": "https://www.linkedin.com/posts/example"})
    assert response.status_code == 502


def test_fetch_url_follows_redirect_and_resolves_relative_location(monkeypatch):
    # Every other URL test mocks fetch_url() itself, so the redirect-
    # following loop inside it was never actually exercised — that's how a
    # real bug (httpx.URL has no .human_repr() in the installed httpx
    # version) shipped unnoticed and turned a login-redirect page like
    # LinkedIn into a raw 500 instead of a clean error. This test drives
    # fetch_url() itself through a redirect with a relative Location header.
    import app.ingestion.url_fetcher as url_fetcher_module

    monkeypatch.setattr(
        url_fetcher_module.socket,
        "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("93.184.216.34", 0))],
    )

    class FakeResponse:
        def __init__(self, *, is_redirect, status_code, headers, body=b""):
            self.is_redirect = is_redirect
            self.status_code = status_code
            self.headers = headers
            self._body = body

        def iter_bytes(self):
            yield self._body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    responses = [
        FakeResponse(is_redirect=True, status_code=302, headers={"location": "/new-location"}),
        FakeResponse(
            is_redirect=False, status_code=200, headers={"content-type": "text/html"}, body=b"<html>ok</html>"
        ),
    ]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def stream(self, method, url, headers=None):
            return responses.pop(0)

    monkeypatch.setattr(url_fetcher_module.httpx, "Client", FakeClient)

    from app.ingestion.url_fetcher import fetch_url

    content, content_type = fetch_url("https://example.com/old-location")
    assert content == b"<html>ok</html>"
    assert content_type == "text/html"


def test_extract_pages_strips_boilerplate_and_keeps_article_text():
    from app.extraction.url import extract_pages

    html = """
    <html><head><title>My Article</title></head>
    <body>
    <nav>Home | About | Contact</nav>
    <article><h1>My Article</h1><p>This is the real article content about
    distributed systems and caching strategies that should be extracted.</p></article>
    <footer>Copyright 2026 Example Corp</footer>
    </body></html>
    """
    pages = extract_pages(html)
    assert len(pages) == 1
    assert "distributed systems" in pages[0]
    assert "Copyright" not in pages[0]
    assert "Home | About | Contact" not in pages[0]
