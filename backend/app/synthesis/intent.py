import re

# Short, formulaic small talk that doesn't need retrieval or an LLM call
# to recognize — matching is exact (after normalizing case/punctuation/
# whitespace), not substring, so a genuine question that happens to start
# with "thanks for the help, but..." is never misclassified as casual.
_GREETINGS = {
    "hi", "hello", "hey", "hiya", "yo", "howdy",
    "good morning", "good afternoon", "good evening",
}

_THANKS = {
    "thanks", "thank you", "thankyou", "thanks a lot", "thank you so much",
    "thank you very much", "thanks so much", "much appreciated",
    "appreciate it", "many thanks", "ty", "thx",
}

_ACKNOWLEDGEMENTS = {
    "ok", "okay", "k", "kk", "got it", "gotcha", "understood",
    "i understand", "sounds good", "cool", "great", "perfect", "nice",
    "alright", "sure", "noted", "makes sense",
}

_FAREWELLS = {
    "bye", "goodbye", "see you", "see ya", "later", "cya", "take care",
}

# A closing remark, optionally paired with thanks — "nothing, thank you",
# "no thanks", "that's all for now". Built from small prefix/suffix sets
# rather than a long hand-written list of every combination.
_NOOP_PREFIXES = {
    "nothing", "no", "nope", "nothing else", "nothing more",
    "that's all", "thats all", "that's it", "thats it",
    "i'm good", "im good", "all good", "no more questions",
}
_NOOP = {f"{prefix} {suffix}".strip() for prefix in _NOOP_PREFIXES for suffix in ({"", *_THANKS})}

_CASUAL_RESPONSES = {
    "greeting": "Hello! Ask me anything about your uploaded documents.",
    "thanks": "You're welcome! Let me know if you need anything else.",
    "acknowledgement": "Got it — let me know if you have another question.",
    "farewell": "Goodbye! Come back anytime you have a question.",
    "noop": "You're welcome! Let me know if you need anything else.",
}


def _normalize(text: str) -> str:
    normalized = re.sub(r"[^\w\s]", " ", text.strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


def classify_casual_message(text: str) -> str | None:
    """Returns a casual-response category if `text` is small talk with no
    knowledge-seeking content (greeting/thanks/acknowledgement/farewell/a
    closing "nothing, thanks"-style remark), else None. Deterministic and
    free: these are short, formulaic phrases that don't need an LLM call
    to recognize, and a canned reply is both instant and more consistent
    than asking Gemini to improvise one.
    """
    normalized = _normalize(text)
    if not normalized:
        return None

    if normalized in _GREETINGS:
        return "greeting"
    if normalized in _THANKS:
        return "thanks"
    if normalized in _ACKNOWLEDGEMENTS:
        return "acknowledgement"
    if normalized in _FAREWELLS:
        return "farewell"
    if normalized in _NOOP or normalized in _NOOP_PREFIXES:
        return "noop"
    return None


def casual_response(category: str) -> str:
    return _CASUAL_RESPONSES[category]
