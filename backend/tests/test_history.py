from app.synthesis.history import condense_query


def test_condense_query_falls_back_to_original_on_llm_failure(monkeypatch):
    import app.synthesis.history as history_module
    from app.llm import LLMError

    monkeypatch.setattr(
        history_module, "generate_answer", lambda **kwargs: (_ for _ in ()).throw(LLMError("boom"))
    )

    result = condense_query("What is its time complexity?", [("user", "What is binary search?")])
    assert result == "What is its time complexity?"


def test_condense_query_returns_rewritten_text(monkeypatch):
    import app.synthesis.history as history_module

    monkeypatch.setattr(history_module, "generate_answer", lambda **kwargs: "What is the time complexity of binary search?")

    result = condense_query("What is its time complexity?", [("user", "What is binary search?")])
    assert result == "What is the time complexity of binary search?"
