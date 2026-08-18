import re

from app.chunking.splitter import chunk_text


def test_short_text_produces_one_chunk():
    text = "This is a short piece of text."
    chunks = chunk_text(text, chunk_size=1000, chunk_overlap=150)
    assert chunks == [text]


def test_text_larger_than_chunk_size_produces_multiple_chunks():
    text = "\n\n".join(f"Paragraph {i}. " + ("word " * 50) for i in range(10))
    chunks = chunk_text(text, chunk_size=200, chunk_overlap=30)
    assert len(chunks) > 1
    assert all(len(c) <= 200 + 30 for c in chunks)


def test_overlap_carries_context_between_chunks():
    text = "\n\n".join(
        f"Paragraph {i} has some unique filler content padded out here." for i in range(6)
    )
    chunks = chunk_text(text, chunk_size=120, chunk_overlap=40)
    assert len(chunks) > 1
    for first, second in zip(chunks, chunks[1:]):
        tail_words = first.strip().split()[-3:]
        assert any(word in second for word in tail_words)


def test_words_are_not_cut_when_hard_splitting():
    words = [f"token{i:04d}" for i in range(200)]
    text = " ".join(words)  # one giant "sentence", no punctuation -> forces a hard split
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    for chunk in chunks:
        for token in chunk.split():
            assert re.fullmatch(r"token\d{4}", token), f"corrupted token: {token!r}"


def test_paragraph_boundaries_are_preferred_when_they_fit():
    paragraph_a = "A" * 40
    paragraph_b = "B" * 40
    paragraph_c = "C" * 40
    text = f"{paragraph_a}\n\n{paragraph_b}\n\n{paragraph_c}"

    chunks = chunk_text(text, chunk_size=90, chunk_overlap=0)

    assert chunks[0] == f"{paragraph_a}\n\n{paragraph_b}"
    assert paragraph_c in chunks[-1]


def test_empty_text_produces_no_chunks():
    assert chunk_text("", chunk_size=500, chunk_overlap=50) == []
    assert chunk_text("   \n\n  ", chunk_size=500, chunk_overlap=50) == []


def test_very_large_text_is_bounded_into_reasonable_chunks():
    text = "\n\n".join(f"Paragraph {i}: " + ("word " * 30) for i in range(500))
    chunks = chunk_text(text, chunk_size=1000, chunk_overlap=150)
    assert len(chunks) > 10
    assert all(len(c) <= 1000 + 150 for c in chunks)


def test_chunking_is_deterministic():
    text = "\n\n".join(
        f"Paragraph number {i} with some repeated filler words here." for i in range(20)
    )
    first_run = chunk_text(text, chunk_size=150, chunk_overlap=30)
    second_run = chunk_text(text, chunk_size=150, chunk_overlap=30)
    assert first_run == second_run
