from app.llm import LLMError, generate_answer

_CONDENSE_SYSTEM_INSTRUCTION = (
    "You rewrite a follow-up message into a standalone search query for a "
    "knowledge base, using the recent conversation to fill in what the user "
    "is really asking about. This includes resolving pronouns ('it', "
    "'that') AND vague clarification requests that only make sense given "
    "the prior topic — 'can you deep dive it?', 'why is it faster?', 'give "
    "me an example', 'what about space complexity?' — by rewriting them "
    "into a specific question about that topic (e.g. after a binary search "
    "discussion, 'deep dive it' becomes 'Explain binary search in more "
    "detail' and 'give me an example' becomes 'Give an example of binary "
    "search'). If the user has clearly moved to a new topic, use the new "
    "topic instead of the old one. Output ONLY the rewritten question — no "
    "explanation, no quotes. If the message is already standalone, return "
    "it unchanged."
)


def condense_query(question: str, history: list[tuple[str, str]]) -> str:
    """Rewrites a follow-up question (e.g. "What is its time complexity?")
    into a standalone one (e.g. "What is the time complexity of binary
    search?") using recent conversation turns, so retrieval actually
    searches for the right thing. Only called when history exists — the
    first question in a conversation is already standalone, so it's used
    as-is with no extra Gemini call.

    Best-effort: if this call fails for any reason, the original question
    is used unchanged rather than failing the whole request — a worse
    retrieval query is better than no answer at all.
    """
    transcript = "\n".join(f"{role.capitalize()}: {content}" for role, content in history)
    prompt = f"RECENT CONVERSATION:\n{transcript}\n\nFOLLOW-UP QUESTION:\n{question}\n\nSTANDALONE QUESTION:"

    try:
        rewritten = generate_answer(system_instruction=_CONDENSE_SYSTEM_INSTRUCTION, prompt=prompt)
    except LLMError:
        return question

    rewritten = rewritten.strip().strip('"')
    return rewritten or question
