from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    """Minimal interface for saving and reading uploaded file bytes.

    LocalFileStorage is the only implementation for now. A cloud object
    storage backend (e.g. S3-compatible) can be added later behind this
    same interface without changing any caller.
    """

    def save(self, relative_path: str, content: bytes) -> str: ...

    def read_bytes(self, relative_path: str) -> bytes: ...

    def delete(self, relative_path: str) -> None: ...

    def path(self, relative_path: str) -> Path: ...

    def exists(self, relative_path: str) -> bool: ...
