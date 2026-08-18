"""baseline

Revision ID: 588acbb8b420
Revises: 
Create Date: 2026-08-11 23:22:10.483864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '588acbb8b420'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# NOTE: this migration was originally generated empty (`pass` / `pass`) and
# applied to the dev database with `alembic stamp` — the documents/chunks
# tables already existed there from before Alembic was introduced, created
# directly from the SQLAlchemy models. That meant `alembic upgrade head`
# against a genuinely empty database (a fresh clone, or an isolated test
# database) silently created nothing here, then failed on the next
# migration's `ALTER TYPE source_type ADD VALUE` because the type never
# existed. Filled in with the real schema so Alembic actually works as the
# single source of truth from a clean database — this does not change the
# already-up-to-date dev database, since these tables already exist there.
def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Passed as column types below with their default create_type=True, so
    # SQLAlchemy creates each type once, as part of creating "documents" —
    # calling .create() here too would create them a second time and fail.
    source_type = postgresql.ENUM("pdf", "text", "markdown", "note", name="source_type")
    document_status = postgresql.ENUM(
        "uploaded", "processing", "completed", "failed", name="document_status"
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("status", document_status, nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.String(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_id_chunk_index"),
    )
    op.create_index(op.f("ix_chunks_document_id"), "chunks", ["document_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_chunks_document_id"), table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("documents")
    postgresql.ENUM(name="document_status").drop(op.get_bind())
    postgresql.ENUM(name="source_type").drop(op.get_bind())
