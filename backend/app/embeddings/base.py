from typing import Protocol


class EmbeddingProvider(Protocol):
    """Minimal interface the rest of the app depends on. LocalEmbeddingProvider
    is the only implementation for now. A remote/paid API provider could be
    added later (e.g. app/embeddings/remote.py) behind this same interface
    without changing any caller — only app/embeddings/service.py would need
    to point at it.
    """

    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...
