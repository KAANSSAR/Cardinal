"""
Gemini 3.5 Flash client — thin wrapper around google-genai SDK.

Isolated here so every agent imports from one place, and swapping
the model or provider later is a one-file change.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from cardinal.config import settings


class GeminiNotConfiguredError(Exception):
    """Raised when GEMINI_API_KEY is not set in the environment."""


def generate(
    prompt: str,
    system_prompt: str,
    max_output_tokens: int = 2048,
    temperature: float = 0.4,
) -> str:
    """
    Call Gemini 3.5 Flash with a system prompt and user prompt.
    Thinking mode is disabled — we want a direct, structured response
    rather than chain-of-thought tokens consuming the output budget.
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