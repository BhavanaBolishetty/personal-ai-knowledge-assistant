class LLMError(Exception):
    """Raised when the LLM provider fails to generate a response."""


class LLMRateLimitError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass
