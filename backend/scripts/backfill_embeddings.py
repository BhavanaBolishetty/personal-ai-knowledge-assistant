"""Re-embeds every chunk whose embedding is NULL, using whichever
embedding provider is currently configured (EMBEDDING_PROVIDER, plus
either LOCAL_EMBEDDING_MODEL_NAME/LOCAL_EMBEDDING_DIMENSION or
GEMINI_EMBEDDING_MODEL_NAME/GEMINI_EMBEDDING_DIMENSION depending on
which provider is active — the same settings the app itself reads, see
app/core/config.py).

Needed after 560002ce2db7_widen_chunks_embedding_for_configurable_.py:
that migration drops and recreates chunks.embedding whenever the
configured dimension changes (e.g. switching EMBEDDING_PROVIDER from
"local" to "gemini" in production), which sets every existing chunk's
embedding back to NULL — old vectors from a different model are not
valid at the new width and cannot be reused. Chunks with a NULL
embedding are already excluded from search results (see
app/retrieval/repository.py), so the app keeps working correctly with
reduced (and shrinking as this runs) coverage while this backs them
all up.

Resumable / idempotent by construction: always selects chunks WHERE
embedding IS NULL, so re-running after an interruption (Ctrl-C, a crash,
a transient API failure) picks up exactly where it left off — chunks
that already got an embedding are never re-processed or double-charged.

Usage (run from backend/, with the same environment — DATABASE_URL,
EMBEDDING_PROVIDER, GEMINI_API_KEY, etc. — as the target environment):

    python -m scripts.backfill_embeddings
    python -m scripts.backfill_embeddings --batch-size 20 --sleep 1
    python -m scripts.backfill_embeddings --dry-run
    python -m scripts.backfill_embeddings --limit 50   # smoke-test a few chunks first
"""
import argparse
import time

from app.db import crud
from app.db.models import Chunk
from app.db.session import SessionLocal
from app.embeddings import EmbeddingError, embed_texts


def _count_remaining(db) -> int:
    return db.query(Chunk).filter(Chunk.embedding.is_(None)).count()


def _fetch_batch(db, batch_size: int) -> list[Chunk]:
    return (
        db.query(Chunk)
        .filter(Chunk.embedding.is_(None))
        .order_by(Chunk.created_at)
        .limit(batch_size)
        .all()
    )


def backfill(*, batch_size: int, sleep_seconds: float, dry_run: bool, limit: int | None) -> None:
    db = SessionLocal()
    try:
        total_remaining = _count_remaining(db)
        print(f"[backfill] {total_remaining} chunk(s) currently need an embedding.")
        if total_remaining == 0:
            print("[backfill] nothing to do.")
            return

        if dry_run:
            preview = _fetch_batch(db, min(batch_size, total_remaining))
            print(f"[backfill] dry run — would embed {len(preview)} chunk(s) in the first batch, e.g.:")
            for chunk in preview[:5]:
                print(f"  chunk {chunk.id} (document {chunk.document_id}): {chunk.text[:80]!r}")
            return

        processed = 0
        while True:
            if limit is not None and processed >= limit:
                print(f"[backfill] reached --limit {limit}, stopping.")
                break

            remaining_for_limit = None if limit is None else limit - processed
            this_batch_size = batch_size if remaining_for_limit is None else min(batch_size, remaining_for_limit)

            batch = _fetch_batch(db, this_batch_size)
            if not batch:
                break

            try:
                embeddings = embed_texts([chunk.text for chunk in batch], task_type="RETRIEVAL_DOCUMENT")
                crud.store_chunk_embeddings(db, batch, embeddings)
            except EmbeddingError as exc:
                print(f"[backfill] batch failed: {exc}")
                print("[backfill] stopping — re-run this script to resume from where it left off.")
                return

            processed += len(batch)
            print(f"[backfill] embedded {processed} chunk(s) so far ({_count_remaining(db)} remaining)")

            if sleep_seconds:
                time.sleep(sleep_seconds)

        print(f"[backfill] done. {processed} chunk(s) embedded this run.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch-size", type=int, default=16, help="Chunks embedded per API call (default: 16).")
    parser.add_argument(
        "--sleep", type=float, default=0.0, help="Seconds to pause between batches, to go easy on API quota."
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview the first batch without writing anything.")
    parser.add_argument("--limit", type=int, default=None, help="Stop after this many chunks (e.g. to smoke-test).")
    args = parser.parse_args()

    backfill(batch_size=args.batch_size, sleep_seconds=args.sleep, dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
