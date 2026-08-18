from typing import Protocol


class LLMProvider(Protocol):
    """Minimal interface the rest of the app depends on. GeminiProvider is
    the only implementation for now. A different provider (another hosted
    API, or a local model) could be added later behind this same interface
    without changing app/synthesis/ — only app/llm/service.py would need to
    point at it.
    """

    def generate(self, *, system_instruction: str, prompt: str) -> str: ...

    def describe_image(self, *, image_bytes: bytes, mime_type: str, prompt: str) -> str: ...
