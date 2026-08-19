import pytest

from app.embeddings.errors import EmbeddingError
from app.embeddings.remote import GeminiEmbeddingProvider, _translate_embedding_error


class _FakeEmbedding:
    def __init__(self, values):
        self.values = values


class _FakeResponse:
    def __init__(self, vectors):
        self.embeddings = [_FakeEmbedding(v) for v in vectors]


def _provider(dimension=768):
    return GeminiEmbeddingProvider(
        model_name="gemini-embedding-001", api_key="fake-key", dimension=dimension, batch_size=16
    )


def test_empty_input_list_is_handled_safely():
    provider = _provider()
    assert provider.embed([]) == []


def test_embed_returns_one_vector_per_text(monkeypatch):
    provider = _provider(dimension=3)
    monkeypatch.setattr(
        provider, "_call_embed_content", lambda texts, task_type: _FakeResponse([[0.1, 0.2, 0.3]] * len(texts))
    )

    vectors = provider.embed(["a", "b", "c"])
    assert len(vectors) == 3
    assert all(len(v) == 3 for v in vectors)


def test_default_task_type_is_retrieval_document(monkeypatch):
    provider = _provider(dimension=3)
    captured = {}

    def _fake_call(texts, task_type):
        captured["task_type"] = task_type
        return _FakeResponse([[0.1, 0.2, 0.3] for _ in texts])

    monkeypatch.setattr(provider, "_call_embed_content", _fake_call)
    provider.embed(["some text"])
    assert captured["task_type"] == "RETRIEVAL_DOCUMENT"


def test_explicit_task_type_is_forwarded(monkeypatch):
    provider = _provider(dimension=3)
    captured = {}

    def _fake_call(texts, task_type):
        captured["task_type"] = task_type
        return _FakeResponse([[0.1, 0.2, 0.3] for _ in texts])

    monkeypatch.setattr(provider, "_call_embed_content", _fake_call)
    provider.embed(["a query"], task_type="RETRIEVAL_QUERY")
    assert captured["task_type"] == "RETRIEVAL_QUERY"


def test_dimension_mismatch_raises_embedding_error(monkeypatch):
    provider = _provider(dimension=768)
    # API returns a 3-dim vector, but the column is configured for 768 —
    # must be caught here, not silently stored at the wrong width.
    monkeypatch.setattr(provider, "_call_embed_content", lambda texts, task_type: _FakeResponse([[0.1, 0.2, 0.3]]))

    with pytest.raises(EmbeddingError, match="768"):
        provider.embed(["one text"])


def test_vector_count_mismatch_raises_embedding_error(monkeypatch):
    provider = _provider(dimension=3)
    # Two texts in, only one embedding back — would silently misalign
    # chunk-to-vector mapping if not caught.
    monkeypatch.setattr(
        provider, "_call_embed_content", lambda texts, task_type: _FakeResponse([[0.1, 0.2, 0.3]])
    )

    with pytest.raises(EmbeddingError, match="Expected 2"):
        provider.embed(["first", "second"])


def test_missing_api_key_raises_embedding_error():
    provider = GeminiEmbeddingProvider(model_name="gemini-embedding-001", api_key="", dimension=768, batch_size=16)
    with pytest.raises(EmbeddingError, match="GEMINI_API_KEY"):
        provider.embed(["some text"])


def test_unexpected_exception_is_translated_not_leaked(monkeypatch):
    provider = _provider(dimension=768)

    def _raise(texts, task_type):
        raise Exception("secret internal detail that should never leak, key=abc123")

    monkeypatch.setattr(provider, "_call_embed_content", _raise)

    with pytest.raises(EmbeddingError) as exc_info:
        provider.embed(["some text"])
    assert "secret internal detail" not in str(exc_info.value)
    assert "abc123" not in str(exc_info.value)


def test_rate_limit_error_produces_user_friendly_message():
    exc = _translate_embedding_error(Exception("429 RESOURCE_EXHAUSTED: quota exceeded"))
    assert isinstance(exc, EmbeddingError)
    assert "rate-limited" in str(exc)


def test_timeout_error_produces_user_friendly_message():
    exc = _translate_embedding_error(TimeoutError("deadline exceeded"))
    assert isinstance(exc, EmbeddingError)
    assert "took too long" in str(exc)


def test_generic_error_produces_user_friendly_message():
    exc = _translate_embedding_error(Exception("some unexpected internal failure"))
    assert isinstance(exc, EmbeddingError)
    assert "temporarily unavailable" in str(exc)
