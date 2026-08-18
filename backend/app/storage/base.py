from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    """Minimal interface for saving and reading uploaded file bytes.

    Two implementations exist: LocalFileStorage (disk, used for local dev
    and Docker) and R2Storage (Cloudflare R2, used in production so
    uploads survive a redeploy instead of living on Render's ephemeral
    filesystem). Callers only depend on this interface.
    """

    def save(self, relative_path: str, content: bytes) -> str: ...

    def read_bytes(self, relative_path: str) -> bytes: ...

    def delete(self, relative_path: str) -> None: ...

    def path(self, relative_path: str) -> Path: ...

    def exists(self, relative_path: str) -> bool: ...

    def serving_url(
        self, relative_path: str, *, filename: str, content_type: str, disposition: str
    ) -> str | None:
        """Returns a URL the client can be redirected to for direct
        download/viewing, or None if the file should instead be streamed
        from this server (e.g. FileResponse over a local path).
        """
        ...
