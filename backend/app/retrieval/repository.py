import uuid

from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, DocumentStatus


def search_chunks(db: Session, query_embedding: list[float], top_k: int, user_id: uuid.UUID):
    """Runs the vector similarity search in Postgres via pgvector's cosine
    distance operator. Only columns actually needed by the API response are
    selected (never the embedding itself), and Postgres — not Python — does
    the ordering and limiting.

    Only chunks belonging to successfully completed documents are eligible.
    By the ingestion pipeline's invariant (app/ingestion/service.py), a
    completed document always has every chunk embedded — the
    embedding-is-not-null filter makes that explicit in the query itself
    rather than relying solely on that invariant holding forever.

    Scoped to the requesting user's own documents — without this filter,
    any user's question would search (and could ground an answer in) every
    other user's private documents too.
    """
    distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")

    return (
        db.query(
            Chunk.id.label("chunk_id"),
            Chunk.document_id,
            Chunk.chunk_index,
            Chunk.text,
            Chunk.character_count,
            Chunk.page_number,
            Document.original_filename,
            Document.source_type,
            Document.doc_metadata,
            distance,
        )
        .join(Document, Chunk.document_id == Document.id)
        .filter(Document.status == DocumentStatus.completed)
        .filter(Document.user_id == user_id)
        .filter(Chunk.embedding.isnot(None))
        .order_by(distance)
        .limit(top_k)
        .all()
    )
