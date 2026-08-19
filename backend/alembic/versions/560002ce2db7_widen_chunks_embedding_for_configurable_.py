"""widen chunks embedding for configurable dimension

Revision ID: 560002ce2db7
Revises: c2f5e0ecfa98
Create Date: 2026-08-19 16:22:47.917664

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from app.core.config import settings


# revision identifiers, used by Alembic.
revision: str = '560002ce2db7'
down_revision: Union[str, Sequence[str], None] = 'c2f5e0ecfa98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# chunks.embedding was originally created at a fixed 384 dimensions
# (all-MiniLM-L6-v2, the local embedding model — see the baseline
# migration). Switching EMBEDDING_PROVIDER to "gemini" in production uses
# a different model at a different dimension (768 by default — see
# config.py) — a different embedding space entirely, not just a wider
# vector, so old 384-dim vectors cannot be cast or reinterpreted at the
# new width.
_OLD_DIMENSION = 384


def upgrade() -> None:
    """Widens chunks.embedding to settings.embedding_dimension — a no-op
    if that's still 384 (e.g. local dev, where EMBEDDING_PROVIDER is
    unset/"local" and nothing about the embedding model changed), so this
    never touches local dev's embeddings. Only actually alters the column
    when the configured dimension has genuinely changed (e.g. production,
    EMBEDDING_PROVIDER=gemini).
    """
    new_dimension = settings.embedding_dimension
    if new_dimension == _OLD_DIMENSION:
        return

    # Old vectors are not valid at the new width — the whole point of a
    # dimension change is that they came from a different model, so they
    # must be re-embedded (see backend/scripts/backfill_embeddings.py),
    # not cast. Dropping and recreating the column (rather than an
    # in-place ALTER) makes this explicit and guarantees no invalid data
    # survives at the wrong width. search_chunks() already filters
    # "embedding IS NOT NULL" (see app/retrieval/repository.py), so
    # existing chunks are simply excluded from search results until the
    # backfill script re-embeds them — no broken reads, no downtime for
    # anything except search relevance until the backfill completes.
    op.drop_column("chunks", "embedding")
    op.add_column("chunks", sa.Column("embedding", Vector(new_dimension), nullable=True))


def downgrade() -> None:
    """Mirrors upgrade(): a no-op unless the dimension actually changed."""
    if settings.embedding_dimension == _OLD_DIMENSION:
        return

    op.drop_column("chunks", "embedding")
    op.add_column("chunks", sa.Column("embedding", Vector(_OLD_DIMENSION), nullable=True))
