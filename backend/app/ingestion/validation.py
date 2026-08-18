from pathlib import PurePosixPath

from app.core.config import settings
from app.db.models import SourceType
from app.ingestion.errors import EmptyFileError, FileTooLargeError, UnsupportedFileTypeError

EXTENSION_TO_SOURCE_TYPE = {
    ".pdf": SourceType.pdf,
    ".txt": SourceType.text,
    ".md": SourceType.markdown,
    ".markdown": SourceType.markdown,
    ".docx": SourceType.docx,
    ".png": SourceType.image,
    ".jpg": SourceType.image,
    ".jpeg": SourceType.image,
    ".webp": SourceType.image,
}

# Extension -> MIME type, used only for image uploads (to tell Gemini's
# vision API what format the bytes are in). Derived from the extension we
# already validated, not trusted from the client's Content-Type header.
IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def validate_upload(original_filename: str, content: bytes) -> tuple[str, SourceType]:
    # Only the extension is read from the filename, and only as text (via
    # PurePosixPath, never touching the real filesystem) — it is never used
    # to build a path on disk.
    extension = PurePosixPath(original_filename or "").suffix.lower()
    source_type = EXTENSION_TO_SOURCE_TYPE.get(extension)
    if source_type is None:
        allowed = ", ".join(sorted(EXTENSION_TO_SOURCE_TYPE))
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{extension or 'unknown'}'. Allowed types: {allowed}."
        )

    if len(content) == 0:
        raise EmptyFileError("Uploaded file is empty.")

    if len(content) > settings.max_upload_size_bytes:
        max_mb = settings.max_upload_size_bytes / (1024 * 1024)
        raise FileTooLargeError(f"File exceeds the maximum allowed size of {max_mb:.0f} MB.")

    return extension, source_type
