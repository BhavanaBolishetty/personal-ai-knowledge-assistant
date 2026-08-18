from app.extraction.errors import ExtractionError


def extract_text(content: bytes) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError("File is not valid UTF-8 text.") from exc

    text = text.strip()
    if not text:
        raise ExtractionError("Text file is empty after decoding.")
    return text
