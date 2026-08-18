from pathlib import Path

from app.core.config import settings
from app.storage.local import LocalFileStorage


def _build_storage():
    if settings.storage_backend == "r2":
        from app.storage.r2 import R2Storage

        return R2Storage(
            bucket_name=settings.r2_bucket_name,
            endpoint_url=settings.r2_endpoint_url,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
        )
    return LocalFileStorage(Path(settings.storage_dir))


storage = _build_storage()

__all__ = ["storage"]
