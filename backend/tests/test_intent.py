import pytest

from app.synthesis.intent import casual_response, classify_casual_message


@pytest.mark.parametrize(
    "text,expected_category",
    [
        ("hi", "greeting"),
        ("Hello!", "greeting"),
        ("hey", "greeting"),
        ("thanks", "thanks"),
        ("Thank you.", "thanks"),
        ("thank you so much", "thanks"),
        ("ok", "acknowledgement"),
        ("Okay!", "acknowledgement"),
        ("got it", "acknowledgement"),
        ("bye", "farewell"),
        ("goodbye!", "farewell"),
        ("nothing, thank you", "noop"),
        ("nothing thanks", "noop"),
        ("no thanks", "noop"),
        ("that's all for now", None),  # not an exact match, and that's fine — falls through to RAG
    ],
)
def test_classify_casual_message(text, expected_category):
    assert classify_casual_message(text) == expected_category


@pytest.mark.parametrize(
    "text",
    [
        "What is binary search?",
        "can you deep dive it?",
        "why is it faster?",
        "give me an example",
        "what about space complexity?",
        "thanks for explaining, but what about space complexity?",
        "How does load balancing compare to binary search?",
    ],
)
def test_classify_casual_message_returns_none_for_genuine_messages(text):
    assert classify_casual_message(text) is None


def test_classify_casual_message_handles_empty_and_whitespace():
    assert classify_casual_message("") is None
    assert classify_casual_message("   ") is None


def test_nothing_thank_you_gets_a_warm_closing_reply_not_a_kb_disclaimer():
    category = classify_casual_message("nothing, thank you")
    assert category is not None
    response = casual_response(category)
    assert "don't have" not in response.lower()
    assert "knowledge base" not in response.lower()
    assert "welcome" in response.lower()
