"""Configuration for the LME Price MCP server.

Settings are read from environment variables with sensible defaults.
"""

import os
from typing import Optional


class LMEConfig:
    """Server configuration loaded from environment variables."""

    @property
    def provider(self) -> str:
        """Price data provider: 'mock' or 'itick'."""
        return os.getenv("LME_PRICE_PROVIDER", "mock")

    @property
    def itick_api_key(self) -> Optional[str]:
        """iTick API key (required when provider='itick')."""
        return os.getenv("ITICK_API_KEY")

    @property
    def cache_ttl_current(self) -> int:
        """Cache TTL for current prices (seconds). Default: 60s."""
        return int(os.getenv("LME_CACHE_TTL_CURRENT", "60"))

    @property
    def cache_ttl_history(self) -> int:
        """Cache TTL for price history (seconds). Default: 300s."""
        return int(os.getenv("LME_CACHE_TTL_HISTORY", "300"))

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")


lme_config = LMEConfig()
