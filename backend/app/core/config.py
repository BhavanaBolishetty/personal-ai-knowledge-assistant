import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    postgres_user = os.getenv("POSTGRES_USER", "paika_user")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "paika_password")
    postgres_db = os.getenv("POSTGRES_DB", "paika_knowledge_base")
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")

    storage_dir = os.getenv("STORAGE_DIR", "storage/uploads")
    max_upload_size_bytes = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024)))

    # URL ingestion (SSRF-conscious). Small, conservative defaults: a
    # personal knowledge base fetching articles/blog posts, not a general
    # web crawler.
    url_fetch_timeout_seconds = float(os.getenv("URL_FETCH_TIMEOUT_SECONDS", "10"))
    max_url_response_bytes = int(os.getenv("MAX_URL_RESPONSE_BYTES", str(5 * 1024 * 1024)))
    max_url_redirects = int(os.getenv("MAX_URL_REDIRECTS", "5"))

    # Chunking (Milestone 3). The embedding model planned for the next
    # milestone (sentence-transformers "all-MiniLM-L6-v2") truncates its
    # input at 256 word-piece tokens — roughly 1000-1100 characters of
    # English text at ~4.3 characters/token. CHUNK_SIZE_CHARS is kept
    # comfortably under that so a chunk is never silently truncated when
    # it's embedded later. CHUNK_OVERLAP_CHARS is ~15% of the chunk size:
    # enough that a sentence spanning a chunk boundary still has
    # surrounding context in the next chunk, without the heavy duplication
    # a larger overlap (e.g. 50%) would cause across a whole document.
    chunk_size_chars = int(os.getenv("CHUNK_SIZE_CHARS", "1000"))
    chunk_overlap_chars = int(os.getenv("CHUNK_OVERLAP_CHARS", "150"))

    # Embeddings (Milestone 4). "all-MiniLM-L6-v2" is a small (~80MB), free,
    # CPU-friendly sentence-transformers model: no paid API key, no GPU
    # needed, and fast enough to embed a document's chunks in well under a
    # second on a laptop CPU. Trade-off: lower retrieval quality than a
    # larger model (e.g. all-mpnet-base-v2) or a paid API embedding — an
    # acceptable starting point, swappable later behind EmbeddingProvider.
    #
    # EMBEDDING_DIMENSION=384 was confirmed by loading the model and
    # checking the actual shape of its output (not guessed). It is used to
    # size the "chunks.embedding" pgvector column, so it must be updated
    # (and that column re-created) if the model ever changes.
    # LocalEmbeddingProvider re-checks this at load time and raises loudly
    # if the model's real output size doesn't match.
    embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    embedding_dimension = int(os.getenv("EMBEDDING_DIMENSION", "384"))

    # sentence-transformers encodes a batch of texts in one vectorized
    # forward pass, which is far faster than one call per chunk. 32 is a
    # reasonable default for CPU inference: large enough to benefit from
    # batching, small enough to keep memory bounded for a personal
    # knowledge base where most documents will have well under 100 chunks.
    embedding_batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

    # Retrieval (Milestone 5). k=5 gives a future answer-generation step a
    # handful of distinct chunks to draw on — enough to cover a question
    # that touches more than one document — without overwhelming it with
    # too much retrieved text. MAX_TOP_K=20 is a hard ceiling so a single
    # request can't pull a large fraction of a small personal knowledge
    # base or return an unreasonably large payload.
    default_top_k = int(os.getenv("DEFAULT_TOP_K", "5"))
    max_top_k = int(os.getenv("MAX_TOP_K", "20"))

    # A query longer than this is rejected outright rather than silently
    # truncated by the embedding model — same practical limit used for
    # CHUNK_SIZE_CHARS above (the model ignores input past ~256 word-piece
    # tokens), so the caller finds out instead of getting an embedding of
    # only part of what they typed.
    max_query_length_chars = int(os.getenv("MAX_QUERY_LENGTH_CHARS", "1000"))

    # A chunk being among the top-K nearest neighbors does not mean it is
    # actually relevant — on a small, mixed-topic knowledge base, an
    # off-topic chunk can still rank in the top few purely from sharing
    # generic wording with the query. min_relevance_score filters those
    # out before they ever reach the context sent to Gemini. Calibrated
    # empirically against this project's embedding model
    # (all-MiniLM-L6-v2), not guessed: querying a real mixed-topic
    # knowledge base (e.g. "Where is load balancing used?" against
    # binary-search and load-balancing documents), genuinely on-topic
    # matches — including loosely-phrased, paraphrased queries — scored
    # 0.45-0.85, while off-topic documents scored 0.05-0.30 even when they
    # shared generic wording with the query. 0.3 sits in that gap with
    # margin on both sides.
    min_relevance_score = float(os.getenv("MIN_RELEVANCE_SCORE", "0.3"))

    # Answer generation (Milestone 6). "gemini-2.5-flash" is Google's
    # lightweight, fast Gemini model — confirmed free-tier eligible, with a
    # generous free daily request quota, which matters since this is a
    # personal project. Same reasoning as picking a small local embedding
    # model in Milestone 4: appropriate for this project's scale, not a
    # guess. Configurable so a newer/different model can be swapped in via
    # .env without any code change.
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Bounds how much retrieved text is sent to Gemini per question. Gemini's
    # own context window is far larger than this, so the limit isn't about
    # avoiding a model error — it keeps each request focused (a large,
    # unfocused context tends to produce vaguer answers), keeps latency and
    # free-tier quota usage predictable, and is a natural fit given chunks
    # are already ~1000-1150 characters each (Milestone 3): 8000 comfortably
    # fits the default top_k=5 results with room to spare, or roughly 6-8
    # chunks if a caller requests more.
    max_context_chars = int(os.getenv("MAX_CONTEXT_CHARS", "8000"))

    # Conversational RAG. Bounds how many recent messages (user+assistant
    # combined) are used both for follow-up query condensing and shown to
    # Gemini as conversation context — 6 messages is 3 back-and-forth
    # turns, enough for pronoun/reference resolution ("its", "that")
    # without letting the prompt grow unbounded as a conversation gets
    # long. Older messages stay in the database and are still visible when
    # the conversation is reopened; they just stop influencing new answers.
    conversation_history_limit = int(os.getenv("CONVERSATION_HISTORY_LIMIT", "6"))

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
