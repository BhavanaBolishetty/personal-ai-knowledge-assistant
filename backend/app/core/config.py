import os

from dotenv import load_dotenv

load_dotenv()

_LOCAL_EMBEDDING_MODEL_DEFAULT = "all-MiniLM-L6-v2"
_LOCAL_EMBEDDING_DIMENSION_DEFAULT = 384
# 768 is Google's smallest officially recommended output_dimensionality for
# gemini-embedding-001 (it supports 128-3072 via Matryoshka Representation
# Learning, truncated + renormalized server-side) — a meaningful quality
# upgrade over all-MiniLM-L6-v2's 384 dimensions, while keeping pgvector
# storage/comparison cost reasonable. Verified against Gemini API docs.
_GEMINI_EMBEDDING_MODEL_DEFAULT = "gemini-embedding-001"
_GEMINI_EMBEDDING_DIMENSION_DEFAULT = 768


def _resolve_embedding_config(provider: str) -> tuple[str, int]:
    """Returns (model_name, dimension) for the given embedding provider.

    Deliberately uses provider-scoped env var names (LOCAL_EMBEDDING_* /
    GEMINI_EMBEDDING_*) rather than one shared EMBEDDING_MODEL_NAME /
    EMBEDDING_DIMENSION pair. A shared name is a trap: a value set for one
    provider (e.g. in a .env file that predates EMBEDDING_PROVIDER
    existing at all) silently applies to the other provider too, since
    os.getenv(key, default) only uses `default` when the key is fully
    absent — not when it "belongs" to the wrong provider. That's exactly
    how a production backfill run ended up sending
    model="all-MiniLM-L6-v2" to the Gemini API and failed with "400
    INVALID_ARGUMENT: unexpected model name format". Provider-scoped
    names make that class of bug structurally impossible: there is no
    longer any env var name both providers could accidentally share.
    """
    if provider == "gemini":
        model_name = os.getenv("GEMINI_EMBEDDING_MODEL_NAME", _GEMINI_EMBEDDING_MODEL_DEFAULT)
        dimension = int(os.getenv("GEMINI_EMBEDDING_DIMENSION", str(_GEMINI_EMBEDDING_DIMENSION_DEFAULT)))
    else:
        model_name = os.getenv("LOCAL_EMBEDDING_MODEL_NAME", _LOCAL_EMBEDDING_MODEL_DEFAULT)
        dimension = int(os.getenv("LOCAL_EMBEDDING_DIMENSION", str(_LOCAL_EMBEDDING_DIMENSION_DEFAULT)))
    return model_name, dimension


class Settings:
    # "development" (default) keeps local Docker/host behavior unchanged
    # (e.g. uvicorn --reload). Set to "production" in Render.
    environment = os.getenv("ENVIRONMENT", "development")

    postgres_user = os.getenv("POSTGRES_USER", "paika_user")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "paika_password")
    postgres_db = os.getenv("POSTGRES_DB", "paika_knowledge_base")
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    # Managed Postgres providers (e.g. Neon) hand out one connection string
    # instead of separate user/password/host/db parts. When set, this takes
    # priority over the POSTGRES_* parts above; local dev leaves it unset
    # and keeps building the URL from those parts as before.
    database_url_override = os.getenv("DATABASE_URL", "")

    # Comma-separated list of origins allowed to call this API with
    # credentials. Defaults to the local Vite dev server so `docker compose
    # up` / running the backend on the host keeps working with no .env
    # change. Production sets this to the deployed frontend's real origin.
    allowed_origins = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    storage_dir = os.getenv("STORAGE_DIR", "storage/uploads")
    max_upload_size_bytes = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024)))

    # "local" (default) keeps using disk storage under storage_dir, exactly
    # as before — no behavior change for local dev/Docker. "r2" switches to
    # Cloudflare R2 (S3-compatible) so uploads survive Render's ephemeral
    # filesystem in production. See app/storage/r2.py.
    storage_backend = os.getenv("STORAGE_BACKEND", "local")
    r2_account_id = os.getenv("R2_ACCOUNT_ID", "")
    r2_access_key_id = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY", "")
    r2_bucket_name = os.getenv("R2_BUCKET_NAME", "")
    # Usually derived from the account id; only set this to override
    # (e.g. a custom S3-compatible endpoint).
    r2_endpoint_url = os.getenv("R2_ENDPOINT_URL", "") or (
        f"https://{os.getenv('R2_ACCOUNT_ID', '')}.r2.cloudflarestorage.com"
        if os.getenv("R2_ACCOUNT_ID")
        else ""
    )

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

    # Embeddings. "local" (default) uses sentence-transformers'
    # "all-MiniLM-L6-v2" — small (~80MB), free, CPU-friendly, no API key —
    # a good fit for local dev, but loading torch + the model itself adds
    # ~370MB of resident memory, which doesn't fit Render's free-tier
    # 512MB backend (confirmed by direct measurement — see memory
    # investigation notes). "gemini" switches to Gemini's remote embedding
    # API (app/embeddings/remote.py): no local model, no torch, at the
    # cost of a network call per embed and Gemini API quota usage instead
    # of unlimited local compute. Same GEMINI_API_KEY already used for
    # answer generation — no separate credential needed.
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "local")

    # See _resolve_embedding_config's docstring above for why this isn't
    # two plain os.getenv(...) calls on a shared env var name. This is
    # used to size the "chunks.embedding" pgvector column, so it must
    # match whatever the active provider actually returns — both
    # LocalEmbeddingProvider and GeminiEmbeddingProvider additionally
    # verify this against the real output at call time and raise loudly
    # on a mismatch, rather than silently storing the wrong width.
    embedding_model_name, embedding_dimension = _resolve_embedding_config(embedding_provider)

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
    # out before they ever reach the context sent to Gemini.
    #
    # Deliberately provider-scoped (LOCAL_MIN_RELEVANCE_SCORE /
    # GEMINI_MIN_RELEVANCE_SCORE), not a single shared MIN_RELEVANCE_SCORE
    # — the same lesson as embedding_model_name/embedding_dimension above.
    # Different embedding models produce differently-shaped similarity
    # score distributions, so a threshold tuned for one is not valid for
    # the other, and a shared name would silently misapply whichever
    # value happened to be set to the wrong provider.
    #
    # LOCAL default (0.3): calibrated empirically against
    # all-MiniLM-L6-v2 — querying a real mixed-topic knowledge base
    # (binary-search and load-balancing documents), genuinely on-topic
    # matches scored 0.45-0.85, off-topic scored 0.05-0.30. 0.3 sits in
    # that gap with margin on both sides.
    #
    # GEMINI default (0.55): calibrated empirically against
    # gemini-embedding-001 in production — querying real production
    # documents with several genuinely off-topic questions (different
    # domains, no lexical overlap), off-topic scored 0.41-0.47 even
    # though nothing matched, while a genuinely on-topic query scored
    # 0.72-0.76. Gemini's embedding space evidently has a higher baseline
    # similarity floor than MiniLM's — reusing 0.3 here would let clearly
    # irrelevant chunks through. 0.55 sits in the observed gap with
    # margin on both sides, same methodology as the LOCAL calibration.
    if embedding_provider == "gemini":
        min_relevance_score = float(os.getenv("GEMINI_MIN_RELEVANCE_SCORE", "0.55"))
    else:
        min_relevance_score = float(os.getenv("LOCAL_MIN_RELEVANCE_SCORE", "0.3"))

    # Answer generation (Milestone 6). "gemini-2.5-flash" was the original
    # pick here — Google's lightweight, fast, free-tier-eligible model at
    # the time — but Google retired it for accounts created after some
    # date ("no longer available to new users", confirmed via a live 404
    # from the API itself, not assumed). "gemini-3.6-flash" is the exact
    # replacement Gemini's own error message named, and confirmed stable
    # (not preview) in the current model list. Configurable so a
    # newer/different model can be swapped in via .env without any code
    # change — this is exactly that kind of swap.
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

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

    # Auth. Signs/verifies JWTs handed out on login/signup (app/core/security.py).
    # Empty-string default matches gemini_api_key above — the app should fail
    # loudly (see security.py) rather than silently sign tokens with an empty
    # key if this was never configured, not crash at import time.
    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "")
    jwt_algorithm = "HS256"
    # 7 days: long enough that a personal-project user isn't annoyed by
    # constant re-logins, short enough that a leaked token doesn't stay valid
    # indefinitely. No refresh-token flow — a flat expiry is a fine tradeoff
    # here; refresh-token rotation/revocation is real complexity this
    # project's scale doesn't need.
    jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", str(7 * 24 * 60)))

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            # Neon (and most managed Postgres) connection strings use the
            # plain "postgresql://" scheme; SQLAlchemy needs the psycopg2
            # driver named explicitly.
            url = self.database_url_override
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg2://", 1)
            # Neon requires TLS; add it if the connection string didn't
            # already specify sslmode (e.g. a local override wouldn't).
            if "sslmode=" not in url:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}sslmode=require"
            return url

        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
