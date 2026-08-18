from app.llm.errors import LLMError, LLMRateLimitError, LLMTimeoutError


class GeminiProvider:
    """Wraps the Gemini API behind the LLMProvider interface. The client is
    created lazily on first use (not at import time or construction time),
    so importing this module — or starting the app without a configured API
    key — never fails; only an actual answer-generation attempt does.
    """

    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        if not self.api_key:
            raise LLMError(
                "GEMINI_API_KEY is not configured. Set it in your .env file to enable answer generation."
            )

        try:
            from google import genai
        except ImportError as exc:
            raise LLMError("google-genai is not installed.") from exc

        self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate(self, *, system_instruction: str, prompt: str) -> str:
        client = self._get_client()

        try:
            from google.genai import types
        except ImportError as exc:
            raise LLMError("google-genai is not installed.") from exc

        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system_instruction),
            )
        except Exception as exc:
            raise _translate_gemini_error(exc) from exc

        text = getattr(response, "text", None)
        if not text or not text.strip():
            raise LLMError("The AI service didn't return an answer. Please try again.")

        return text.strip()

    def describe_image(self, *, image_bytes: bytes, mime_type: str, prompt: str) -> str:
        client = self._get_client()

        try:
            from google.genai import types
        except ImportError as exc:
            raise LLMError("google-genai is not installed.") from exc

        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
            )
        except Exception as exc:
            raise _translate_gemini_error(exc) from exc

        text = getattr(response, "text", None)
        if not text or not text.strip():
            raise LLMError("The AI service didn't return a description for this image.")

        return text.strip()


def _translate_gemini_error(exc: Exception) -> LLMError:
    """Maps a Gemini SDK exception to one of our own error types with a
    clean, safe message. Deliberately never includes the original
    exception's text in the message we return — only used here to decide
    *which* clean message to raise, so nothing from the SDK (which could,
    in principle, echo request details) reaches the API response.
    """
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    lowered = str(exc).lower()

    if status_code == 429 or "rate limit" in lowered or "resource_exhausted" in lowered or "quota" in lowered:
        return LLMRateLimitError("Gemini is temporarily rate-limited. Please try again in a moment.")

    if isinstance(exc, TimeoutError) or "timeout" in lowered or "deadline" in lowered:
        return LLMTimeoutError("The AI service took too long to respond. Please try again.")

    return LLMError("The AI service is temporarily unavailable. Please try again shortly.")
