import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Chunk, Conversation, Document, DocumentStatus, Message, MessageRole, SourceType, User


def create_user(db: Session, *, email: str, hashed_password: str) -> User:
    user = User(email=email, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def create_document(
    db: Session,
    *,
    id: uuid.UUID,
    user_id: uuid.UUID,
    original_filename: str,
    source_type: SourceType,
    file_size_bytes: int,
    storage_path: str | None = None,
    doc_metadata: dict | None = None,
) -> Document:
    document = Document(
        id=id,
        user_id=user_id,
        original_filename=original_filename,
        source_type=source_type,
        status=DocumentStatus.processing,
        file_size_bytes=file_size_bytes,
        storage_path=storage_path,
        doc_metadata=doc_metadata,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def mark_document_completed(db: Session, document: Document, *, extracted_text: str) -> Document:
    document.status = DocumentStatus.completed
    document.extracted_text = extracted_text
    document.processed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(document)
    return document


def mark_document_failed(db: Session, document: Document, *, error_message: str) -> Document:
    document.status = DocumentStatus.failed
    document.error_message = error_message
    document.processed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(document)
    return document


def get_document(db: Session, document_id: uuid.UUID, user_id: uuid.UUID) -> Document | None:
    # Scoped by owner in the query itself (not checked after fetching) so a
    # document belonging to another user returns None — indistinguishable
    # from "doesn't exist" to every caller, which already 404s on None.
    return db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()


def list_documents(db: Session, user_id: uuid.UUID) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.user_id == user_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )


def delete_document(db: Session, document: Document) -> None:
    # Chunk.document_id has ondelete="CASCADE" (see models.py), so the
    # database removes the document's chunks/embeddings in the same
    # statement — no separate chunk-deletion step needed here.
    db.delete(document)
    db.commit()


def create_chunks(
    db: Session, document_id: uuid.UUID, chunk_records: list[tuple[str, int | None]]
) -> list[Chunk]:
    # A single add_all + commit: either every chunk for this document is
    # written, or (if the commit raises) none are — no partial chunk sets.
    # Each record is (text, page_number) — page_number is None for source
    # types with no real page concept (see app/extraction/__init__.py).
    chunk_rows = [
        Chunk(
            document_id=document_id,
            chunk_index=index,
            text=text,
            character_count=len(text),
            page_number=page_number,
        )
        for index, (text, page_number) in enumerate(chunk_records)
    ]
    db.add_all(chunk_rows)
    db.commit()
    for row in chunk_rows:
        db.refresh(row)
    return chunk_rows


def count_chunks_for_document(db: Session, document_id: uuid.UUID) -> int:
    return db.query(Chunk).filter(Chunk.document_id == document_id).count()


def get_chunks_for_document(db: Session, document_id: uuid.UUID, limit: int = 50) -> list[Chunk]:
    return (
        db.query(Chunk)
        .filter(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
        .limit(limit)
        .all()
    )


def store_chunk_embeddings(
    db: Session, chunks: list[Chunk], embeddings: list[list[float]]
) -> None:
    # One update per chunk, but a single commit for the whole document: all
    # of its chunks get an embedding, or (if the commit fails) none do.
    if len(chunks) != len(embeddings):
        raise ValueError("Number of chunks and embeddings must match.")

    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding

    db.commit()


def create_conversation(
    db: Session, *, id: uuid.UUID, user_id: uuid.UUID, title: str = "New conversation"
) -> Conversation:
    conversation = Conversation(id=id, user_id=user_id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, user_id: uuid.UUID) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def get_conversation(db: Session, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
    # Scoped by owner in the query itself — see get_document's comment above,
    # same reasoning.
    return (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )


def delete_conversation(db: Session, conversation: Conversation) -> None:
    db.delete(conversation)
    db.commit()


def touch_conversation(db: Session, conversation: Conversation) -> None:
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()


def set_conversation_title_if_default(db: Session, conversation: Conversation, title: str) -> None:
    if conversation.title != "New conversation":
        return
    trimmed = title.strip().replace("\n", " ")
    conversation.title = (trimmed[:60] + "…") if len(trimmed) > 60 else trimmed
    db.commit()


def create_message(
    db: Session,
    conversation_id: uuid.UUID,
    *,
    role: MessageRole,
    content: str,
    sources: list[dict] | None = None,
) -> Message:
    message = Message(conversation_id=conversation_id, role=role, content=content, sources=sources)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_messages(db: Session, conversation_id: uuid.UUID) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .all()
    )


def get_recent_messages(db: Session, conversation_id: uuid.UUID, limit: int) -> list[Message]:
    # Most recent `limit` messages, returned in chronological order (oldest
    # first) so callers can read them as a normal conversation transcript.
    recent = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(recent))
