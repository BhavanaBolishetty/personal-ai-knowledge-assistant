from app.embeddings.errors import EmbeddingError


class LocalEmbeddingProvider:
    """Wraps a local sentence-transformers model behind the EmbeddingProvider
    interface. The model is loaded lazily on first use (not at import time)
    so importing this module — e.g. during test collection — never triggers
    a model download or load unless embeddings are actually generated.
    """

    def __init__(self, model_name: str, expected_dimension: int, batch_size: int):
        self.model_name = model_name
        self.expected_dimension = expected_dimension
        self.batch_size = batch_size
        self.dimension = expected_dimension
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError("sentence-transformers is not installed.") from exc

        try:
            model = SentenceTransformer(self.model_name)
        except Exception as exc:
            raise EmbeddingError(
                f"Could not load embedding model '{self.model_name}': {exc}"
            ) from exc

        # Verified programmatically from the model's real output, not
        # assumed — the whole point of this check is to catch a mismatch
        # between EMBEDDING_DIMENSION and the actual model before any
        # vector gets stored in the fixed-width pgvector column.
        probe = model.encode(["dimension probe"], convert_to_numpy=True)
        actual_dimension = int(probe.shape[-1])
        if actual_dimension != self.expected_dimension:
            raise EmbeddingError(
                f"Embedding model '{self.model_name}' produces {actual_dimension}-dimensional "
                f"vectors, but EMBEDDING_DIMENSION is set to {self.expected_dimension}. "
                "Update EMBEDDING_DIMENSION (and recreate the chunks.embedding column) to match."
            )

        self._model = model
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._load_model()
        try:
            vectors = model.encode(
                texts,
                batch_size=self.batch_size,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingError(f"Failed to generate embeddings: {exc}") from exc

        return vectors.tolist()
