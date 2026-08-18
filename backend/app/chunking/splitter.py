import re

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_SEPARATOR = "\n\n"


def chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into deterministic, retrieval-sized chunks.

    Strategy: text is first broken into "units" — paragraphs, falling back
    to sentences for any paragraph longer than chunk_size, falling back to
    a hard whitespace-boundary split for any sentence longer than
    chunk_size. Units are then greedily packed into chunks up to
    chunk_size, and each new chunk is seeded with a word-boundary-safe
    tail of the previous chunk (up to chunk_overlap characters) so context
    isn't lost across a chunk boundary.
    """
    text = text.strip()
    if not text:
        return []

    units = _split_into_units(text, chunk_size)
    if not units:
        return []

    chunks: list[str] = []
    current = ""

    for unit in units:
        candidate = f"{current}{_SEPARATOR}{unit}" if current else unit
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        chunks.append(current)
        overlap_budget = max(0, chunk_size - len(_SEPARATOR) - len(unit))
        overlap_text = _take_overlap(current, min(chunk_overlap, overlap_budget))
        current = f"{overlap_text}{_SEPARATOR}{unit}" if overlap_text else unit

    if current:
        chunks.append(current)

    return chunks


def _split_into_units(text: str, chunk_size: int) -> list[str]:
    units: list[str] = []
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT_RE.split(text) if p.strip()]

    for paragraph in paragraphs:
        if len(paragraph) <= chunk_size:
            units.append(paragraph)
            continue

        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(paragraph) if s.strip()]
        for sentence in sentences:
            if len(sentence) <= chunk_size:
                units.append(sentence)
            else:
                units.extend(_hard_split(sentence, chunk_size))

    return units


def _hard_split(text: str, chunk_size: int) -> list[str]:
    """Last-resort split for a single "sentence" longer than chunk_size
    (e.g. a long unbroken block of text with no sentence punctuation).
    Splits at the last whitespace at-or-before the limit so words are
    never cut; if no whitespace exists within the window (one giant
    unbroken token), cuts exactly at chunk_size as a bounded worst case.
    """
    pieces: list[str] = []
    remaining = text

    while len(remaining) > chunk_size:
        window = remaining[:chunk_size]
        split_at = window.rfind(" ")
        if split_at <= 0:
            split_at = chunk_size
        piece = remaining[:split_at].strip()
        if piece:
            pieces.append(piece)
        remaining = remaining[split_at:].strip()

    if remaining:
        pieces.append(remaining)

    return pieces


def _take_overlap(text: str, max_overlap_chars: int) -> str:
    if max_overlap_chars <= 0 or not text:
        return ""

    tail = text[-max_overlap_chars:]
    space_index = tail.find(" ")
    if space_index == -1:
        # No safe word boundary within the overlap window — skip overlap
        # for this chunk rather than start it mid-word.
        return ""
    return tail[space_index + 1 :]
