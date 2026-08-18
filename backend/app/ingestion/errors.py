class IngestionError(Exception):
    """Base class for upload validation failures."""


class UnsupportedFileTypeError(IngestionError):
    pass


class EmptyFileError(IngestionError):
    pass


class FileTooLargeError(IngestionError):
    pass


class InvalidURLError(IngestionError):
    """The URL itself is malformed, disallowed, or points at a
    private/internal address — rejected before any network request."""


class URLFetchError(IngestionError):
    """The URL was valid to attempt, but fetching it failed (unreachable,
    blocked, timed out, or too large)."""
