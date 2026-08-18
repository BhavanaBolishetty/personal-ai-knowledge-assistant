# The test suite must never touch the real development database — running
# pytest repeatedly (or alongside manual verification in the browser) would
# otherwise accumulate documents/conversations across runs and made
# retrieval-quality assertions flaky (near-duplicate "binary search"-style
# fixtures from earlier runs competing with the current run's fixtures).
#
# This line has to run before ANY `app.*` module is imported anywhere in the
# test session — Settings reads POSTGRES_DB from the environment once, at
# import time, and every test module does `from app.main import app` at
# module level. Pytest always imports a directory's conftest.py before it
# collects that directory's test_*.py files, so setting the override here,
# before any `app` import in this file, guarantees every test module picks
# up the test database instead of the dev one.
import os

_DEV_POSTGRES_DB = os.getenv("POSTGRES_DB", "paika_knowledge_base")
os.environ["POSTGRES_DB"] = os.getenv("POSTGRES_TEST_DB", f"{_DEV_POSTGRES_DB}_test")

import pathlib

import psycopg2
import pytest
from alembic.config import Config
from alembic import command
from psycopg2 import sql
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from tests.db_utils import truncate_all


def _ensure_test_database_exists() -> None:
    # Connects to the cluster's always-present admin database ("postgres")
    # to check for / create the test database itself — you can't run
    # CREATE DATABASE against the database you're currently connected to.
    admin_connection = psycopg2.connect(
        dbname="postgres",
        user=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
    )
    admin_connection.autocommit = True
    try:
        with admin_connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.postgres_db,))
            if cursor.fetchone() is None:
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.postgres_db)))
    finally:
        admin_connection.close()


def _run_migrations() -> None:
    # Alembic is the single schema-management mechanism for this project —
    # the test database is brought up to date the same way the dev/prod
    # database is, instead of a separate Base.metadata.create_all() path
    # that could silently drift from the real migrations.
    alembic_ini_path = pathlib.Path(__file__).resolve().parent.parent / "alembic.ini"
    config = Config(str(alembic_ini_path))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    _ensure_test_database_exists()
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    _run_migrations()
    # A defensive wipe at session start, in case a previous run was
    # interrupted mid-test and left rows behind.
    truncate_all()
    yield
