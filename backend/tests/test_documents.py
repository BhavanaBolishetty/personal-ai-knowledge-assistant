import io
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.pdf_fixtures import make_minimal_pdf_bytes

client = TestClient(app)


def upload(filename, content, content_type="application/octet-stream"):
    return client.post(
        "/documents",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


def test_upload_txt_succeeds_and_extracts_text():
    response = upload("notes.txt", b"Hello from a text file.", "text/plain")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["source_type"] == "text"

    detail = client.get(f"/documents/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["extracted_text"] == "Hello from a text file."


def test_upload_markdown_succeeds_and_extracts_text():
    content = b"# Heading\n\nSome markdown content."
    response = upload("notes.md", content, "text/markdown")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["source_type"] == "markdown"

    detail = client.get(f"/documents/{body['id']}")
    assert "Some markdown content." in detail.json()["extracted_text"]


def test_upload_pdf_succeeds_and_extracts_text():
    pdf_bytes = make_minimal_pdf_bytes("Hello World")
    response = upload("report.pdf", pdf_bytes, "application/pdf")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["source_type"] == "pdf"

    detail = client.get(f"/documents/{body['id']}")
    assert "Hello World" in detail.json()["extracted_text"]


def test_upload_unsupported_file_type_is_rejected():
    response = upload("archive.zip", b"not really a zip", "application/zip")
    assert response.status_code == 415
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_empty_file_is_rejected():
    response = upload("empty.txt", b"", "text/plain")
    assert response.status_code == 400


def test_upload_invalid_pdf_marks_document_failed():
    response = upload("broken.pdf", b"this is not a real pdf", "application/pdf")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"]


def test_upload_pdf_with_no_extractable_text_marks_document_failed():
    pdf_bytes = make_minimal_pdf_bytes("")
    response = upload("blank.pdf", pdf_bytes, "application/pdf")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert "No extractable text" in body["error_message"]


def test_upload_oversized_file_is_rejected(monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "max_upload_size_bytes", 10)
    response = upload("too_big.txt", b"this is definitely more than ten bytes", "text/plain")
    assert response.status_code == 413


def test_duplicate_filenames_are_handled_independently():
    first = upload("duplicate.txt", b"first version", "text/plain")
    second = upload("duplicate.txt", b"second version", "text/plain")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    first_detail = client.get(f"/documents/{first.json()['id']}").json()
    second_detail = client.get(f"/documents/{second.json()['id']}").json()
    assert first_detail["extracted_text"] == "first version"
    assert second_detail["extracted_text"] == "second version"


def test_get_nonexistent_document_returns_404():
    response = client.get("/documents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_list_documents_returns_array():
    response = client.get("/documents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_delete_document_removes_it_its_chunks_and_its_file():
    from app.db import crud
    from app.db.session import SessionLocal
    from app.storage import storage

    upload_response = upload(
        "delete-me.txt", b"Distinct deletable content about kangaroo migration patterns.", "text/plain"
    )
    document_id = upload_response.json()["id"]
    assert client.get(f"/documents/{document_id}").json()["status"] == "completed"

    # Confirm it's actually retrievable before deleting, so the
    # post-delete check below is a meaningful negative, not a tautology.
    search_before = client.post("/search", json={"query": "kangaroo migration patterns"})
    assert any(r["document_id"] == document_id for r in search_before.json()["results"])

    db = SessionLocal()
    try:
        from tests.db_utils import DEFAULT_TEST_USER_EMAIL

        owner = crud.get_user_by_email(db, DEFAULT_TEST_USER_EMAIL)
        storage_path = crud.get_document(db, uuid.UUID(document_id), owner.id).storage_path
    finally:
        db.close()
    assert storage.read_bytes(storage_path)  # file exists pre-delete (would raise otherwise)

    response = client.delete(f"/documents/{document_id}")
    assert response.status_code == 204

    assert client.get(f"/documents/{document_id}").status_code == 404

    search_after = client.post("/search", json={"query": "kangaroo migration patterns"})
    assert not any(r["document_id"] == document_id for r in search_after.json()["results"])

    with pytest.raises(FileNotFoundError):
        storage.read_bytes(storage_path)


def test_delete_nonexistent_document_returns_404():
    response = client.delete("/documents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_get_document_file_returns_original_bytes():
    content = b"Distinct file-serving test content for download verification."
    upload_response = upload("file-serving-check.txt", content, "text/plain")
    document_id = upload_response.json()["id"]

    response = client.get(f"/documents/{document_id}/file")
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"].startswith("text/plain")
    assert "file-serving-check.txt" in response.headers["content-disposition"]
    # TXT is browser-renderable — must open in a tab, not force a download.
    assert response.headers["content-disposition"].startswith("inline")


def test_get_document_file_is_inline_for_images_including_webp():
    # A 1x1 PNG's worth of bytes is enough here — this endpoint only cares
    # about content-type/disposition by extension, not image validity.
    upload_response = upload("photo.webp", b"fake webp bytes for header-only verification", "image/webp")
    document_id = upload_response.json()["id"]

    response = client.get(f"/documents/{document_id}/file")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["content-disposition"].startswith("inline")


def test_get_document_file_is_attachment_for_docx():
    from tests.docx_fixtures import make_docx_bytes

    docx_bytes = make_docx_bytes(heading="Test", paragraphs=["Distinct docx download-disposition test content."])
    upload_response = upload(
        "report.docx",
        docx_bytes,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    document_id = upload_response.json()["id"]

    response = client.get(f"/documents/{document_id}/file")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    # DOCX has no in-browser renderer — served as a real, explicit
    # download rather than a broken "open" that downloads anyway.
    assert response.headers["content-disposition"].startswith("attachment")


def test_get_document_file_for_nonexistent_document_returns_404():
    response = client.get("/documents/00000000-0000-0000-0000-000000000000/file")
    assert response.status_code == 404


def test_get_document_file_supports_range_requests():
    # Some browsers' built-in PDF viewers fetch large files progressively
    # via Range requests rather than downloading the whole thing up
    # front — a server that ignores Range and always returns the full
    # body can be exactly the kind of mismatch that makes a viewer show
    # nothing instead of the document.
    content = b"0123456789" * 100  # 1000 bytes, enough for a meaningful partial range
    upload_response = upload("range-check.txt", content, "text/plain")
    document_id = upload_response.json()["id"]

    response = client.get(f"/documents/{document_id}/file", headers={"Range": "bytes=0-9"})
    assert response.status_code == 206
    assert response.content == content[:10]
    assert response.headers["content-range"] == f"bytes 0-9/{len(content)}"
    assert response.headers["accept-ranges"] == "bytes"


def test_get_document_file_advertises_range_support_on_full_requests():
    upload_response = upload("range-advertise-check.txt", b"Some content.", "text/plain")
    document_id = upload_response.json()["id"]

    response = client.get(f"/documents/{document_id}/file")
    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == str(len(b"Some content."))


def test_get_document_file_returns_clean_404_when_file_missing_from_disk():
    from app.db import crud
    from app.db.session import SessionLocal
    from app.storage import storage

    upload_response = upload("vanished-from-disk.txt", b"This file will be deleted straight off disk.", "text/plain")
    document_id = upload_response.json()["id"]

    db = SessionLocal()
    try:
        from tests.db_utils import DEFAULT_TEST_USER_EMAIL

        owner = crud.get_user_by_email(db, DEFAULT_TEST_USER_EMAIL)
        document = crud.get_document(db, uuid.UUID(document_id), owner.id)
        storage.delete(document.storage_path)  # simulate the file going missing independently of the DB row
    finally:
        db.close()

    response = client.get(f"/documents/{document_id}/file")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert "could not be found" in response.json()["detail"].lower()


def test_get_document_file_for_url_sourced_document_returns_404(monkeypatch):
    # URL-sourced documents have no uploaded file (storage_path is None) —
    # the frontend already has source_url for those, so this endpoint
    # correctly has nothing to serve.
    import app.ingestion.service as service_module

    fake_html = "<html><head><title>File Serving Test</title></head><body><article><p>Distinct URL file serving test content.</p></article></body></html>"
    monkeypatch.setattr(service_module, "fetch_url", lambda url: (fake_html.encode(), "text/html"))

    response = client.post("/documents/url", json={"url": "https://example.com/file-serving-test"})
    document_id = response.json()["id"]

    file_response = client.get(f"/documents/{document_id}/file")
    assert file_response.status_code == 404
