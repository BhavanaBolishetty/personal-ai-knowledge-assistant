from app.embeddings.errors import EmbeddingError


class GeminiEmbeddingProvider:
    """Wraps Gemini's remote embedding API (gemini-embedding-001) behind
    the EmbeddingProvider interface. Unlike LocalEmbeddingProvider, this
    has no local model to load — no torch, no ~370MB resident memory —
    which is why it's the production default (see EMBEDDING_PROVIDER in
    config.py). Each embed() call is a network request instead of local
    computation.

    The Gemini client is created lazily on first use (not at import or
    construction time), matching GeminiProvider's pattern in
    app/llm/gemini.py — importing this module never fails just because no
    API key is configured yet.
    """

    def __init__(self, model_name: str, api_key: str, dimension: int, batch_size: int):
        self.model_name = model_name
        self.api_key = api_key
        self.dimension = dimension
        self.batch_size = batch_size
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        if not self.api_key:
            raise EmbeddingError(
                "GEMINI_API_KEY is not configured. Set it in your .env file to enable embeddings."
            )

        try:
            from google import genai
        except ImportError as exc:
            raise EmbeddingError("google-genai is not installed.") from exc

        self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _call_embed_content(self, texts: list[str], task_type: str):
        """Isolated seam for the actual API call, so tests can substitute
        a fake response without mocking the google-genai SDK itself."""
        client = self._get_client()

        try:
            from google.genai import types
        except ImportError as exc:
            raise EmbeddingError("google-genai is not installed.") from exc

        return client.models.embed_content(
            model=self.model_name,
            contents=texts,
            # RETRIEVAL_DOCUMENT vs RETRIEVAL_QUERY: Gemini's embedding
            # model produces different (asymmetric) vectors depending on
            # which side of a search a text is on — using the matching
            # task_type for chunks-being-stored vs a query-being-searched
            # is Google's documented recommendation for RAG and measurably
            # improves retrieval quality over embedding both the same way.
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dimension),
        )

    def embed(self, texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        if not texts:
            return []

        try:
            response = self._call_embed_content(texts, task_type)
        except EmbeddingError:
            raise
        except Exception as exc:
            raise _translate_embedding_error(exc) from exc

        embeddings = getattr(response, "embeddings", None) or []
        vectors = [list(item.values) for item in embeddings]

        # gemini-embedding-001 returns one embedding per input string when
        # given a list (unlike some other Gemini embedding models, which
        # can aggregate a list into a single embedding) — verified against
        # the API docs, but checked here too rather than assumed, since a
        # silent mismatch would corrupt which vector maps to which chunk.
        if len(vectors) != len(texts):
            raise EmbeddingError(
                f"Expected {len(texts)} embeddings from Gemini but received {len(vectors)}."
            )

        for vector in vectors:
            if len(vector) != self.dimension:
                raise EmbeddingError(
                    f"Gemini embedding model '{self.model_name}' returned a "
                    f"{len(vector)}-dimensional vector, but GEMINI_EMBEDDING_DIMENSION is "
                    f"set to {self.dimension}. Update GEMINI_EMBEDDING_DIMENSION (and recreate "
                    "the chunks.embedding column) to match."
                )

        return vectors


def _translate_embedding_error(exc: Exception) -> EmbeddingError:
    """Maps a Gemini SDK exception to a clean EmbeddingError message.
    Deliberately never includes the original exception's text — mirrors
    app/llm/gemini.py's _translate_gemini_error for the same reason: only
    used here to decide *which* clean message to raise, so nothing from
    the SDK reaches an API response.
    """
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    lowered = str(exc).lower()

    if status_code == 429 or "rate limit" in lowered or "resource_exhausted" in lowered or "quota" in lowered:
        return EmbeddingError("The embedding service is temporarily rate-limited. Please try again in a moment.")

    if isinstance(exc, TimeoutError) or "timeout" in lowered or "deadline" in lowered:
        return EmbeddingError("The embedding service took too long to respond. Please try again.")

    return EmbeddingError("The embedding service is temporarily unavailable. Please try again shortly.")
