from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine


def truncate_all() -> None:
    """Wipes every application table. CASCADE means the exact table order
    given doesn't matter for foreign-key dependencies (e.g. messages ->
    conversations, chunks -> documents)."""
    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
