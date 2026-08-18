import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.chunking import chunk_text
from app.core.config import settings
from app.db import crud
from app.db.models import Document, SourceType
from app.embeddings import embed_texts
from app.extraction import ExtractionError, extract_pages
from app.extraction.url import extract_title
from app.ingestion.url_fetcher import fetch_url
from app.ingestion.validation import IMAGE_MIME_TYPES, validate_upload
from app.storage import storage

# Only PDF has a real, extraction-verified page concept today (see
# app/extraction/pdf.py). Every other source type's chunks get
# page_number=None rather than an invented page number.
PAGINATED_SOURCE_TYPES = {SourceType.pdf}


def delete_document(db: Session, document: Document) -> None:
    """Removes a document's uploaded file (if any — URL-sourced documents
    have none) before deleting its database row, which cascades to its
    chunks/embeddings (see crud.delete_document)."""
    if document.storage_path:
        storage.delete(document.storage_path)
    crud.delete_document(db, document)


def ingest_document(db: Session, original_filename: str, content: bytes) -> Document:
    extension, source_type = validate_upload(original_filename, content)

    document_id = uuid.uuid4()
    storage_path = storage.save(f"{document_id}{extension}", content)

    document = crud.create_document(
        db,
        id=document_id,
        original_filename=original_filename,
        source_type=source_type,
        file_size_bytes=len(content),
        storage_path=storage_path,
    )

    extract_kwargs = {}
    if source_type == SourceType.image:
        extract_kwargs["mime_type"] = IMAGE_MIME_TYPES[extension]

    return _process_document(db, document, source_type, content, extract_kwargs)


def ingest_url(db: Session, url: str) -> Document:
    content, _content_type = fetch_url(url)  # raises InvalidURLError/URLFetchError

    html = content.decode("utf-8", errors="replace")
    title = extract_title(html)
    domain = urlparse(url).netloc

    document = crud.create_document(
        db,
        id=uuid.uuid4(),
        original_filename=title or url,
        source_type=SourceType.url,
        file_size_bytes=len(content),
        doc_metadata={
            "source_url": url,
            "title": title,
            "domain": domain,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return _process_document(db, document, SourceType.url, content, {})


def _process_document(
    db: Session,
    document: Document,
    source_type: SourceType,
    content: bytes,
    extract_kwargs: dict,
) -> Document:
    try:
        pages = extract_pages(source_type, content, **extract_kwargs)
    except ExtractionError as exc:
        return crud.mark_document_failed(db, document, error_message=str(exc))

    extracted_text = "\n\n".join(page for page in pages if page.strip())
    is_paginated = source_type in PAGINATED_SOURCE_TYPES

    try:
        chunk_records: list[tuple[str, int | None]] = []
        for page_number, page_text in enumerate(pages, start=1):
            if not page_text.strip():
                continue
            for chunk in chunk_text(
                page_text,
                chunk_size=settings.chunk_size_chars,
                chunk_overlap=settings.chunk_overlap_chars,
            ):
                chunk_records.append((chunk, page_number if is_paginated else None))
        chunks = crud.create_chunks(db, document.id, chunk_records)
    except Exception as exc:
        # Whether chunking raised (no DB touched yet) or the chunk commit
        # itself failed partway through, roll back before writing the
        # failure state so no partial chunk set is ever left behind.
        db.rollback()
        return crud.mark_document_failed(db, document, error_message=f"Chunking failed: {exc}")

    try:
        embeddings = embed_texts([text for text, _ in chunk_records])
        crud.store_chunk_embeddings(db, chunks, embeddings)
    except Exception as exc:
        # The chunk rows are already committed and deliberately left in
        # place (real, successful work) — but the document stays "failed",
        # so nothing treats these embedding-less chunks as search-ready.
        db.rollback()
        return crud.mark_document_failed(db, document, error_message=f"Embedding failed: {exc}")

    return crud.mark_document_completed(db, document, extracted_text=extracted_text)
