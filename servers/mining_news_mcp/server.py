"""Mining News MCP Server — entry point.

Provides tools for searching mining news and fetching full article text.
Supports stdio (local) and SSE (Docker/remote) transports.

Usage:
    # Local (stdio):
    python -m servers.mining_news_mcp.server

    # Docker (SSE):
    MCP_TRANSPORT=sse MCP_PORT=8000 python -m servers.mining_news_mcp.server
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server.fastmcp import FastMCP
from loguru import logger

from servers.shared.logging_base import setup_logging
from servers.shared.base_server import BaseMCPServer
from servers.mining_news_mcp.tools import search_mining_news, fetch_article

# ── Initialize ───────────────────────────────────────────────────────────────

setup_logging("mining-news-mcp", use_stderr=True)

mcp = FastMCP(
    name="mining-news-mcp",
    description="Mining industry news search and article fetching",
)

server = BaseMCPServer(
    mcp=mcp,
    name="mining-news-mcp",
    description="Search mining news from RSS feeds and fetch article bodies",
)

# ── Register Tools ───────────────────────────────────────────────────────────


@mcp.tool()
def tool_search_mining_news(
    query: str,
    days: int = 7,
    max_results: int = 10,
) -> str:
    """Search for mining-related news articles from major mining news sources.

    Covers Mining.com, Kitco, Mining Weekly, Junior Mining Network, and more.
    Falls back to built-in data when feeds are unavailable.

    Args:
        query: Search keywords (e.g. "Pilbara lithium", "copper price forecast").
        days: How many days back to search. Defaults to 7.
        max_results: Maximum number of results to return. Defaults to 10.
    """
    logger.info(f"Tool call: search_mining_news(query={query!r}, days={days})")
    return search_mining_news(query=query, days=days, max_results=max_results)


@mcp.tool()
def tool_fetch_article(url: str) -> str:
    """Fetch the full body text of a news article.

    Uses trafilatura for readability-based extraction, removing ads,
    navigation, and other non-content elements.

    Args:
        url: The article URL to fetch.
    """
    logger.info(f"Tool call: fetch_article(url={url!r})")
    return fetch_article(url=url)


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Mining News MCP Server starting")
    server.run()
