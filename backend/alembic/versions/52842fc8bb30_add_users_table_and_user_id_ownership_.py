"""add users table and user_id ownership columns

Revision ID: 52842fc8bb30
Revises: a51acb26dbb5
Create Date: 2026-08-21 21:25:02.016036

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '52842fc8bb30'
down_revision: Union[str, Sequence[str], None] = 'a51acb26dbb5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # Nullable — documents/conversations created before auth existed have no
    # owner and stay that way until claimed by
    # backend/scripts/assign_orphaned_data.py. Every list/get/delete query is
    # scoped by user_id at the application layer, so a NULL owner is simply
    # inaccessible rather than a data-integrity problem needing a follow-up
    # NOT NULL migration.
    op.add_column("documents", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_documents_user_id"), "documents", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_documents_user_id_users", "documents", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )

    op.add_column("conversations", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_conversations_user_id_users", "conversations", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("fk_conversations_user_id_users", "conversations", type_="foreignkey")
    op.drop_index(op.f("ix_conversations_user_id"), table_name="conversations")
    op.drop_column("conversations", "user_id")

    op.drop_constraint("fk_documents_user_id_users", "documents", type_="foreignkey")
    op.drop_index(op.f("ix_documents_user_id"), table_name="documents")
    op.drop_column("documents", "user_id")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
