import enum
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.config import settings
from app.db.base import Base


class SourceType(str, enum.Enum):
    pdf = "pdf"
    text = "text"
    markdown = "markdown"
    note = "note"
    docx = "docx"
    url = "url"
    image = "image"


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class User(Base):
    """An account. Every document and conversation is scoped to exactly one
    user (see Document.user_id / Conversation.user_id below) — without this,
    the app has no concept of "private" data at all, which is exactly the
    gap that motivated adding auth: the live demo URL let anyone see every
    uploaded document and every conversation, not just their own."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Document(Base):
    """Metadata for one uploaded knowledge source. Chunk/embedding storage
    is added in a later milestone once retrieval is implemented."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable rather than a hard NOT NULL: documents uploaded before auth
    # existed have no owner and stay that way until explicitly claimed (see
    # backend/scripts/assign_orphaned_data.py) — every query that lists/gets/
    # deletes documents filters by user_id, so a NULL owner is simply
    # invisible/inaccessible rather than a data-integrity problem to fix.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    original_filename = Column(String, nullable=False)
    source_type = Column(Enum(SourceType, name="source_type"), nullable=False)
    status = Column(
        Enum(DocumentStatus, name="document_status"),
        nullable=False,
        default=DocumentStatus.uploaded,
    )
    file_size_bytes = Column(Integer, nullable=True)
    storage_path = Column(String, nullable=True)
    extracted_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    doc_metadata = Column("metadata", JSONB, nullable=True)
    uploaded_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def source_url(self) -> str | None:
        return (self.doc_metadata or {}).get("source_url")

    chunks = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Chunk.chunk_index",
    )


class Chunk(Base):
    """A retrieval-sized slice of one document's extracted text, plus its
    embedding vector once the embedding step succeeds. Semantic search
    (comparing a query's embedding against these vectors) is implemented
    in a later milestone — this table only stores them for now."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_id_chunk_index"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    character_count = Column(Integer, nullable=False)
    # Populated with a real page number for paginated sources (currently
    # PDF only — see PAGINATED_SOURCE_TYPES in app/ingestion/service.py).
    # NULL for source types with no real page concept.
    page_number = Column(Integer, nullable=True)
    chunk_metadata = Column("metadata", JSONB, nullable=True)
    # NULL until the embedding step succeeds for this chunk's document. A
    # chunk with a NULL embedding is never mistaken for a ready-to-search
    # one: its document's status stays "failed" until every chunk has one
    # (see app/ingestion/service.py).
    embedding = Column(Vector(settings.embedding_dimension), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document = relationship("Document", back_populates="chunks")

    @property
    def has_embedding(self) -> bool:
        return self.embedding is not None


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class Conversation(Base):
    """A persisted chat thread, scoped to the user who created it (see
    User.__doc__ above for why user_id is nullable)."""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String, nullable=False, default="New conversation")
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )


class Message(Base):
    """One turn in a conversation. Assistant messages carry their
    structured sources (same shape as the stateless /ask response) as
    JSONB, so reopening a conversation re-renders the same citations
    without re-running retrieval."""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(Enum(MessageRole, name="message_role"), nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    conversation = relationship("Conversation", back_populates="messages")
