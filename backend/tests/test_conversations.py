import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_conversation_returns_default_title():
    response = client.post("/conversations")
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "New conversation"
    assert "id" in body and "created_at" in body and "updated_at" in body


def test_list_conversations_includes_created_ones():
    created = client.post("/conversations").json()
    response = client.get("/conversations")
    assert response.status_code == 200
    ids = [c["id"] for c in response.json()]
    assert created["id"] in ids


def test_get_conversation_returns_empty_messages_initially():
    conversation = client.post("/conversations").json()
    response = client.get(f"/conversations/{conversation['id']}")
    assert response.status_code == 200
    assert response.json()["messages"] == []


def test_get_nonexistent_conversation_returns_404():
    response = client.get("/conversations/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_delete_conversation_removes_it():
    conversation = client.post("/conversations").json()
    response = client.delete(f"/conversations/{conversation['id']}")
    assert response.status_code == 204
    assert client.get(f"/conversations/{conversation['id']}").status_code == 404


def test_delete_nonexistent_conversation_returns_404():
    response = client.delete("/conversations/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_new_chat_does_not_delete_other_conversations():
    first = client.post("/conversations").json()
    second = client.post("/conversations").json()
    ids = [c["id"] for c in client.get("/conversations").json()]
    assert first["id"] in ids
    assert second["id"] in ids


def test_ask_in_conversation_persists_messages_and_sources(monkeypatch):
    import app.synthesis.service as service_module

    upload_response = client.post(
        "/documents",
        files={
            "file": (
                "conv-doc.txt",
                io.BytesIO(b"Distinct conversation persistence test content."),
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 201

    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: "A persisted answer. [S1]")

    conversation = client.post("/conversations").json()
    response = client.post(
        f"/conversations/{conversation['id']}/ask",
        json={"query": "distinct conversation persistence test content"},
    )
    assert response.status_code == 200
    assert response.json()["answer"] == "A persisted answer. [S1]"

    # Reopening the conversation (simulating a browser refresh) must show
    # the same messages, including the assistant's citations.
    detail = client.get(f"/conversations/{conversation['id']}").json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][1]["role"] == "assistant"
    assert detail["messages"][1]["content"] == "A persisted answer. [S1]"
    assert detail["messages"][1]["sources"]


def test_ask_in_conversation_sets_title_from_first_question(monkeypatch):
    import app.synthesis.service as service_module

    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: "Answer.")

    conversation = client.post("/conversations").json()
    client.post(f"/conversations/{conversation['id']}/ask", json={"query": "What is a title test question?"})

    detail = client.get(f"/conversations/{conversation['id']}").json()
    assert detail["title"] == "What is a title test question?"


def test_followup_question_uses_condensed_query_for_retrieval(monkeypatch):
    import app.synthesis.service as service_module

    captured_queries = []

    def _fake_search(db, query, top_k, user_id):
        captured_queries.append(query)
        return []

    monkeypatch.setattr(service_module, "search", _fake_search)
    monkeypatch.setattr(service_module, "condense_query", lambda question, history: "condensed standalone query")

    conversation = client.post("/conversations").json()

    # First question: no prior history, so condense_query's output must
    # not be used — retrieval searches for the raw question.
    client.post(f"/conversations/{conversation['id']}/ask", json={"query": "What is binary search?"})
    assert captured_queries[-1] == "What is binary search?"

    # Follow-up: history now exists, so the condensed (standalone) query —
    # not the raw "its ..." text — is what retrieval must search for.
    client.post(f"/conversations/{conversation['id']}/ask", json={"query": "What is its time complexity?"})
    assert captured_queries[-1] == "condensed standalone query"


def test_followup_question_does_not_pull_in_unrelated_document(monkeypatch):
    import app.synthesis.service as service_module

    upload_response_lb = client.post(
        "/documents",
        files={
            "file": (
                "conv-relevance-load-balancing.txt",
                io.BytesIO(
                    b"A load balancer distributes incoming network traffic across multiple "
                    b"backend servers so no single server is overwhelmed."
                ),
                "text/plain",
            )
        },
    )
    client.post(
        "/documents",
        files={
            "file": (
                "conv-relevance-binary-search.txt",
                io.BytesIO(
                    b"Binary search finds a target value in a sorted array by repeatedly "
                    b"halving the search interval."
                ),
                "text/plain",
            )
        },
    )
    assert upload_response_lb.status_code == 201

    # condense_query is mocked (deterministic, no live Gemini call needed
    # for this test) but real, unmocked retrieval — with the relevance
    # threshold — is what must exclude the unrelated document.
    monkeypatch.setattr(service_module, "condense_query", lambda question, history: "Where is a load balancer used?")
    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: "Used in web services. [S1]")

    conversation = client.post("/conversations").json()
    client.post(f"/conversations/{conversation['id']}/ask", json={"query": "What is load balancing?"})

    response = client.post(f"/conversations/{conversation['id']}/ask", json={"query": "Where is it used?"})
    assert response.status_code == 200
    filenames = [s["filename"] for s in response.json()["sources"]]
    assert "conv-relevance-binary-search.txt" not in filenames


def test_failed_gemini_call_does_not_persist_an_orphaned_question(monkeypatch):
    import app.synthesis.service as service_module
    from app.llm import LLMRateLimitError

    client.post(
        "/documents",
        files={
            "file": (
                "conv-failure-check.txt",
                io.BytesIO(b"Distinct content for the Gemini-failure persistence regression test."),
                "text/plain",
            )
        },
    )

    def _rate_limited(**kwargs):
        raise LLMRateLimitError("Gemini is temporarily rate-limited. Please try again in a moment.")

    monkeypatch.setattr(service_module, "generate_answer", _rate_limited)

    conversation = client.post("/conversations").json()
    response = client.post(
        f"/conversations/{conversation['id']}/ask",
        json={"query": "Distinct content for the Gemini-failure persistence regression test"},
    )
    assert response.status_code == 429

    # The question must not be saved when answering it failed — otherwise
    # it sits in the conversation forever with no reply, and later
    # follow-ups would read it back as history.
    detail = client.get(f"/conversations/{conversation['id']}").json()
    assert detail["messages"] == []


def test_casual_message_in_conversation_skips_retrieval_gets_no_sources(monkeypatch):
    import app.synthesis.service as service_module

    search_calls = []
    generate_calls = []
    monkeypatch.setattr(service_module, "search", lambda db, query, top_k, user_id: search_calls.append(1) or [])
    monkeypatch.setattr(
        service_module, "generate_answer", lambda **kwargs: generate_calls.append(1) or "unused"
    )

    conversation = client.post("/conversations").json()
    response = client.post(f"/conversations/{conversation['id']}/ask", json={"query": "nothing, thank you"})

    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert search_calls == []
    assert generate_calls == []
    assert "don't have" not in body["answer"].lower()

    # Still recorded as part of the conversation like any other turn.
    detail = client.get(f"/conversations/{conversation['id']}").json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["content"] == "nothing, thank you"


def test_casual_first_message_does_not_set_conversation_title(monkeypatch):
    import app.synthesis.service as service_module

    monkeypatch.setattr(service_module, "search", lambda db, query, top_k, user_id: [])

    conversation = client.post("/conversations").json()
    client.post(f"/conversations/{conversation['id']}/ask", json={"query": "hi"})

    detail = client.get(f"/conversations/{conversation['id']}").json()
    assert detail["title"] == "New conversation"


def test_no_gemini_call_when_nothing_retrieved(monkeypatch):
    import app.synthesis.service as service_module

    calls = []
    monkeypatch.setattr(service_module, "generate_answer", lambda **kwargs: calls.append(1) or "unused")
    monkeypatch.setattr(service_module, "search", lambda db, query, top_k, user_id: [])

    conversation = client.post("/conversations").json()
    response = client.post(
        f"/conversations/{conversation['id']}/ask", json={"query": "a question with no matching content"}
    )
    assert response.status_code == 200
    assert response.json()["sources"] == []
    assert calls == []


def test_ask_in_nonexistent_conversation_returns_404():
    response = client.post(
        "/conversations/00000000-0000-0000-0000-000000000000/ask", json={"query": "test"}
    )
    assert response.status_code == 404


def test_empty_question_in_conversation_is_rejected():
    conversation = client.post("/conversations").json()
    response = client.post(f"/conversations/{conversation['id']}/ask", json={"query": ""})
    assert response.status_code == 400
