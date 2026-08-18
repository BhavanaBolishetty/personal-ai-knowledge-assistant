import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.ask import run_ask
from app.api.schemas import (
    AskRequest,
    AskResponse,
    ConversationDetailResponse,
    ConversationSummary,
)
from app.db import crud
from app.db.session import get_db
from app.synthesis import answer_conversation_question

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_conversation_or_404(db: Session, conversation_id: uuid.UUID):
    conversation = crud.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.post("", response_model=ConversationSummary, status_code=201)
def create_conversation(db: Session = Depends(get_db)):
    return crud.create_conversation(db, id=uuid.uuid4())


@router.get("", response_model=list[ConversationSummary])
def list_conversations(db: Session = Depends(get_db)):
    return crud.list_conversations(db)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)):
    conversation = _get_conversation_or_404(db, conversation_id)
    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=crud.get_messages(db, conversation_id),
    )


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)):
    conversation = _get_conversation_or_404(db, conversation_id)
    crud.delete_conversation(db, conversation)


@router.post("/{conversation_id}/ask", response_model=AskResponse)
def ask_in_conversation(conversation_id: uuid.UUID, request: AskRequest, db: Session = Depends(get_db)):
    """Same grounded pipeline as POST /ask, but history-aware: recent
    turns in this conversation help resolve follow-up questions (e.g.
    "its" -> the thing just discussed) before retrieval runs, and both the
    question and answer are persisted as part of the conversation.
    """
    _get_conversation_or_404(db, conversation_id)
    result = run_ask(lambda: answer_conversation_question(db, conversation_id, request.query, request.top_k))
    return AskResponse(**result)
