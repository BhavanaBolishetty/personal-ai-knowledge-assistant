from app.llm.errors import LLMError, LLMRateLimitError, LLMTimeoutError
from app.llm.gemini import _translate_gemini_error


def test_rate_limit_error_produces_user_friendly_message():
    exc = _translate_gemini_error(Exception("429 RESOURCE_EXHAUSTED: quota exceeded"))
    assert isinstance(exc, LLMRateLimitError)
    assert str(exc) == "Gemini is temporarily rate-limited. Please try again in a moment."


def test_timeout_error_produces_user_friendly_message():
    exc = _translate_gemini_error(TimeoutError("deadline exceeded"))
    assert isinstance(exc, LLMTimeoutError)
    assert str(exc) == "The AI service took too long to respond. Please try again."


def test_generic_error_produces_user_friendly_message():
    exc = _translate_gemini_error(Exception("some unexpected internal failure"))
    assert isinstance(exc, LLMError)
    assert str(exc) == "The AI service is temporarily unavailable. Please try again shortly."


def test_translated_errors_never_leak_original_exception_text():
    original = Exception("secret internal detail that should never leak, key=abc123")
    exc = _translate_gemini_error(original)
    assert "secret internal detail" not in str(exc)
    assert "abc123" not in str(exc)
