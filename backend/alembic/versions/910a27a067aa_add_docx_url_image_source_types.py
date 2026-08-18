"""add docx url image source types

Revision ID: 910a27a067aa
Revises: 588acbb8b420
Create Date: 2026-08-11 23:22:45.587299

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '910a27a067aa'
down_revision: Union[str, Sequence[str], None] = '588acbb8b420'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Postgres enum values can't be removed within a transaction, so this
    # migration is additive-only (see downgrade note below).
    for value in ("docx", "url", "image"):
        op.execute(f"ALTER TYPE source_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no ALTER TYPE ... DROP VALUE. Reverting would require
    # rebuilding the enum type (create new type, migrate column, drop old
    # type) — not implemented since no code path produces these values
    # without this migration's forward changes also being present.
    raise NotImplementedError("Downgrade not supported: Postgres cannot drop enum values.")
