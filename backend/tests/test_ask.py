import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def upload(filename, content, content_type="text/plain"):
    return client.post(
        "/documents",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


def ask(query, top_k=None, **kwargs):
    payload = {"query": query}
    if top_k is not None:
        payload["top_k"] = top_k
    payload.update(kwargs)
    return client.post("/ask", json=payload)


def test_valid_question_produces_an_answer(monkeypatch):
    import app.synthesis.service as service_module

    upload(
        "ask-basic.txt",
        b"Binary search runs in logarithmic time on sorted arrays.",
        "text/plain",
    )
    monkeypatch.setattr(
        service_module, "generate_answer", lambda **kwargs: "Binary search runs in O(log n) time. [S1]"
    )

    response = ask("What is the time complexity of binary search, per ask-basic.txt?")
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Binary search runs in O(log n) time. [S1]"
    assert body["sources"]
    assert body["retrieved_chunk_count"] >= 1
    assert body["model"]


def test_empty_question_is_rejected():
    response = ask("")
    assert response.status_code == 400


def test_whitespace_only_question_is_rejected():
    response = ask("    ")
    assert response.status_code == 400


def test_retrieval_results_are_passed_to_synthesis(monkeypatch):
    import app.synthesis.service as service_module

    upload(
        "ask-retrieval-check.txt",
        b"Content specifically about caching layers and databases.",
        "text/plain",
    )

    captured_prompts = []

    def _fake_generate_answer(*, system_instruction, prompt):
        captured_prompts.append(prompt)
        return "A generated answer. [S1]"

    monkeypatch.setattr(service_module, "generate_answer", _fake_generate_answer)

    response = ask("Tell me about caching layers and databases")
    assert response.status_code == 200
    assert captured_prompts
    assert "caching layers" in captured_prompts[0].lower()


def test_source_metadata_is_preserved(monkeypatch):
    import app.synthesis.service as service_module

    upload_response = upload(
        "ask-metadata-check.txt",
        b"Metadata preservation content for ask endpoint tests.",
        "text/plain",
    )
    document_id = upload_response.json()["id"]

    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: "Answer referencing [S1].")

    response = ask("metadata preservation content ask endpoint")
    assert response.status_code == 200
    sources = response.json()["sources"]
    matching = [s for s in sources if s["document_id"] == document_id]
    assert matching
    source = matching[0]
    assert source["filename"] == "ask-metadata-check.txt"
    assert source["id"].startswith("S")
    assert "chunk_index" in source
    assert "page_start" in source
    assert "page_end" in source


def test_citation_ids_are_sequential_and_map_to_sources(monkeypatch):
    import app.synthesis.service as service_module

    upload("ask-citation-a.txt", b"First distinct citation mapping test document about topic A.", "text/plain")
    upload("ask-citation-b.txt", b"Second distinct citation mapping test document about topic B.", "text/plain")

    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: "See [S1] and [S2].")

    response = ask("citation mapping test document topic", top_k=2)
    assert response.status_code == 200
    ids = [s["id"] for s in response.json()["sources"]]
    assert ids == [f"S{i + 1}" for i in range(len(ids))]


def test_response_contains_structured_sources_and_no_raw_context(monkeypatch):
    import app.synthesis.service as service_module

    upload("ask-structure-check.txt", b"Structured response content for ask endpoint verification.", "text/plain")
    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: "Structured answer. [S1]")

    response = ask("structured response content ask endpoint")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["sources"], list)
    assert "context" not in body
    assert "embedding" not in response.text
    assert "vector" not in response.text


def test_gemini_failure_is_handled_cleanly(monkeypatch):
    import app.synthesis.service as service_module
    from app.llm import LLMError

    upload("ask-llm-failure.txt", b"Content for testing Gemini failure handling.", "text/plain")

    def _broken_generate_answer(**kwargs):
        raise LLMError("simulated Gemini failure")

    monkeypatch.setattr(service_module, "generate_answer", _broken_generate_answer)

    response = ask("content for testing Gemini failure handling")
    assert response.status_code == 503
    assert response.json()["detail"] == "simulated Gemini failure"


def test_gemini_rate_limit_is_handled_cleanly(monkeypatch):
    import app.synthesis.service as service_module
    from app.llm import LLMRateLimitError

    upload("ask-rate-limit.txt", b"Content for testing Gemini rate limit handling.", "text/plain")

    def _rate_limited(**kwargs):
        raise LLMRateLimitError("Gemini rate limit reached. Please try again shortly.")

    monkeypatch.setattr(service_module, "generate_answer", _rate_limited)

    response = ask("content for testing Gemini rate limit handling")
    assert response.status_code == 429


def test_gemini_timeout_is_handled_cleanly(monkeypatch):
    import app.synthesis.service as service_module
    from app.llm import LLMTimeoutError

    upload("ask-timeout.txt", b"Content for testing Gemini timeout handling.", "text/plain")

    def _timed_out(**kwargs):
        raise LLMTimeoutError("Gemini request timed out. Please try again.")

    monkeypatch.setattr(service_module, "generate_answer", _timed_out)

    response = ask("content for testing Gemini timeout handling")
    assert response.status_code == 504


def test_empty_knowledge_base_does_not_call_gemini(monkeypatch):
    import app.synthesis.service as service_module

    calls = []
    monkeypatch.setattr(
        service_module, "generate_answer", lambda **kwargs: calls.append(1) or "should not be used"
    )
    monkeypatch.setattr(service_module, "search", lambda db, query, top_k: [])

    response = ask("a question with absolutely no matching knowledge base content")
    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert calls == []  # Gemini must not be called when nothing was retrieved


def test_response_never_includes_raw_embeddings_or_api_key(monkeypatch):
    import app.core.config as config_module
    import app.synthesis.service as service_module

    upload("ask-secret-check.txt", b"Content used to verify no secrets leak into responses.", "text/plain")

    fake_key = "FAKE_TEST_GEMINI_KEY_SHOULD_NEVER_APPEAR"
    monkeypatch.setattr(config_module.settings, "gemini_api_key", fake_key)
    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: "Answer without secrets. [S1]")

    response = ask("content used to verify no secrets leak into responses")
    assert response.status_code == 200
    assert fake_key not in response.text
    assert "embedding" not in response.text


def test_context_size_limit_is_respected(monkeypatch):
    import app.core.config as config_module
    import app.synthesis.service as service_module

    monkeypatch.setattr(config_module.settings, "max_context_chars", 500)

    for i in range(5):
        upload(
            f"ask-context-limit-{i}.txt",
            (f"Context limit test document number {i}. " * 20).encode(),
            "text/plain",
        )

    captured_prompts = []

    def _fake_generate_answer(*, system_instruction, prompt):
        captured_prompts.append(prompt)
        return "Answer. [S1]"

    monkeypatch.setattr(service_module, "generate_answer", _fake_generate_answer)

    response = ask("context limit test document", top_k=5)
    assert response.status_code == 200
    assert captured_prompts
    # With a 500-char budget, the prompt should be clearly bounded, not
    # contain all 5 documents' full (20x-repeated) text.
    assert len(captured_prompts[0]) < 3000


def test_uncited_retrieved_source_is_excluded_from_response(monkeypatch):
    import app.synthesis.service as service_module

    upload("ask-cited-a.txt", b"Distinct citation exclusion test content about topic Alpha only.", "text/plain")
    upload("ask-cited-b.txt", b"Distinct citation exclusion test content about topic Beta only.", "text/plain")

    # Both documents get retrieved and handed to Gemini as context (same
    # query text, same relevance), but the mocked answer only cites S1 —
    # the response's sources must reflect only what was actually cited.
    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: "Only about topic Alpha. [S1]")

    response = ask("distinct citation exclusion test content topic", top_k=4)
    assert response.status_code == 200
    sources = response.json()["sources"]
    assert len(sources) == 1
    assert sources[0]["id"] == "S1"


def test_no_relevant_context_gives_honest_answer_without_hallucinating(monkeypatch):
    import app.synthesis.service as service_module

    upload(
        "ask-unrelated-check.txt",
        b"Distinct content about sourdough bread baking techniques and recipes.",
        "text/plain",
    )

    calls = []
    monkeypatch.setattr(
        service_module, "generate_answer", lambda **kwargs: calls.append(1) or "should not be used"
    )

    # Genuinely unrelated query against real (unmocked) retrieval — the
    # min_relevance_score filter should exclude the bread-baking document
    # rather than Gemini being handed irrelevant context and asked to
    # make the best of it.
    response = ask("What is the population of Mars colonies in the year 2200?")
    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert calls == []  # Gemini must not be called when nothing clears the relevance bar


def test_casual_message_skips_retrieval_and_gemini(monkeypatch):
    import app.synthesis.service as service_module

    search_calls = []
    generate_calls = []
    monkeypatch.setattr(service_module, "search", lambda db, query, top_k: search_calls.append(1) or [])
    monkeypatch.setattr(
        service_module, "generate_answer", lambda **kwargs: generate_calls.append(1) or "unused"
    )

    response = ask("thanks")
    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert search_calls == []
    assert generate_calls == []
    assert "welcome" in body["answer"].lower()


def test_multi_document_question_returns_multiple_sources(monkeypatch):
    import app.synthesis.service as service_module

    upload("ask-multi-a.txt", b"Distinct comprehensive multi document retrieval test content Alpha.", "text/plain")
    upload("ask-multi-b.txt", b"Distinct comprehensive multi document retrieval test content Beta.", "text/plain")

    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: "See [S1] and [S2].")

    response = ask("distinct comprehensive multi document retrieval test content", top_k=4)
    assert response.status_code == 200
    document_ids = {s["document_id"] for s in response.json()["sources"]}
    assert len(document_ids) > 1
