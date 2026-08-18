from app.core.config import settings
from app.retrieval.errors import EmptyQueryError, QueryTooLongError


def validate_query(query: str) -> str:
    query = (query or "").strip()

    if not query:
        raise EmptyQueryError("Query cannot be empty.")

    if len(query) > settings.max_query_length_chars:
        raise QueryTooLongError(
            f"Query exceeds the maximum length of {settings.max_query_length_chars} characters."
        )

    return query
