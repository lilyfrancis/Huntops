import json
import logging

from anthropic import Anthropic

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: Anthropic | None = None


class AIResponseError(Exception):
    """Raised when the model's reply isn't the JSON we asked for.

    JobQuick's prototype did a bare `json.loads()` on every AI call with no
    validation and let a malformed reply 500 the whole request. This gives
    callers one clear exception to catch instead of an unhandled JSONDecodeError.
    """


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise AIResponseError("ANTHROPIC_API_KEY is not configured")
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json") :]
    elif text.startswith("```"):
        text = text[len("```") :]
    if text.endswith("```"):
        text = text[: -len("```")]
    return text.strip()


def complete_json(system: str, prompt: str, model: str, max_tokens: int = 1024) -> dict | list:
    """Call Claude and parse its reply as JSON. Raises AIResponseError on any failure."""
    client = _get_client()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text
        stop_reason = response.stop_reason
    except Exception as e:  # network/API errors from the SDK
        logger.error("Anthropic API call failed: %s", e)
        raise AIResponseError(f"AI provider call failed: {e}") from e

    # Checked before parsing, because a truncated reply is invalid JSON and
    # would otherwise be reported as a malformed model response — which sends
    # you looking at the prompt and the model when the real problem is that
    # the answer did not fit in the budget it was given.
    if stop_reason == "max_tokens":
        logger.error(
            "Model reply truncated at max_tokens=%s (%d chars returned)", max_tokens, len(raw_text)
        )
        raise AIResponseError(
            f"The model's reply was cut off at {max_tokens} tokens — "
            f"the request asked for more output than it had room for."
        )

    try:
        return json.loads(_strip_json_fence(raw_text))
    except json.JSONDecodeError as e:
        logger.error("AI response was not valid JSON (stop_reason=%s): %s", stop_reason, raw_text[:500])
        raise AIResponseError("AI response was not valid JSON") from e
