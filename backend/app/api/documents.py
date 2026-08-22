import uuid
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import (
    AddUrlRequest,
    DocumentChunksResponse,
    DocumentDetailResponse,
    DocumentResponse,
)
from app.db import crud
from app.db.models import User
from app.db.session import get_db
from app.ingestion import delete_document, ingest_document, ingest_url
from app.ingestion.errors import (
    EmptyFileError,
    FileTooLargeError,
    InvalidURLError,
    UnsupportedFileTypeError,
    URLFetchError,
)
from app.storage import storage

router = APIRouter(prefix="/documents", tags=["documents"])

# Every type a browser can render natively opens inline (a new tab shows
# the PDF/image/text directly, not a save dialog). DOCX has no browser
# renderer, so it's served as an explicit attachment — a real download,
# not a broken "open" that silently downloads anyway. Own table instead
# of the OS mimetypes module: that module's coverage is inconsistent
# across platforms (e.g. it doesn't know .webp on some systems), and this
# app only ever needs to handle the extensions validate_upload accepts.
_INLINE_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_ATTACHMENT_CONTENT_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    content = await file.read()
    try:
        return ingest_document(db, file.filename or "unnamed", content, current_user.id)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except EmptyFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc


@router.post("/url", response_model=DocumentResponse, status_code=201)
def add_url(request: AddUrlRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return ingest_url(db, request.url, current_user.id)
    except InvalidURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except URLFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.list_documents(db, current_user.id)


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    document = crud.get_document(db, document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    document_data = DocumentResponse.model_validate(document).model_dump()
    return DocumentDetailResponse(
        **document_data,
        extracted_text=document.extracted_text,
        chunk_count=crud.count_chunks_for_document(db, document_id),
    )


@router.delete("/{document_id}", status_code=204)
def remove_document(
    document_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    document = crud.get_document(db, document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    delete_document(db, document)
    return Response(status_code=204)


@router.get("/{document_id}/file")
def get_document_file(
    document_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Serves the original uploaded file directly from disk so a source
    can be opened from its citation (e.g. a PDF at the cited page via a
    #page= fragment). Uses FileResponse rather than reading the file into
    memory: it streams from disk and natively supports HTTP Range
    requests, ETag, and Last-Modified, which some browsers' built-in PDF
    viewers rely on for progressive rendering — a plain in-memory Response
    always returns the whole body and ignores Range entirely. URL-sourced
    documents have no uploaded file — the frontend already has
    source_url for those. Never exposes the internal storage path or
    reveals whether one exists beyond a generic 404 — only document bytes
    keyed by document ID, addressed by original_filename in headers."""
    document = crud.get_document(db, document_id, current_user.id)
    if document is None or not document.storage_path:
        raise HTTPException(status_code=404, detail="No original file available for this document.")

    if not storage.exists(document.storage_path):
        # The DB row references a file that isn't on disk (deleted or
        # moved out-of-band). A clear 404 here, not a raw 500 from
        # FileResponse failing deep inside once it starts streaming, and
        # not a blank page with no explanation.
        raise HTTPException(status_code=404, detail="The original file for this document could not be found.")

    extension = PurePosixPath(document.original_filename).suffix.lower()
    if extension in _INLINE_CONTENT_TYPES:
        content_type = _INLINE_CONTENT_TYPES[extension]
        disposition = "inline"
    elif extension in _ATTACHMENT_CONTENT_TYPES:
        content_type = _ATTACHMENT_CONTENT_TYPES[extension]
        disposition = "attachment"
    else:
        content_type = "application/octet-stream"
        disposition = "attachment"

    # LocalFileStorage returns None here (nothing to redirect to — stream
    # from disk instead). R2Storage returns a short-lived presigned URL, so
    # the browser downloads/views the file directly from R2 instead of
    # proxying the bytes through this API.
    redirect_url = storage.serving_url(
        document.storage_path,
        filename=document.original_filename,
        content_type=content_type,
        disposition=disposition,
    )
    if redirect_url is not None:
        return RedirectResponse(redirect_url, status_code=302)

    return FileResponse(
        path=storage.path(document.storage_path),
        media_type=content_type,
        filename=document.original_filename,
        content_disposition_type=disposition,
    )


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse, tags=["debug"])
def get_document_chunks(
    document_id: uuid.UUID,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Debugging aid to inspect a document's stored chunks. Not the future
    retrieval API — retrieval will search across documents by relevance,
    not list one document's chunks in order."""
    document = crud.get_document(db, document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    limit = max(1, min(limit, 200))
    return DocumentChunksResponse(
        document_id=document_id,
        total_chunks=crud.count_chunks_for_document(db, document_id),
        chunks=crud.get_chunks_for_document(db, document_id, limit=limit),
    )
