"""Runtime settings, read from the environment (.env supported). Same pattern as the sibling
claim-triage-agent and analytics-agent projects, for consistency across the portfolio.
"""

from __future__ import annotations

import os
from functools import lru_cache

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional in production
    pass


class Settings:
    def __init__(self) -> None:
        # Shared secret n8n sends so random requests can't reach this service.
        self.service_api_key: str = os.getenv("SERVICE_API_KEY", "dev-key-change-me")
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        # live = call Gemini; record = call and cache; replay = read cache only.
        self.llm_mode: str = os.getenv("LLM_MODE", "replay")
        self.prompt_version: str = os.getenv("PROMPT_VERSION", "v1")
        self.tickets_db: str = os.getenv("TICKETS_DB", "data/tickets.db")
        # Per business config. One place a new client edits; nothing else changes.
        self.business_name: str = os.getenv("BUSINESS_NAME", "Bright Smile Dental")
        self.business_type: str = os.getenv("BUSINESS_TYPE", "a dental clinic")
        self.categories: str = os.getenv("CATEGORIES", "appointments,billing,insurance,general,other")


@lru_cache
def get_settings() -> Settings:
    return Settings()
