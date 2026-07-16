from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    fmp_api_key: str | None = os.getenv("FMP_API_KEY")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    tavily_api_key: str | None = os.getenv("TAVILY_API_KEY")
    fmp_base_url: str = "https://financialmodelingprep.com/stable"
    fmp_configured: bool = bool(os.getenv("FMP_API_KEY"))


settings = Settings()