from app.core.config import settings
from app.llm.gemini import GeminiProvider

# The single provider instance the rest of the app depends on. Swapping to a
# different provider later means changing this line, not every caller —
# callers only ever import generate_answer from this module.
_provider = GeminiProvider(
    model_name=settings.gemini_model,
    api_key=settings.gemini_api_key,
)


def generate_answer(*, system_instruction: str, prompt: str) -> str:
    return _provider.generate(system_instruction=system_instruction, prompt=prompt)


def describe_image(*, image_bytes: bytes, mime_type: str, prompt: str) -> str:
    return _provider.describe_image(image_bytes=image_bytes, mime_type=mime_type, prompt=prompt)
