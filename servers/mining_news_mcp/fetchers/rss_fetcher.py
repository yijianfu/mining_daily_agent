"""RSS feed aggregator for mining industry news.

Fetches articles from working RSS feeds with robust error handling.
"""

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
from loguru import logger

from servers.mining_news_mcp.models import NewsArticle

# Curated working mining RSS feeds (verified 2026-07)
RSS_FEEDS: list[dict[str, str]] = [
    {
        "name": "Mining.com",
        "url": "https://www.mining.com/feed/",
    },
    {
        "name": "Mining Technology",
        "url": "https://www.mining-technology.com/feed/",
    },
    {
        "name": "Reuters Commodities",
        "url": "https://news.google.com/rss/search?q=mining+commodities&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "S&P Global Mining",
        "url": "https://news.google.com/rss/search?q=%22mining+industry%22+metals&hl=en-US&gl=US&ceid=US:en",
    },
]


class RSSFetcher:
    """Fetch mining news from RSS feeds with relaxed matching.

    Failed feeds are silently skipped — partial results are fine.
    """

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    async def search(
        self,
        query: str,
        days: int = 7,
        max_results: int = 10,
    ) -> list[NewsArticle]:
        """Search RSS feeds for articles matching a query.

        Matching is relaxed: any article containing at least one word
        from the query gets included. If RSS returns nothing, returns
        an empty list (caller handles mock fallback).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        all_articles: list[NewsArticle] = []
        query_terms = [t for t in query.lower().split() if len(t) > 1]

        logger.info(f"Searching {len(RSS_FEEDS)} feeds for '{query}'")

        tasks = [self._fetch_feed(f) for f in RSS_FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for feed_info, result in zip(RSS_FEEDS, results):
            if isinstance(result, Exception):
                logger.debug(f"{feed_info['name']}: {result}")
                continue

            matched = 0
            for entry in result:
                text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                if not query_terms or not self._matches_query(text, query_terms):
                    continue

                pub_date = self._parse_date(entry)
                if pub_date and pub_date < cutoff:
                    continue

                all_articles.append(self._to_article(entry, feed_info["name"]))
                matched += 1

            if matched:
                logger.info(f"{feed_info['name']}: {matched} matches")

        all_articles.sort(key=lambda a: a.published_date or "", reverse=True)
        result = all_articles[:max_results]

        logger.info(f"RSS total: {len(result)} articles")
        return result

    async def _fetch_feed(self, feed_info: dict[str, str]) -> list[dict]:
        """Fetch and parse a single RSS feed."""
        logger.debug(f"Fetching {feed_info['name']}")
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, lambda: feedparser.parse(feed_info["url"]))

        if feed.bozo and not feed.entries:
            raise ValueError(f"Parse error: {feed.bozo_exception}")

        logger.debug(f"{feed_info['name']}: {len(feed.entries)} entries")
        return feed.entries

    @staticmethod
    def _matches_query(text: str, terms: list[str]) -> bool:
        """Match if text contains ANY query term (relaxed OR)."""
        return any(t in text for t in terms)

    @staticmethod
    def _parse_date(entry: dict) -> Optional[datetime]:
        """Extract pub date from feed entry."""
        for attr in ("published_parsed", "updated_parsed"):
            val = entry.get(attr)
            if val:
                try:
                    from time import mktime
                    return datetime.fromtimestamp(mktime(val), tz=timezone.utc)
                except Exception:
                    pass
        return None

    @staticmethod
    def _to_article(entry: dict, source: str) -> NewsArticle:
        """Convert feed entry to NewsArticle."""
        pub_date = None
        parsed = RSSFetcher._parse_date(entry)
        if parsed:
            pub_date = parsed.strftime("%Y-%m-%d")

        link = entry.get("link", "")
        if isinstance(link, list):
            link = next((l.get("href", "") for l in link if l.get("href")), "")

        summary = entry.get("summary", entry.get("description", ""))
        summary = re.sub(r"<[^>]+>", "", summary).strip()[:300]

        return NewsArticle(
            title=entry.get("title", "Untitled"),
            url=link,
            source=source,
            published_date=pub_date,
            snippet=summary or None,
        )
