import trafilatura

from app.extraction.errors import ExtractionError


def extract_pages(html: str) -> list[str]:
    """Extracts the main readable content from an HTML page — article
    body, not navigation/ads/boilerplate. A web page has no page-number
    concept, so this returns a single "page".
    """
    text = trafilatura.extract(html, include_comments=False, include_tables=True)
    if not text or not text.strip():
        raise ExtractionError("Could not extract readable article content from this page.")
    return [text.strip()]


def extract_title(html: str) -> str | None:
    metadata = trafilatura.extract_metadata(html)
    title = getattr(metadata, "title", None) if metadata else None
    return title.strip() if title and title.strip() else None
