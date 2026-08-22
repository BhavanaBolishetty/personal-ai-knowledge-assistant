from sqlalchemy import text

from app.core.security import hash_password
from app.db import crud
from app.db.base import Base
from app.db.session import SessionLocal, engine

# A fixed, well-known account every test implicitly runs as by default (see
# conftest.py's get_current_user override) — recreated here, not just once
# at session start, so it survives every truncate_all() call, including
# test_retrieval_quality.py's module-scoped one.
DEFAULT_TEST_USER_EMAIL = "test-user@example.com"


def truncate_all() -> None:
    """Wipes every application table, then recreates the default test user
    (see DEFAULT_TEST_USER_EMAIL). CASCADE means the exact table order given
    doesn't matter for foreign-key dependencies (e.g. messages ->
    conversations, chunks/documents -> users)."""
    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))

    db = SessionLocal()
    try:
        crud.create_user(db, email=DEFAULT_TEST_USER_EMAIL, hashed_password=hash_password("test-password"))
    finally:
        db.close()
