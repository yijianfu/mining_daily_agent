"""Configuration for the Agent Client."""

import os
from typing import Optional


class AgentConfig:
    """Agent configuration loaded from environment variables."""

    @property
    def model_provider(self) -> str:
        """LLM provider: 'anthropic' or 'openai'."""
        return os.getenv("MODEL_PROVIDER", "anthropic")

    @property
    def model_name(self) -> str:
        """Model name to use."""
        return os.getenv(
            "MODEL_NAME",
            "claude-sonnet-4-20250514",
        )

    @property
    def anthropic_api_key(self) -> Optional[str]:
        return os.getenv("ANTHROPIC_API_KEY")

    @property
    def openai_api_key(self) -> Optional[str]:
        return os.getenv("OPENAI_API_KEY")

    @property
    def mcp_news_url(self) -> str:
        """URL for mining-news MCP server (SSE mode)."""
        return os.getenv(
            "MCP_NEWS_URL",
            "http://localhost:8001/sse",
        )

    @property
    def mcp_pdf_url(self) -> str:
        """URL for mineral-pdf MCP server (SSE mode)."""
        return os.getenv(
            "MCP_PDF_URL",
            "http://localhost:8002/sse",
        )

    @property
    def mcp_lme_url(self) -> str:
        """URL for lme-price MCP server (SSE mode)."""
        return os.getenv(
            "MCP_LME_URL",
            "http://localhost:8003/sse",
        )

    @property
    def mcp_transport(self) -> str:
        """MCP transport mode: 'stdio' or 'sse'."""
        return os.getenv("MCP_CLIENT_TRANSPORT", "stdio")

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def max_retries(self) -> int:
        return int(os.getenv("AGENT_MAX_RETRIES", "3"))


agent_config = AgentConfig()
