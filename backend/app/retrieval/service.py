import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.memory_diagnostics import log_memory
from app.embeddings import embed_texts
from app.retrieval.repository import search_chunks
from app.retrieval.validation import validate_query


def search(db: Session, query: str, top_k: int, user_id: uuid.UUID) -> list[dict]:
    """Embeds the query with the exact same embedding function used for
    document chunks (app.embeddings.embed_texts — there is only one such
    function in the app, so "same model and configuration" is guaranteed by
    construction rather than by keeping two configs in sync), then returns
    the top_k nearest chunks that also clear settings.min_relevance_score
    — nearest-K alone doesn't guarantee relevance (see config.py). Callers
    may legitimately get fewer than top_k results, including zero.
    Retrieval only — no answer is generated here. Scoped to user_id's own
    documents (see search_chunks) — never searches another user's data.
    """
    query = validate_query(query)
    query_embedding = embed_texts([query], task_type="RETRIEVAL_QUERY")[0]
    rows = search_chunks(db, query_embedding, top_k, user_id)

    results = [
        {
            "chunk_id": row.chunk_id,
            "document_id": row.document_id,
            "chunk_index": row.chunk_index,
            "text": row.text,
            "character_count": row.character_count,
            "page_number": row.page_number,
            "original_filename": row.original_filename,
            "source_type": row.source_type,
            "source_url": (row.doc_metadata or {}).get("source_url"),
            # pgvector's cosine_distance ranges 0 (identical) to 2
            # (opposite); flipping it to "similarity" (higher = more
            # relevant) is more intuitive for API consumers than a raw
            # distance would be.
            "similarity_score": 1 - row.distance,
        }
        for row in rows
    ]

    filtered = [r for r in results if r["similarity_score"] >= settings.min_relevance_score]
    log_memory("after_retrieval")
    return filtered
