import io

from fastapi.testclient import TestClient

from app.db import crud
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)


def upload(filename, content, content_type):
    return client.post(
        "/documents",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


def test_upload_triggers_chunk_creation_with_correct_indexes():
    content = ("This document discusses retrieval augmented generation. " * 40).encode()
    response = upload("rag-notes.txt", content, "text/plain")
    assert response.status_code == 201
    document_id = response.json()["id"]

    detail = client.get(f"/documents/{document_id}").json()
    assert detail["status"] == "completed"
    assert detail["chunk_count"] > 0

    chunks_response = client.get(f"/documents/{document_id}/chunks")
    assert chunks_response.status_code == 200
    body = chunks_response.json()
    assert body["total_chunks"] == detail["chunk_count"]
    assert [c["chunk_index"] for c in body["chunks"]] == list(range(len(body["chunks"])))


def test_chunks_are_associated_with_the_correct_document():
    first = upload("doc-a.txt", b"Document A content about caching strategies.", "text/plain")
    second = upload(
        "doc-b.txt", b"Document B content about load balancing approaches.", "text/plain"
    )

    first_chunks = client.get(f"/documents/{first.json()['id']}/chunks").json()["chunks"]
    second_chunks = client.get(f"/documents/{second.json()['id']}/chunks").json()["chunks"]

    assert all("caching" in c["text"] for c in first_chunks)
    assert all("load balancing" in c["text"] for c in second_chunks)


def test_failed_chunking_leaves_no_partial_chunks(monkeypatch):
    import app.ingestion.service as service_module

    def _broken_chunk_text(*args, **kwargs):
        raise RuntimeError("simulated chunking failure")

    monkeypatch.setattr(service_module, "chunk_text", _broken_chunk_text)

    response = upload("will-fail.txt", b"Some perfectly fine text content.", "text/plain")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert "Chunking failed" in body["error_message"]

    db = SessionLocal()
    try:
        chunks = crud.get_chunks_for_document(db, body["id"], limit=10)
        assert chunks == []
    finally:
        db.close()
