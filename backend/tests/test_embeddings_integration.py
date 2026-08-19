import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def upload(filename, content, content_type):
    return client.post(
        "/documents",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


def test_chunks_receive_embeddings_after_successful_processing():
    content = b"Vector databases store embeddings for semantic search over documents."
    response = upload("embedding-notes.txt", content, "text/plain")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"

    chunks = client.get(f"/documents/{body['id']}/chunks").json()["chunks"]
    assert len(chunks) > 0
    assert all(c["has_embedding"] for c in chunks)


def test_no_silently_missing_embeddings_across_multiple_chunks():
    content = ("Section about caching strategies and their trade-offs. " * 200).encode()
    response = upload("multi-chunk.txt", content, "text/plain")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"

    chunks = client.get(f"/documents/{body['id']}/chunks?limit=200").json()["chunks"]
    assert len(chunks) > 1
    assert all(
        c["has_embedding"] for c in chunks
    ), "every chunk of a completed document must have an embedding"


def test_embedding_failure_is_handled_cleanly_and_document_not_marked_completed(monkeypatch):
    import app.ingestion.service as service_module

    def _broken_embed_texts(texts, **kwargs):
        raise RuntimeError("simulated embedding failure")

    monkeypatch.setattr(service_module, "embed_texts", _broken_embed_texts)

    response = upload(
        "will-fail-embedding.txt", b"Some perfectly fine text content.", "text/plain"
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert "Embedding failed" in body["error_message"]

    chunks = client.get(f"/documents/{body['id']}/chunks").json()["chunks"]
    assert len(chunks) > 0  # chunking succeeded before the simulated embedding failure
    assert all(not c["has_embedding"] for c in chunks)
