from typing import Protocol


class EmbeddingProvider(Protocol):
    """Minimal interface the rest of the app depends on.
    LocalEmbeddingProvider (sentence-transformers, local dev default) and
    GeminiEmbeddingProvider (app/embeddings/remote.py, production default)
    both implement this — only app/embeddings/service.py knows which one
    is active.
    """

    dimension: int

    def embed(self, texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]: ...
