"""
Gemini 3.5 Flash client — thin wrapper around google-genai SDK.

Isolated here so every agent imports from one place, and swapping
the model or provider later is a one-file change.
"""

from __future__ import annotations

from google import genai
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from cardinal.config import settings


class GeminiNotConfiguredError(Exception):
    """Raised when GEMINI_API_KEY is not set in the environment."""


def _is_retryable(exc: BaseException) -> bool:
    """Retry on 503 (UNAVAILABLE) and 429 (RESOURCE_EXHAUSTED) only."""
    msg = str(exc)
    return "503" in msg or "UNAVAILABLE" in msg or "429" in msg or "RESOURCE_EXHAUSTED" in msg


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    stop=stop_after_attempt(4),
    reraise=True,
)
def generate(
    prompt: str,
    system_prompt: str,
    max_output_tokens: int = 2048,
    temperature: float = 0.4,
) -> str:
    """
    Call Gemini 3.5 Flash with a system prompt and user prompt.
    Automatically retries up to 4 times on 503/429 with exponential backoff.
    Thinking mode disabled — all tokens go to the actual response.
    """
    if not settings.gemini_configured:
        raise GeminiNotConfiguredError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )

    client = genai.Client(api_key=settings.gemini_api_key)

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    return response.text