"""correct chunks embedding dimension by introspecting actual column state

Revision ID: a51acb26dbb5
Revises: 560002ce2db7
Create Date: 2026-08-19 18:07:47.029340

"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from app.core.config import settings


# revision identifiers, used by Alembic.
revision: str = 'a51acb26dbb5'
down_revision: Union[str, Sequence[str], None] = '560002ce2db7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_embedding_dimension(connection) -> int | None:
    """Reads the chunks.embedding column's actual current width directly
    from Postgres, rather than trusting any earlier migration's own
    assumption about what it "should" be. This is the fix for
    560002ce2db7: that migration decided whether to act based on
    settings.embedding_dimension at the moment it ran, and if
    EMBEDDING_PROVIDER wasn't yet "gemini" in that environment at that
    exact moment, it correctly did nothing by its own logic — but Alembic
    still recorded it as applied, so it will never run again even after
    the environment is fixed. Checking the database's real, current state
    (instead of environment state at some past migration run) makes this
    migration correct regardless of what actually happened before.
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

    # Old vectors are not valid at a different width — they came from a
    # different model entirely, not just a differently-sized one — so
    # they must be re-embedded (see backend/scripts/backfill_embeddings.py),
    # not cast. Dropping and recreating the column makes that explicit.
    # search_chunks() already filters "embedding IS NOT NULL" (see
    # app/retrieval/repository.py), so chunks are simply excluded from
    # search until the backfill script re-embeds them.
    op.drop_column("chunks", "embedding")
    op.add_column("chunks", sa.Column("embedding", Vector(target_dimension), nullable=True))


def downgrade() -> None:
    """No safe generic downgrade — the previous dimension isn't knowable
    from this migration alone (560002ce2db7 didn't necessarily succeed in
    setting it). If you need to roll back, restore from a backup or run a
    manual, environment-specific ALTER instead.
    """
    raise NotImplementedError(
        "No generic downgrade for this migration — see the docstring."
    )
