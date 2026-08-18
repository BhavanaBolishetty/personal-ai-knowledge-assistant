from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.schemas import SearchRequest, SearchResponse
from app.db.session import get_db
from app.embeddings import EmbeddingError
from app.retrieval import EmptyQueryError, QueryTooLongError, search

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search_documents(request: SearchRequest, db: Session = Depends(get_db)):
    """Semantic search over successfully embedded chunks.

    This is retrieval only — it returns relevant chunks and their source
    metadata. It does not generate an answer (see a future milestone for
    that).
    """
    try:
        results = search(db, request.query, request.top_k)
    except EmptyQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except QueryTooLongError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=503, detail="The embedding model is temporarily unavailable."
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503, detail="The database is temporarily unavailable."
        ) from exc

    return SearchResponse(
        query=request.query,
        top_k=request.top_k,
        result_count=len(results),
        results=results,
    )
