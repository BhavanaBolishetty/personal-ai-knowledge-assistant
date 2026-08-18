from app.core.config import settings
from app.embeddings.local import LocalEmbeddingProvider

# The single provider instance the rest of the app depends on. Swapping to a
# different provider later (e.g. a remote API) means changing this line, not
# every caller — callers only ever import embed_texts from this module.
_provider = LocalEmbeddingProvider(
    model_name=settings.embedding_model_name,
    expected_dimension=settings.embedding_dimension,
    batch_size=settings.embedding_batch_size,
)


def embed_texts(texts: list[str]) -> list[list[float]]:
    return _provider.embed(texts)
