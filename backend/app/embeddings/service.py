from app.core.config import settings
from app.embeddings.local import LocalEmbeddingProvider


def _build_provider():
    if settings.embedding_provider == "gemini":
        from app.embeddings.remote import GeminiEmbeddingProvider

        return GeminiEmbeddingProvider(
            model_name=settings.embedding_model_name,
            api_key=settings.gemini_api_key,
            dimension=settings.embedding_dimension,
            batch_size=settings.embedding_batch_size,
        )
    return LocalEmbeddingProvider(
        model_name=settings.embedding_model_name,
        expected_dimension=settings.embedding_dimension,
        batch_size=settings.embedding_batch_size,
    )


# The single provider instance the rest of the app depends on. Swapping to a
# different provider means changing EMBEDDING_PROVIDER, not every caller —
# callers only ever import embed_texts from this module. Neither provider
# does any real work at construction time (both load lazily on first
# embed() call), so this is safe to build eagerly at import time.
_provider = _build_provider()


def embed_texts(texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """task_type distinguishes embedding text that will be stored and
    searched later (RETRIEVAL_DOCUMENT, the default — used for document
    chunks) from embedding a user's search query (RETRIEVAL_QUERY — see
    app/retrieval/service.py). Only GeminiEmbeddingProvider uses this;
    LocalEmbeddingProvider ignores it.
    """
    return _provider.embed(texts, task_type=task_type)
