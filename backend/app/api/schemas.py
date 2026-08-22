import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.config import settings
from app.db.models import DocumentStatus, SourceType


class SignupRequest(BaseModel):
    email: EmailStr
    # Length-only requirement, deliberately not complex composition rules
    # (uppercase/digit/symbol requirements) — those rules are well known to
    # push users toward predictable patterns without meaningfully improving
    # real-world security, and this project isn't the place for a password
    # policy debate.
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    token: str
    user: UserResponse


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    source_type: SourceType
    status: DocumentStatus
    file_size_bytes: int | None
    error_message: str | None
    source_url: str | None
    uploaded_at: datetime
    processed_at: datetime | None


class DocumentDetailResponse(DocumentResponse):
    extracted_text: str | None
    chunk_count: int


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_index: int
    text: str
    character_count: int
    page_number: int | None
    has_embedding: bool
    created_at: datetime


class DocumentChunksResponse(BaseModel):
    document_id: uuid.UUID
    total_chunks: int
    chunks: list[ChunkResponse]


class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural-language question to search for.")
    # Range-checked here (request shape); non-empty/max-length content
    # checks live in app/retrieval/validation.py so every query-content
    # rule produces the same clean error shape, instead of splitting
    # "empty" and "too long" across two different validation mechanisms.
    top_k: int = Field(
        default=settings.default_top_k,
        ge=1,
        le=settings.max_top_k,
        description="Number of chunks to retrieve.",
    )


class SearchResultItem(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    character_count: int
    page_number: int | None
    original_filename: str
    source_type: SourceType
    source_url: str | None
    similarity_score: float


class SearchResponse(BaseModel):
    query: str
    top_k: int
    result_count: int
    results: list[SearchResultItem]


class AskRequest(BaseModel):
    query: str = Field(..., description="Natural-language question to answer using the knowledge base.")
    top_k: int = Field(
        default=settings.default_top_k,
        ge=1,
        le=settings.max_top_k,
        description="Number of chunks to retrieve as context for the answer.",
    )


class AskSourceItem(BaseModel):
    id: str
    document_id: uuid.UUID
    filename: str
    source_url: str | None
    # Debug/dev-only field — not shown in the default chat UI.
    chunk_index: int
    page_start: int | None
    page_end: int | None


class AddUrlRequest(BaseModel):
    url: str = Field(..., description="Public http(s) URL of an article/blog page to ingest.")


class AskResponse(BaseModel):
    answer: str
    sources: list[AskSourceItem]
    retrieved_chunk_count: int
    model: str | None


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    sources: list[AskSourceItem] | None
    created_at: datetime


class ConversationDetailResponse(ConversationSummary):
    messages: list[MessageResponse]
