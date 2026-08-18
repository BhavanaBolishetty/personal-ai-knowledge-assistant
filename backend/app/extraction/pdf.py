import io

from pypdf import PdfReader

from app.extraction.errors import ExtractionError


def extract_pages(content: bytes) -> list[str]:
    """Returns one string per PDF page (1-indexed by position), so callers
    can chunk per page and preserve real page numbers on each chunk."""
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise ExtractionError(f"Could not read PDF file: {exc}") from exc

    if not any(pages):
        raise ExtractionError("No extractable text found in PDF.")

    return pages
