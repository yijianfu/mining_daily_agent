"""RSS feed aggregator for mining industry news.

Collects articles from major mining news RSS feeds including
Mining.com, Kitco, Mining Weekly, and Junior Mining Network.
No API key required.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
from loguru import logger

from servers.mining_news_mcp.models import NewsArticle

# Major mining news RSS feeds
RSS_FEEDS: list[dict[str, str]] = [
    {
        "name": "Mining.com",
        "url": "https://www.mining.com/feed/",
        "category": "general",
    },
    {
        "name": "Mining Weekly",
        "url": "https://www.miningweekly.com/page/feed",
        "category": "general",
    },
    {
        "name": "Kitco Mining",
        "url": "https://www.kitco.com/mining/feed",
        "category": "precious_metals",
    },
    {
        "name": "Junior Mining Network",
        "url": "https://www.juniorminingnetwork.com/component/obrss/junior-mining-network-press-releases.html",
        "category": "juniors",
    },
    {
        "name": "Australian Mining",
        "url": "https://www.australianmining.com.au/feed/",
        "category": "regional",
    },
]


class RSSFetcher:
    """Fetches and aggregates mining news from RSS feeds.

    Searches feeds for articles matching a query and time window.
    Handles feed parse failures gracefully — a broken feed is skipped
    rather than failing the entire search.
    """

    def __init__(self, timeout: int = 15) -> None:
        """Initialize the RSS fetcher.

        Args:
            timeout: HTTP timeout per feed in seconds.
        """
        self.timeout = timeout

    async def search(
        self,
        query: str,
        days: int = 7,
        max_results: int = 10,
    ) -> list[NewsArticle]:
        """Search RSS feeds for mining news matching a query.

        Args:
            query: Search keywords.
            days: How many days back to search.
            max_results: Maximum number of articles to return.

        Returns:
            List of NewsArticle objects, sorted by recency.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        all_articles: list[NewsArticle] = []
        query_lower = query.lower().split()

        logger.info(
            f"Searching {len(RSS_FEEDS)} RSS feeds for '{query}' "
            f"(last {days} days)"
        )

        # Fetch all feeds concurrently
        tasks = [self._fetch_feed(feed_info) for feed_info in RSS_FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for feed_info, result in zip(RSS_FEEDS, results):
            if isinstance(result, Exception):
                logger.warning(
                    f"Failed to fetch {feed_info['name']}: {result}"
                )
                continue

            raw_articles = result
            for article in raw_articles:
                # Match query keywords against title + snippet
                text = f"{article.get('title', '')} {article.get('summary', '')}"
                if not self._matches_query(text.lower(), query_lower):
                    continue

                # Check date
                pub_date = self._parse_date(article)
                if pub_date and pub_date < cutoff:
                    continue

                all_articles.append(self._to_news_article(article, feed_info["name"]))

        # Sort by date (newest first) and limit
        all_articles.sort(
            key=lambda a: a.published_date or "",
            reverse=True,
        )

        result = all_articles[:max_results]
        logger.info(
            f"RSS search for '{query}': {len(result)} results "
            f"(from {len(all_articles)} total)"
        )
        return result

    async def _fetch_feed(self, feed_info: dict[str, str]) -> list[dict]:
        """Fetch and parse a single RSS feed.

        Args:
            feed_info: Dict with 'name' and 'url' keys.

        Returns:
            List of raw feed entry dicts.
        """
        logger.debug(f"Fetching RSS: {feed_info['name']}")
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(
            None,
            lambda: feedparser.parse(feed_info["url"]),
        )

        if feed.bozo and not feed.entries:
            raise ValueError(
                f"Feed parse error for {feed_info['name']}: {feed.bozo_exception}"
            )

        logger.debug(f"{feed_info['name']}: {len(feed.entries)} entries")
        return feed.entries

    @staticmethod
    def _matches_query(text: str, query_terms: list[str]) -> bool:
        """Check if text matches any query term."""
        return any(term in text for term in query_terms)

    @staticmethod
    def _parse_date(entry: dict) -> Optional[datetime]:
        """Extract publication date from a feed entry."""
        # Try published_parsed first
        if hasattr(entry, "published_parsed") and entry.get("published_parsed"):
            try:
                from time import mktime
                return datetime.fromtimestamp(
                    mktime(entry.published_parsed), tz=timezone.utc
                )
            except Exception:
                pass

        # Try updated_parsed
        if hasattr(entry, "updated_parsed") and entry.get("updated_parsed"):
            try:
                from time import mktime
                return datetime.fromtimestamp(
                    mktime(entry.updated_parsed), tz=timezone.utc
                )
            except Exception:
                pass

        return None

    @staticmethod
    def _to_news_article(entry: dict, source: str) -> NewsArticle:
        """Convert a raw feed entry to a NewsArticle model."""
        pub_date: Optional[str] = None
        parsed = RSSFetcher._parse_date(entry)
        if parsed:
            pub_date = parsed.strftime("%Y-%m-%d")

        # Get the first non-empty link
        link = entry.get("link", "")
        if isinstance(link, list):
            # Some feeds provide multiple links
            link = next(
                (l.get("href", "") for l in link if l.get("href")),
                "",
            )

        # Clean HTML from summary
        import re
        summary = entry.get("summary", entry.get("description", ""))
        summary = re.sub(r"<[^>]+>", "", summary)
        summary = summary.strip()[:300] if summary else ""

        return NewsArticle(
            title=entry.get("title", "Untitled"),
            url=link,
            source=source,
            published_date=pub_date,
            snippet=summary if summary else None,
        )
