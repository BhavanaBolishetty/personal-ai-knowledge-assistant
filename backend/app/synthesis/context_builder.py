import re

_CITATION_ID_PATTERN = re.compile(r"\[S(\d+)\]")


def select_cited_sources(answer_text: str, sources: list[dict]) -> tuple[str, list[dict]]:
    """Keeps only the sources the model's answer text actually cites, and
    renumbers them sequentially (S1, S2, ...) in citation order, rewriting
    the answer text's [S#] markers to match. The IDs a source happens to
    get during context-building are relevance-ranked, so they vary from
    run to run (a source might be [S1] in one answer and [S3] in
    another) — that internal numbering must never leak into what the
    user sees. The displayed numbering always starts at S1 and matches
    the source list exactly, with no gaps.

    A chunk being retrieved, or even included in the prompt's context,
    does not mean the answer actually relied on it — showing it as a
    citation anyway would misrepresent what backs the answer (e.g. an
    unrelated document surfacing alongside the real one just because it
    was among the top-K retrieved). build_context already groups every
    chunk retrieved from one document into a single source (see
    _group_by_document), so the same document can't produce two
    different IDs to begin with — the dedup below (by document + page
    range) is a cheap, explicit guarantee regardless. A citation marker
    with no matching source (e.g. a hallucinated ID) is stripped from
    the text entirely rather than left as a dangling reference.

    Returns (rewritten_answer_text, renumbered_sources).
    """
    sources_by_id = {source["source_id"]: source for source in sources}

    cited_ids_in_order = []
    seen_ids = set()
    for match in _CITATION_ID_PATTERN.finditer(answer_text):
        old_id = f"S{match.group(1)}"
        if old_id in sources_by_id and old_id not in seen_ids:
            seen_ids.add(old_id)
            cited_ids_in_order.append(old_id)

    id_remap: dict[str, str] = {}
    evidence_to_new_id: dict[tuple, str] = {}
    selected: list[dict] = []

    for old_id in cited_ids_in_order:
        source = sources_by_id[old_id]
        evidence_key = (source["document_id"], source["page_start"], source["page_end"])
        if evidence_key in evidence_to_new_id:
            id_remap[old_id] = evidence_to_new_id[evidence_key]
            continue
        new_id = f"S{len(selected) + 1}"
        evidence_to_new_id[evidence_key] = new_id
        id_remap[old_id] = new_id
        selected.append({**source, "source_id": new_id})

    def _renumber(match: re.Match) -> str:
        old_id = f"S{match.group(1)}"
        return f"[{id_remap[old_id]}]" if old_id in id_remap else ""

    rewritten_text = _CITATION_ID_PATTERN.sub(_renumber, answer_text)
    return rewritten_text, selected


def build_context(results: list[dict], *, max_context_chars: int) -> tuple[str, list[dict]]:
    """Formats retrieved chunks into a structured, source-labeled context
    block for the prompt, and returns the source groups actually included
    (each tagged with its provisional source_id, e.g. "S1") — this list
    doubles as the citation map used to build the API response's
    `sources` field.

    Retrieved chunks are first grouped with `_group_by_document` — every
    chunk retrieved from the same document becomes one group, so a
    document can never end up with more than one citation ID in an
    answer — then tried in relevance order. A group that would not fit
    within max_context_chars is skipped — never truncated mid-text — so
    a smaller, lower-ranked group further down the list still gets a
    chance to fit in the remaining budget, which tends to preserve
    source diversity better than simply stopping at the first group that
    doesn't fit. At least one source is always included even if it alone
    exceeds the budget, since an empty context defeats grounding
    entirely.

    The IDs assigned here only need to be stable within this one prompt,
    so Gemini's citations map back to the right group — select_cited_sources
    renumbers the final, user-facing list after filtering to what was
    actually cited.
    """
    groups = _group_by_document(results)

    included: list[dict] = []
    sections: list[str] = []
    used_chars = 0

    for group in groups:
        source_id = f"S{len(included) + 1}"
        section = _format_source_section(source_id, group)

        if included and used_chars + len(section) > max_context_chars:
            continue

        sections.append(section)
        included.append({**group, "source_id": source_id})
        used_chars += len(section)

    return "\n\n".join(sections), included


def _group_by_document(results: list[dict]) -> list[dict]:
    """Merges every retrieved chunk from the same document into a single
    source, regardless of how many chunks were retrieved or whether
    they're adjacent — a document must never produce more than one
    citation in an answer (e.g. three separate entries all pointing at
    the same resume just because three of its chunks were relevant).
    Preserves relevance order: each group is emitted at the position of
    its best-ranked (first-encountered) chunk, since `results` arrives
    already sorted by relevance.
    """
    order: list[str] = []
    members_by_document: dict[str, list[dict]] = {}

    for result in results:
        document_id = result["document_id"]
        if document_id not in members_by_document:
            order.append(document_id)
            members_by_document[document_id] = []
        members_by_document[document_id].append(result)

    return [_merge_group(members_by_document[document_id]) for document_id in order]


def _merge_group(members: list[dict]) -> dict:
    best = max(members, key=lambda m: m.get("similarity_score", 0))
    ordered_members = sorted(members, key=lambda m: m["chunk_index"])
    page_numbers = [m["page_number"] for m in members if m.get("page_number") is not None]

    return {
        "document_id": best["document_id"],
        "original_filename": best["original_filename"],
        "source_type": best["source_type"],
        "source_url": best.get("source_url"),
        "chunk_index": ordered_members[0]["chunk_index"],
        "text": "\n\n".join(m["text"] for m in ordered_members),
        # If the retrieved pages aren't contiguous (e.g. 1 and 26), this
        # still reports the outer span rather than adding a second
        # citation for the same document — an intentional simplification,
        # consistent with how a page-range citation ("pp. 1-26") is
        # normally read as "material drawn from within this range", not
        # "every single page in it".
        "page_start": min(page_numbers) if page_numbers else None,
        "page_end": max(page_numbers) if page_numbers else None,
        "similarity_score": best.get("similarity_score"),
    }


def _format_source_section(source_id: str, group: dict) -> str:
    if group["page_start"] is None:
        page_line = ""
    elif group["page_start"] == group["page_end"]:
        page_line = f"Page: {group['page_start']}\n"
    else:
        page_line = f"Pages: {group['page_start']}-{group['page_end']}\n"

    return f"[{source_id}]\nDocument: {group['original_filename']}\n{page_line}Text:\n{group['text']}"
