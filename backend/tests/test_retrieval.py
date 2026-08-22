import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def upload(filename, content, content_type="text/plain"):
    return client.post(
        "/documents",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


def search(query, top_k=None, **kwargs):
    payload = {"query": query}
    if top_k is not None:
        payload["top_k"] = top_k
    payload.update(kwargs)
    return client.post("/search", json=payload)


def test_empty_query_is_rejected():
    response = search("")
    assert response.status_code == 400


def test_whitespace_only_query_is_rejected():
    response = search("    \n\t  ")
    assert response.status_code == 400


def test_excessively_long_query_is_rejected():
    response = search("word " * 500)  # far past MAX_QUERY_LENGTH_CHARS
    assert response.status_code == 400


def test_missing_query_field_returns_422_not_a_crash():
    response = client.post("/search", json={"top_k": 5})
    assert response.status_code == 422


def test_top_k_zero_is_rejected():
    response = search("a reasonable question", top_k=0)
    assert response.status_code == 422


def test_top_k_above_maximum_is_rejected():
    response = search("a reasonable question", top_k=10_000)
    assert response.status_code == 422


def test_query_embedding_uses_the_shared_embedding_function(monkeypatch):
    import app.retrieval.service as service_module

    calls = []
    original_embed_texts = service_module.embed_texts

    def _spy_embed_texts(texts, **kwargs):
        calls.append(list(texts))
        return original_embed_texts(texts, **kwargs)

    monkeypatch.setattr(service_module, "embed_texts", _spy_embed_texts)

    response = search("does retrieval reuse the same embedding function")
    assert response.status_code == 200

    # Same app.embeddings.embed_texts function used for chunks — there is
    # only one such function in the app, so this proves the query was
    # embedded with the identical model and configuration as documents.
    assert calls == [["does retrieval reuse the same embedding function"]]


def test_results_never_include_raw_embeddings():
    upload("embedding-leak-check.txt", b"Some content about caches and databases.", "text/plain")

    response = search("caches and databases")
    assert response.status_code == 200
    body = response.json()
    assert body["results"], "expected at least one result to check for leaks"
    for result in body["results"]:
        assert "embedding" not in result
        assert "vector" not in result


def test_results_contain_expected_metadata_fields():
    upload_response = upload(
        "metadata-check.txt", b"Content used to verify search result metadata fields.", "text/plain"
    )
    document_id = upload_response.json()["id"]

    response = search("verify search result metadata fields")
    assert response.status_code == 200
    results = response.json()["results"]
    assert results

    matching = [r for r in results if r["document_id"] == document_id]
    assert matching, "expected the just-uploaded document to appear in results"
    result = matching[0]
    assert result["original_filename"] == "metadata-check.txt"
    assert result["source_type"] == "text"
    assert result["chunk_index"] == 0
    assert result["page_number"] is None
    assert isinstance(result["similarity_score"], float)
    assert isinstance(result["character_count"], int)


def test_results_are_ordered_by_similarity_descending():
    upload("ordering-check-a.txt", b"Apples are a sweet, crunchy fruit that grow on trees.", "text/plain")
    upload("ordering-check-b.txt", b"Quantum computers use qubits instead of classical bits.", "text/plain")
    upload("ordering-check-c.txt", b"Fruit orchards often grow apples, pears, and cherries.", "text/plain")

    response = search("sweet fruit grown on trees", top_k=10)
    assert response.status_code == 200
    scores = [r["similarity_score"] for r in response.json()["results"]]
    assert scores == sorted(scores, reverse=True)


def test_top_k_is_respected():
    for i in range(6):
        upload(f"topk-check-{i}.txt", f"Document number {i} about miscellaneous topics.".encode(), "text/plain")

    response = search("miscellaneous topics", top_k=3)
    assert response.status_code == 200
    body = response.json()
    assert body["top_k"] == 3
    assert len(body["results"]) <= 3


def test_empty_knowledge_base_returns_clean_response(monkeypatch):
    import app.retrieval.service as service_module

    monkeypatch.setattr(service_module, "search_chunks", lambda db, embedding, top_k, user_id: [])

    response = search("anything at all, nothing should match")
    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["result_count"] == 0


def test_embedding_model_failure_returns_clean_error(monkeypatch):
    import app.retrieval.service as service_module
    from app.embeddings import EmbeddingError

    def _broken_embed_texts(texts, **kwargs):
        raise EmbeddingError("simulated embedding backend failure")

    monkeypatch.setattr(service_module, "embed_texts", _broken_embed_texts)

    response = search("this should fail cleanly")
    assert response.status_code == 503
    assert "simulated embedding backend failure" not in response.text


def test_database_failure_returns_clean_error(monkeypatch):
    import app.retrieval.service as service_module
    from sqlalchemy.exc import OperationalError

    def _broken_search_chunks(db, embedding, top_k, user_id):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(service_module, "search_chunks", _broken_search_chunks)

    response = search("this should also fail cleanly")
    assert response.status_code == 503
    assert "connection refused" not in response.text


def test_min_relevance_score_excludes_off_topic_matches():
    # Real embeddings, real documents, genuinely unrelated topics — a
    # top-K search should not surface a document just because it made the
    # cut numerically; it must also clear settings.min_relevance_score.
    upload(
        "relevance-topic-cooking.txt",
        b"A recipe for baking sourdough bread requires flour, water, salt, and a starter culture.",
        "text/plain",
    )
    upload(
        "relevance-topic-astronomy.txt",
        b"Neutron stars are the collapsed core of a massive star, incredibly dense and compact.",
        "text/plain",
    )

    response = search("How do you bake sourdough bread at home?", top_k=5)
    assert response.status_code == 200
    filenames = [r["original_filename"] for r in response.json()["results"]]
    assert "relevance-topic-cooking.txt" in filenames
    assert "relevance-topic-astronomy.txt" not in filenames


def test_all_returned_results_meet_minimum_relevance_score():
    from app.core.config import settings

    upload(
        "relevance-min-score-check.txt",
        b"Distinct relevance threshold verification content about a specific narrow subject.",
        "text/plain",
    )

    response = search("distinct relevance threshold verification content", top_k=10)
    assert response.status_code == 200
    for result in response.json()["results"]:
        assert result["similarity_score"] >= settings.min_relevance_score
