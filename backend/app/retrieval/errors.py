class RetrievalError(Exception):
    """Base class for retrieval/search failures."""


class EmptyQueryError(RetrievalError):
    pass


class QueryTooLongError(RetrievalError):
    pass
