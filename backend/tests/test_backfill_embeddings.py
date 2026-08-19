import io

from fastapi.testclient import TestClient

from app.db.models import Chunk
from app.db.session import SessionLocal
from app.main import app
from scripts.backfill_embeddings import backfill

client = TestClient(app)


def _upload(filename, content):
    return client.post("/documents", files={"file": (filename, io.BytesIO(content), "text/plain")})


def _null_out_embeddings(document_id: str) -> int:
    """Simulates what the dimension-change Alembic migration does: clears
    existing embeddings so they're no longer valid at a new width."""
    db = SessionLocal()
    try:
        chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()
        for chunk in chunks:
            chunk.embedding = None
        db.commit()
        return len(chunks)
    finally:
        db.close()


def _embedding_is_null_count(document_id: str) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(Chunk)
            .filter(Chunk.document_id == document_id, Chunk.embedding.is_(None))
            .count()
        )
    finally:
        db.close()


def test_backfill_re_embeds_chunks_with_null_embedding():
    response = _upload("backfill-check.txt", b"Content used to verify the embedding backfill script works.")
    assert response.status_code == 201
    document_id = response.json()["id"]

    cleared = _null_out_embeddings(document_id)
    assert cleared > 0
    assert _embedding_is_null_count(document_id) == cleared

    backfill(batch_size=16, sleep_seconds=0, dry_run=False, limit=None)

    assert _embedding_is_null_count(document_id) == 0


def test_backfill_is_idempotent_on_a_second_run():
    response = _upload("backfill-idempotent-check.txt", b"More content for the idempotent backfill test.")
    document_id = response.json()["id"]
    _null_out_embeddings(document_id)

    backfill(batch_size=16, sleep_seconds=0, dry_run=False, limit=None)
    assert _embedding_is_null_count(document_id) == 0

    # Nothing left with a NULL embedding, so a second run must be a no-op —
    # it should not error, and should not re-process anything.
    backfill(batch_size=16, sleep_seconds=0, dry_run=False, limit=None)
    assert _embedding_is_null_count(document_id) == 0


def test_backfill_dry_run_does_not_write_anything():
    response = _upload("backfill-dry-run-check.txt", b"Content for the dry-run backfill test.")
    document_id = response.json()["id"]
    cleared = _null_out_embeddings(document_id)

    backfill(batch_size=16, sleep_seconds=0, dry_run=True, limit=None)

    # Dry run must not have written any embeddings back.
    assert _embedding_is_null_count(document_id) == cleared


def test_backfill_respects_limit():
    # --limit caps how many chunks backfill() processes *globally* (there's
    # only one production DB, no per-document scoping in the real script).
    # This test DB isn't truncated between tests, so drain any NULL-embedding
    # chunks left by other tests first — otherwise --limit could consume
    # them instead of this test's own chunks, making the assertion below
    # order-dependent on whatever else happened to run first.
    backfill(batch_size=1000, sleep_seconds=0, dry_run=False, limit=None)

    response = _upload(
        "backfill-limit-check.txt",
        ("Section about backfill limits and batching behavior. " * 200).encode(),
    )
    document_id = response.json()["id"]
    cleared = _null_out_embeddings(document_id)
    assert cleared > 1, "need multiple chunks for --limit to be meaningful"

    backfill(batch_size=16, sleep_seconds=0, dry_run=False, limit=1)

    remaining = _embedding_is_null_count(document_id)
    assert remaining == cleared - 1
