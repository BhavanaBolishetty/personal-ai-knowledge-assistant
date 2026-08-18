from pathlib import Path

from app.core.config import settings


class LocalFileStorage:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        destination = (self.base_dir / relative_path).resolve()
        if not destination.is_relative_to(self.base_dir):
            raise ValueError("Invalid storage path.")
        return destination

    def save(self, relative_path: str, content: bytes) -> str:
        destination = self._resolve(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return relative_path

    def read_bytes(self, relative_path: str) -> bytes:
        return self._resolve(relative_path).read_bytes()

    def delete(self, relative_path: str) -> None:
        # Best-effort: a document's DB row should not become undeletable
        # just because its file was already missing on disk.
        self._resolve(relative_path).unlink(missing_ok=True)

    def path(self, relative_path: str) -> Path:
        # For FileResponse, which streams straight from disk (supporting
        # HTTP Range requests, ETag, Last-Modified) rather than loading
        # the whole file into memory first.
        return self._resolve(relative_path)

    def exists(self, relative_path: str) -> bool:
        return self._resolve(relative_path).is_file()


storage = LocalFileStorage(Path(settings.storage_dir))
