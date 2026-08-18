from app.core.config import settings
from app.embeddings import embed_texts


def test_embedding_generation_for_one_text():
    vectors = embed_texts(["Retrieval augmented generation grounds answers in real documents."])
    assert len(vectors) == 1
    assert len(vectors[0]) == settings.embedding_dimension


def test_multiple_texts_produce_multiple_vectors():
    texts = [
        "Chunking splits documents into smaller pieces.",
        "Embeddings turn text into vectors for semantic search.",
        "pgvector stores and searches those vectors inside Postgres.",
    ]
    vectors = embed_texts(texts)
    assert len(vectors) == len(texts)
    assert all(len(v) == settings.embedding_dimension for v in vectors)


def test_empty_input_list_is_handled_safely():
    assert embed_texts([]) == []


def test_whitespace_only_text_does_not_crash():
    vectors = embed_texts(["   "])
    assert len(vectors) == 1
    assert len(vectors[0]) == settings.embedding_dimension


def test_vector_dimension_matches_configured_dimension():
    vectors = embed_texts(["dimension check"])
    assert len(vectors[0]) == settings.embedding_dimension


def test_same_input_produces_consistent_embedding():
    text = "The same input should always produce the same embedding."
    first = embed_texts([text])[0]
    second = embed_texts([text])[0]
    assert first == second
