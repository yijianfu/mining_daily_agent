"""Article body extraction via trafilatura.

Downloads HTML and extracts clean article text, stripping navigation,
ads, and other non-content elements.
"""

import re
from typing import Optional

from loguru import logger

from servers.shared.http_client import HTTPClient
from servers.mining_news_mcp.models import ArticleBody


class ArticleFetcher:
    """Fetches and extracts clean article body text from news URLs.

    Uses trafilatura for readability-style extraction with fallback
    to basic HTML tag stripping. Each call creates and closes its own
    HTTP session to avoid resource leaks.
    """

    async def fetch(self, url: str) -> ArticleBody:
        """Fetch and extract clean article text from a URL.

        Args:
            url: Article URL.

        Returns:
            ArticleBody with extracted text and metadata.

        Raises:
            ValueError: If URL is invalid or page cannot be parsed.
        """
        logger.info(f"Fetching article: {url}")

        async with HTTPClient(max_retries=2, read_timeout=20) as http:
            status, html_bytes = await http.get(url)
            html = html_bytes.decode("utf-8", errors="replace")

            if status != 200:
                raise ValueError(
                    f"HTTP {status} when fetching article: {url}"
                )

            # Try trafilatura first
            try:
                import trafilatura

                # Note: trafilatura API changed in v2.x — pass bytes directly
                extracted = trafilatura.extract(
                    html_bytes,
                    include_comments=False,
                    include_tables=False,
                    include_images=False,
                    include_links=True,
                    output_format="markdown",
                    with_metadata=True,
                    url=url,
                )

                if extracted:
                    return self._build_article(url, html, extracted, "trafilatura")
            except Exception as e:
                logger.warning(f"trafilatura extraction failed for {url}: {e}")

            # Fallback: basic text extraction
            logger.info(f"Using fallback extraction for {url}")
            text = self._fallback_extract(html)
            return self._build_article(url, html, text, "fallback_html")

    def _build_article(
        self, url: str, raw_html: str, text: str, method: str
    ) -> ArticleBody:
        """Build ArticleBody from extracted text."""
        title = "Unknown"
        lines = text.strip().split("\n")
        if lines:
            first_line = lines[0].strip()
            if len(first_line) < 200 and not first_line.startswith("http"):
                title = first_line

        return ArticleBody(
            url=url,
            title=title,
            publisher=None,
            author=None,
            published_date=None,
            text=text.strip(),
            text_length=len(text.strip()),
            fetch_method=method,
        )

    @staticmethod
    def _fallback_extract(html: str) -> str:
        """Basic HTML to text extraction — strips tags, scripts, styles."""
        text = re.sub(
            r"<(script|style|nav|header|footer|iframe|noscript)[^>]*>.*?"
            r"</\1>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(r"<(script|style|iframe)[^>]*/>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)

        import html as html_mod
        text = html_mod.unescape(text)

        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()
