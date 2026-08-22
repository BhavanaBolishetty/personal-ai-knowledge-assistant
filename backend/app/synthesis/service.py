import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.memory_diagnostics import log_memory
from app.db import crud
from app.db.models import MessageRole
from app.llm import generate_answer
from app.retrieval import search
from app.synthesis.context_builder import build_context, select_cited_sources
from app.synthesis.history import condense_query
from app.synthesis.intent import casual_response, classify_casual_message
from app.synthesis.prompt import SYSTEM_INSTRUCTION, build_prompt

NO_CONTEXT_ANSWER = (
    "I don't have any information in the knowledge base to answer that question. "
    "Try uploading a document that covers this topic."
)


def answer_question(db: Session, query: str, top_k: int, user_id: uuid.UUID) -> dict:
    """Retrieval -> grounded prompt -> Gemini -> answer + structured
    sources. Stateless — no conversation memory. Ends here: this does not
    do multi-source synthesis beyond handing Gemini several labeled
    sources in one prompt.
    """
    casual_category = classify_casual_message(query)
    if casual_category:
        return _casual_result(casual_category)

    results = search(db, query, top_k, user_id)  # validates the query; may raise retrieval errors
    context, sources = build_context(results, max_context_chars=settings.max_context_chars)

    if not sources:
        return _no_context_result()

    prompt = build_prompt(question=query, context=context)
    answer_text = generate_answer(system_instruction=SYSTEM_INSTRUCTION, prompt=prompt)
    answer_text, cited_sources = select_cited_sources(answer_text, sources)
    log_memory("after_answer_generation")

    return _result(answer_text, cited_sources, results, settings.gemini_model)


def answer_conversation_question(
    db: Session, conversation_id: uuid.UUID, query: str, top_k: int, user_id: uuid.UUID
) -> dict:
    """Same as answer_question, but history-aware: recent conversation
    turns are used to resolve references ("its", "that") in the retrieval
    query, and shown to Gemini as context for tone — never as a source of
    facts (see prompt.py). The user's question and Gemini's answer are
    both persisted as part of the conversation. The caller (app/api/
    conversations.py) has already verified conversation_id belongs to
    user_id before calling this.
    """
    # Casual small talk ("thanks", "hi", "nothing, thank you") skips
    # retrieval and Gemini entirely — a knowledge-base disclaimer or a
    # citation list makes no sense as a reply to "thanks". Still recorded
    # as part of the conversation like any other turn, but the auto-title
    # is left alone so a chat that opens with "hi" gets its real title
    # from the first substantive question instead.
    casual_category = classify_casual_message(query)
    if casual_category:
        result = _casual_result(casual_category)
        crud.create_message(db, conversation_id, role=MessageRole.user, content=query)
        crud.create_message(
            db, conversation_id, role=MessageRole.assistant, content=result["answer"], sources=result["sources"]
        )
        conversation = crud.get_conversation(db, conversation_id, user_id)
        crud.touch_conversation(db, conversation)
        return result

    history_messages = crud.get_recent_messages(db, conversation_id, limit=settings.conversation_history_limit)
    history = [(m.role.value, m.content) for m in history_messages]

    # A follow-up like "What is its time complexity?" or a vague
    # clarification like "can you deep dive it?" carries almost no
    # meaning on its own — embedding it directly would retrieve poorly.
    # Only spend the extra Gemini call when there's actually prior
    # history to resolve against; a first question is already standalone.
    search_query = condense_query(query, history) if history else query

    results = search(db, search_query, top_k, user_id)
    context, sources = build_context(results, max_context_chars=settings.max_context_chars)

    if not sources:
        result = _no_context_result()
    else:
        prompt = build_prompt(question=query, context=context, history=history)
        # If this raises (rate limit, timeout, etc.), nothing has been
        # persisted yet — the question is not saved. Persisting it first
        # would leave an orphaned question with no reply on every failure,
        # permanently corrupting this conversation's history (and any
        # future follow-up's reference resolution, which reads that
        # history back) instead of just letting the user retry.
        answer_text = generate_answer(system_instruction=SYSTEM_INSTRUCTION, prompt=prompt)
        answer_text, cited_sources = select_cited_sources(answer_text, sources)
        log_memory("after_answer_generation")
        result = _result(answer_text, cited_sources, results, settings.gemini_model)

    crud.create_message(db, conversation_id, role=MessageRole.user, content=query)
    crud.create_message(
        db, conversation_id, role=MessageRole.assistant, content=result["answer"], sources=result["sources"]
    )

    conversation = crud.get_conversation(db, conversation_id, user_id)
    crud.set_conversation_title_if_default(db, conversation, query)
    crud.touch_conversation(db, conversation)

    return result


def _no_context_result() -> dict:
    # Nothing was retrieved at all — there is nothing to ground an answer
    # in, so we don't spend a Gemini call finding that out.
    return {"answer": NO_CONTEXT_ANSWER, "sources": [], "retrieved_chunk_count": 0, "model": None}


def _casual_result(category: str) -> dict:
    # No retrieval, no Gemini call, no sources — small talk isn't a
    # knowledge-base query.
    return {"answer": casual_response(category), "sources": [], "retrieved_chunk_count": 0, "model": None}


def _result(answer_text: str, sources: list[dict], results: list[dict], model: str) -> dict:
    return {
        "answer": answer_text,
        # Already filtered down to sources the answer text actually cites
        # by select_cited_sources (see context_builder.py) — a chunk being
        # retrieved and handed to Gemini does not mean the answer used it.
        "sources": [
            {
                "id": item["source_id"],
                # Stringified: this list is stored as-is in the messages
                # table's JSONB "sources" column (see
                # answer_conversation_question), and raw UUID objects
                # aren't JSON-serializable. A plain UUID string is still
                # valid input for the AskSourceItem/MessageResponse
                # schemas, which coerce it back to a UUID.
                "document_id": str(item["document_id"]),
                "filename": item["original_filename"],
                "source_url": item.get("source_url"),
                # Internal/debug only — the frontend does not display this
                # by default (see Chat.jsx's developer-info toggle).
                "chunk_index": item["chunk_index"],
                "page_start": item["page_start"],
                "page_end": item["page_end"],
            }
            for item in sources
        ],
        "retrieved_chunk_count": len(results),
        "model": model,
    }
