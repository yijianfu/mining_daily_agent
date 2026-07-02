"""Tool implementations for the Mining News MCP server.

Provides:
- search_mining_news: Search RSS feeds for mining-related articles
- fetch_article: Get full article body text
"""

import json
import sys
import os
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger

from servers.shared.cache_base import TTLCache
from servers.shared.async_utils import run_async
from servers.mining_news_mcp.config import news_config
from servers.mining_news_mcp.models import NewsArticle, SearchResult
from servers.mining_news_mcp.fetchers.rss_fetcher import RSSFetcher
from servers.mining_news_mcp.fetchers.article_fetcher import ArticleFetcher

# In-memory caches
_search_cache = TTLCache[str, str](
    ttl_seconds=news_config.cache_ttl_search, max_size=200
)
_article_cache = TTLCache[str, str](
    ttl_seconds=news_config.cache_ttl_article, max_size=500
)

# Lazy-init fetchers
_rss_fetcher: Optional[RSSFetcher] = None
_article_fetcher: Optional[ArticleFetcher] = None

# Mock data for offline/demo use
MOCK_NEWS: list[dict] = [
    {
        "title": "Pilbara Lithium Production Hits Record as Greenbushes Expands",
        "url": "https://www.mining.com/pilbara-lithium-production-record-greenbushes/",
        "source": "Mining.com",
        "published_date": datetime.now().strftime("%Y-%m-%d"),
        "snippet": "Pilbara Minerals reported record spodumene concentrate production at its Pilgangoora operation, while the Greenbushes joint venture announced expansion plans to meet growing EV battery demand from Asian markets.",
    },
    {
        "title": "Lithium Prices Stabilize After Months of Decline",
        "url": "https://www.kitco.com/commentaries/lithium-prices-stabilize-2026/",
        "source": "Kitco Mining",
        "published_date": datetime.now().strftime("%Y-%m-%d"),
        "snippet": "Lithium carbonate spot prices in China showed signs of stabilization this week after a prolonged downturn, with market analysts pointing to production cuts and resilient EV sales as supporting factors.",
    },
    {
        "title": "Western Australia Approves New Critical Minerals Exploration Licenses",
        "url": "https://www.miningweekly.com/article/wa-approves-critical-minerals-exploration-2026-07/",
        "source": "Mining Weekly",
        "published_date": datetime.now().strftime("%Y-%m-%d"),
        "snippet": "The Western Australian government has granted 15 new exploration licenses focused on critical minerals including lithium, rare earths, and nickel across the Pilbara and Goldfields regions.",
    },
    {
        "title": "NI 43-101 Update: Pilgangoora Measured Resources Increase 22%",
        "url": "https://www.juniorminingnetwork.com/pilbara-minerals-43-101-update.html",
        "source": "Junior Mining Network",
        "published_date": datetime.now().strftime("%Y-%m-%d"),
        "snippet": "Pilbara Minerals Ltd. announced an updated NI 43-101 technical report for its 100%-owned Pilgangoora Lithium-Tantalum Project, showing a 22% increase in Measured and Indicated resources.",
    },
    {
        "title": "China EV Sales Surge Drives Lithium Demand Outlook Higher",
        "url": "https://www.mining.com/china-ev-sales-lithium-demand-outlook-2026/",
        "source": "Mining.com",
        "published_date": datetime.now().strftime("%Y-%m-%d"),
        "snippet": "Chinese electric vehicle sales surged 35% year-over-year in H1 2026, driving analysts to revise lithium demand forecasts upward and tightening the supply-demand balance for battery-grade lithium carbonate.",
    },
    {
        "title": "Rio Tinto Advances Rincon Lithium Project in Argentina",
        "url": "https://www.miningweekly.com/article/rio-tinto-rincon-lithium-update-2026-07/",
        "source": "Mining Weekly",
        "published_date": datetime.now().strftime("%Y-%m-%d"),
        "snippet": "Rio Tinto reported significant progress at its Rincon lithium brine project in Argentina, with first production targeted for 2028 and a planned capacity of 60,000 tonnes per annum of battery-grade lithium carbonate.",
    },
    {
        "title": "Gold Hits New All-Time High Above $2,700 on Rate Cut Expectations",
        "url": "https://www.kitco.com/news/gold-new-record-2700-rate-cut/",
        "source": "Kitco Mining",
        "published_date": datetime.now().strftime("%Y-%m-%d"),
        "snippet": "Gold surged past $2,700/oz for the first time as markets priced in aggressive Federal Reserve rate cuts for the second half of 2026, with mining equities following the metal higher.",
    },
    {
        "title": "Iron Ore Prices Face Headwinds from China Steel Production Cuts",
        "url": "https://www.mining.com/iron-ore-prices-china-steel-cuts-2026/",
        "source": "Mining.com",
        "published_date": datetime.now().strftime("%Y-%m-%d"),
        "snippet": "Iron ore prices retreated below $110/t as Chinese steel mills announced production cuts amid weakening domestic construction demand and tighter environmental regulations.",
    },
]


def _get_rss_fetcher() -> RSSFetcher:
    """Get or create the RSS fetcher singleton."""
    global _rss_fetcher
    if _rss_fetcher is None:
        _rss_fetcher = RSSFetcher(timeout=news_config.rss_timeout)
    return _rss_fetcher


def _get_article_fetcher() -> ArticleFetcher:
    """Get or create the article fetcher singleton."""
    global _article_fetcher
    if _article_fetcher is None:
        _article_fetcher = ArticleFetcher()
    return _article_fetcher


def _filter_mock_news(query: str, days: int, max_results: int) -> list[NewsArticle]:
    """Filter mock news data by query and recency."""
    query_terms = query.lower().split()
    results: list[NewsArticle] = []

    for item in MOCK_NEWS:
        text = f"{item['title']} {item['snippet']}".lower()
        if any(term in text for term in query_terms):
            results.append(NewsArticle(**item))

    return results[:max_results]


def search_mining_news(
    query: str,
    days: int = 7,
    max_results: int = 10,
) -> str:
    """Search for mining-related news articles.

    Searches RSS feeds from Mining.com, Kitco, Mining Weekly, and
    Junior Mining Network. Falls back to built-in mock data when
    RSS feeds are unavailable.

    Args:
        query: Search keywords (e.g. "Pilbara lithium", "gold price").
        days: How many days back to search. Defaults to 7.
        max_results: Maximum number of results. Defaults to 10.

    Returns:
        JSON string with SearchResult (list of articles with metadata).
    """
    cache_key = f"search:{query.lower()}:{days}:{max_results}"

    # Check cache
    cached = _search_cache.get(cache_key)
    if cached:
        logger.debug(f"Search cache hit: {cache_key}")
        return cached

    logger.info(f"Searching news: query='{query}', days={days}")

    articles: list[NewsArticle] = []
    sources_searched: list[str] = []

    # Try RSS first
    try:
        rss = _get_rss_fetcher()
        articles = run_async(rss.search(query, days, max_results))
        sources_searched = ["Mining.com RSS", "Mining Weekly RSS",
                            "Kitco RSS", "Junior Mining Network RSS"]
    except Exception as e:
        logger.warning(f"RSS search failed, using mock data: {e}")

    # Fallback to mock if RSS returned nothing
    if not articles:
        logger.info("No RSS results, using mock data")
        articles = _filter_mock_news(query, days, max_results)
        sources_searched = ["mock_data"]

    result = SearchResult(
        query=query,
        searched_days=days,
        total_results=len(articles),
        articles=articles,
        sources_searched=sources_searched,
    )

    json_str = result.model_dump_json(indent=2)
    _search_cache.set(cache_key, json_str)
    return json_str


def fetch_article(url: str) -> str:
    """Fetch and extract the full body text of a news article.

    Uses trafilatura for readability-based extraction.

    Args:
        url: The article URL to fetch.

    Returns:
        JSON string with ArticleBody (title, text, publisher, etc.).
    """
    cache_key = f"article:{url}"

    # Check cache
    cached = _article_cache.get(cache_key)
    if cached:
        logger.debug(f"Article cache hit: {cache_key}")
        return cached

    logger.info(f"Fetching article: {url}")

    try:
        fetcher = _get_article_fetcher()
        article = run_async(fetcher.fetch(url))
        json_str = article.model_dump_json(indent=2)
        _article_cache.set(cache_key, json_str)
        return json_str

    except Exception as e:
        logger.error(f"Failed to fetch article {url}: {e}")

        # Return mock article body for known URLs
        for mock in MOCK_NEWS:
            if mock["url"] == url:
                mock_body = {
                    "url": url,
                    "title": mock["title"],
                    "publisher": mock["source"],
                    "author": None,
                    "published_date": mock["published_date"],
                    "text": (
                        f"{mock['title']}\n\n{mock['snippet']}\n\n"
                        f"This article was retrieved from {mock['source']}. "
                    ),
                    "text_length": 0,
                    "fetch_method": "mock",
                }
                mock_body["text_length"] = len(mock_body["text"])
                return json.dumps(mock_body, ensure_ascii=False, indent=2)

        return json.dumps({
            "error": True,
            "error_code": "FETCH_ERROR",
            "message": str(e),
            "url": url,
        }, ensure_ascii=False)
