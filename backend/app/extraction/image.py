from app.extraction.errors import ExtractionError
from app.llm import LLMError, describe_image

_DESCRIBE_PROMPT = (
    "Describe this image factually and in detail for someone who cannot see it. "
    "Transcribe any visible text verbatim. If it's a diagram, chart, or architecture "
    "drawing, describe the components and how they connect. Do not invent details "
    "that aren't visibly present in the image."
)


def extract_pages(content: bytes, mime_type: str) -> list[str]:
    """Uses Gemini's vision capability (via the existing LLM abstraction —
    no separate OCR/vision stack) to turn an image into text: a factual
    description plus verbatim transcription of any visible text. An image
    has no page concept, so this returns a single "page". The model is
    explicitly instructed not to invent content that isn't visible.
    """
    try:
        description = describe_image(image_bytes=content, mime_type=mime_type, prompt=_DESCRIBE_PROMPT)
    except LLMError as exc:
        raise ExtractionError(f"Could not analyze image: {exc}") from exc

    return [description]
