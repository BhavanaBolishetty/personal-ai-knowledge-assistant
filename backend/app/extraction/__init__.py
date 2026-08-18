from app.db.models import SourceType
from app.extraction import docx, image, markdown, pdf, text, url
from app.extraction.errors import ExtractionError

_TEXT_EXTRACTORS = {
    SourceType.text: text.extract_text,
    SourceType.markdown: markdown.extract_text,
}


def extract_pages(source_type: SourceType, content: bytes, **kwargs) -> list[str]:
    """Returns one string per logical "page". Only PDF currently has a
    real page concept; every other source type returns a single-element
    list, and chunks derived from it get page_number=None rather than an
    invented page number.
    """
    if source_type == SourceType.pdf:
        return pdf.extract_pages(content)
    if source_type == SourceType.docx:
        return docx.extract_pages(content)
    if source_type == SourceType.url:
        html = content.decode("utf-8", errors="replace")
        return url.extract_pages(html)
    if source_type == SourceType.image:
        return image.extract_pages(content, mime_type=kwargs["mime_type"])
    return [_TEXT_EXTRACTORS[source_type](content)]


__all__ = ["extract_pages", "ExtractionError"]
