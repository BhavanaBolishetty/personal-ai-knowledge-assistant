"""resync chunks embedding dimension after deferred env config

Revision ID: eff5700db0a1
Revises: 52842fc8bb30
Create Date: 2026-08-22 14:00:46.784404

"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from app.core.config import settings


# revision identifiers, used by Alembic.
revision: str = 'eff5700db0a1'
down_revision: Union[str, Sequence[str], None] = '52842fc8bb30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_embedding_dimension(connection) -> int | None:
    """Same introspection a51acb26dbb5 already used, applied once more.

    a51acb26dbb5 was written to fix exactly this class of bug — a
    migration that decides what to do based on settings.embedding_dimension
    at the moment it happens to run, rather than the column's real state —
    but it hit the same trap itself: Render Blueprint env var changes (see
    render.yaml's EMBEDDING_PROVIDER) only apply automatically to services
    created fresh from the blueprint. For an already-existing service they
    need a one-time manual dashboard edit, confirmed in commit 45661b1's
    own message ("Not yet active in production... render.yaml changes
    don't retroactively apply to an already-created service"). So
    a51acb26dbb5 ran once while the live EMBEDDING_PROVIDER was still
    "local", saw 384==384, correctly no-op'd by its own logic — and, being
    marked "applied", never ran again even after the dashboard was fixed.
    Reading the database's actual current state (instead of trusting that
    an earlier migration run reflected today's environment) makes this
    migration correct regardless of what happened before, and safe to
    leave as a no-op forever once the dimension genuinely matches.
    """
    result = connection.execute(
        sa.text(
            "SELECT format_type(atttypid, atttypmod) "
            "FROM pg_attribute "
            "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding' AND NOT attisdropped"
        )
    ).scalar()
    if result is None:
        return None
    match = re.search(r"vector\((\d+)\)", result)
    return int(match.group(1)) if match else None


def upgrade() -> None:
    target_dimension = settings.embedding_dimension
    connection = op.get_bind()
    current_dimension = _current_embedding_dimension(connection)

    if current_dimension == target_dimension:
        return

    # Old vectors at the previous width are not valid at the new one — they
    # came from a different embedding model entirely (all-MiniLM-L6-v2 vs.
    # gemini-embedding-001), not just a differently-sized version of the
    # same one — so they must be re-embedded (see
    # backend/scripts/backfill_embeddings.py), not cast. Dropping and
    # recreating the column makes that explicit. Every other column
    # (id, document_id, chunk_index, text, character_count, page_number,
    # metadata, created_at) is untouched, and no rows are added or removed
    # — only this one column's values are discarded and rebuilt as NULL.
    # search_chunks() already filters "embedding IS NOT NULL" (see
    # app/retrieval/repository.py), so affected chunks are simply excluded
    # from search until the backfill script re-embeds them — no broken
    # reads, no downtime.
    op.drop_column("chunks", "embedding")
    op.add_column("chunks", sa.Column("embedding", Vector(target_dimension), nullable=True))


def downgrade() -> None:
    """No safe generic downgrade — mirrors a51acb26dbb5. The previous
    dimension isn't reliably knowable from this migration alone. If you
    need to roll back, restore from a backup or run a manual,
    environment-specific ALTER instead.
    """
    raise NotImplementedError(
        "No generic downgrade for this migration — see the docstring."
    )
