"""Configuration for the Mining News MCP server."""

import os


class NewsConfig:
    """Server configuration loaded from environment variables."""

    @property
    def rss_timeout(self) -> int:
        """Timeout per RSS feed in seconds."""
        return int(os.getenv("NEWS_RSS_TIMEOUT", "15"))

    @property
    def cache_ttl_search(self) -> int:
        """Cache TTL for search results (seconds). Default: 300s."""
        return int(os.getenv("NEWS_CACHE_TTL_SEARCH", "300"))

    @property
    def cache_ttl_article(self) -> int:
        """Cache TTL for article bodies (seconds). Default: 3600s."""
        return int(os.getenv("NEWS_CACHE_TTL_ARTICLE", "3600"))

    @property
    def newsapi_key(self) -> str | None:
        """NewsAPI key for additional search (optional)."""
        return os.getenv("NEWSAPI_KEY")

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def max_article_size_kb(self) -> int:
        """Max article body size in KB."""
        return int(os.getenv("NEWS_MAX_ARTICLE_KB", "500"))


news_config = NewsConfig()
