"""
Centralised configuration — loads from environment variables / .env file.

Never hardcode API keys here or anywhere else in the codebase. Copy
.env.example to .env and fill in real values; .env is gitignored.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    fmp_api_key: str | None = os.getenv("FMP_API_KEY")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    tavily_api_key: str | None = os.getenv("TAVILY_API_KEY")

    fmp_base_url: str = "https://financialmodelingprep.com/stable"

    @property
    def fmp_configured(self) -> bool:
        return bool(self.fmp_api_key)


settings = Settings()
