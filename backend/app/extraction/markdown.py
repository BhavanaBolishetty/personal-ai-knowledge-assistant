from app.extraction.errors import ExtractionError


def extract_text(content: bytes) -> str:
    # Markdown source is kept as-is (not stripped of syntax) because the
    # structure (headings, lists) is useful signal for chunking later.
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError("File is not valid UTF-8 text.") from exc

    text = text.strip()
    if not text:
        raise ExtractionError("Markdown file is empty after decoding.")
    return text
