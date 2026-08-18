import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.ingestion.errors import InvalidURLError, URLFetchError

ALLOWED_SCHEMES = {"http", "https"}


def _is_unsafe_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _validate_url(url: str) -> str:
    """Validates scheme and resolves the hostname to reject
    private/loopback/link-local/reserved targets — the SSRF defense.
    Raises InvalidURLError (not URLFetchError) since this is a rejection
    based on the URL itself, before any request is attempted.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise InvalidURLError("Only http and https URLs are supported.")

    hostname = parsed.hostname
    if not hostname:
        raise InvalidURLError("URL is missing a hostname.")
    if hostname.lower() == "localhost":
        raise InvalidURLError("Local addresses cannot be fetched.")

    try:
        resolved = {info[4][0] for info in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise InvalidURLError("Could not resolve this URL's hostname.") from exc

    if not resolved:
        raise InvalidURLError("Could not resolve this URL's hostname.")

    for ip in resolved:
        if _is_unsafe_ip(ip):
            raise InvalidURLError(
                "This URL resolves to a private or internal address and cannot be fetched."
            )

    return url


def fetch_url(url: str) -> tuple[bytes, str]:
    """Fetches a URL safely: validates the URL (and every redirect hop) is
    not a private/internal address, enforces a timeout and a maximum
    response size, and never follows more than max_url_redirects hops.
    Returns (content_bytes, content_type).
    """
    current_url = _validate_url(url)

    with httpx.Client(follow_redirects=False, timeout=settings.url_fetch_timeout_seconds) as client:
        for _ in range(settings.max_url_redirects + 1):
            try:
                with client.stream("GET", current_url, headers={"User-Agent": "PersonalAIKnowledgeAssistant/1.0"}) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise URLFetchError("The page redirected without a destination.")
                        current_url = _validate_url(str(httpx.URL(current_url).join(location)))
                        continue

                    if response.status_code >= 400:
                        raise URLFetchError(
                            f"The page could not be accessed (HTTP {response.status_code})."
                        )

                    content_type = response.headers.get("content-type", "").split(";")[0].strip()

                    chunks = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > settings.max_url_response_bytes:
                            raise URLFetchError("The page is too large to process.")
                        chunks.append(chunk)

                    return b"".join(chunks), content_type
            except httpx.TimeoutException as exc:
                raise URLFetchError("The page took too long to respond.") from exc
            except httpx.RequestError as exc:
                raise URLFetchError("Could not reach that webpage.") from exc

        raise URLFetchError("Too many redirects.")
