from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import AskRequest, AskResponse
from app.core.rate_limit import limit_ask
from app.db.models import User
from app.db.session import get_db
from app.embeddings import EmbeddingError
from app.llm import LLMError, LLMRateLimitError, LLMTimeoutError
from app.retrieval import EmptyQueryError, QueryTooLongError
from app.synthesis import answer_question

router = APIRouter(tags=["ask"])

T = TypeVar("T")


def run_ask(call: Callable[[], T]) -> T:
    """Shared exception-to-HTTP mapping for anything that runs the
    retrieval -> Gemini pipeline (the stateless /ask route and the
    conversational /conversations/{id}/ask route) — kept in one place so
    the two never drift apart.
    """
    try:
        return call()
    except EmptyQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except QueryTooLongError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=503, detail="The embedding model is temporarily unavailable."
        ) from exc
    except LLMRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503, detail="The database is temporarily unavailable."
        ) from exc


@router.post("/ask", response_model=AskResponse, dependencies=[Depends(limit_ask)])
def ask_question(
    request: AskRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Grounded question answering: retrieves relevant chunks and asks
    Gemini to answer using only that retrieved context, returning
    structured source citations alongside the answer.

    Stateless — no conversation memory. See POST /conversations/{id}/ask
    for the conversation-aware version.
    """
    result = run_ask(lambda: answer_question(db, request.query, request.top_k, current_user.id))
    return AskResponse(**result)
