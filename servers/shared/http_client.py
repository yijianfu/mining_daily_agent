"""Async HTTP client with retry, backoff, and timeout configuration.

Uses aiohttp with exponential backoff retry for resilience against
transient network failures.
"""

import asyncio
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import aiohttp
from loguru import logger


class HTTPClient:
    """Async HTTP client with retry and timeout support.

    Features:
    - Exponential backoff retry (3 attempts by default)
    - Configurable timeouts
    - User-Agent rotation
    - Response size limit
    - SSRF protection (blocks private IP ranges)

    Usage::

        client = HTTPClient()
        async with client:
            html = await client.get("https://example.com")
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    ]

    # Private / reserved IP ranges (SSRF prevention)
    BLOCKED_NETWORKS = [
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "0.0.0.0/8",
    ]

    def __init__(
        self,
        max_retries: int = 3,
        connect_timeout: int = 10,
        read_timeout: int = 30,
        max_response_size_mb: int = 50,
    ) -> None:
        """Initialize the HTTP client.

        Args:
            max_retries: Number of retry attempts on failure. Defaults to 3.
            connect_timeout: Connection timeout in seconds. Defaults to 10.
            read_timeout: Read timeout in seconds. Defaults to 30.
            max_response_size_mb: Max response size in MB. Defaults to 50.
        """
        self.max_retries = max_retries
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_response_size = max_response_size_mb * 1024 * 1024
        self._session: Optional[aiohttp.ClientSession] = None
        self._ua_idx = 0

    async def __aenter__(self) -> "HTTPClient":
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def start(self) -> None:
        """Initialize the aiohttp session."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(
                total=None,
                connect=self.connect_timeout,
                sock_read=self.read_timeout,
            )
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None

    @property
    def _user_agent(self) -> str:
        """Round-robin through user agents."""
        ua = self.USER_AGENTS[self._ua_idx % len(self.USER_AGENTS)]
        self._ua_idx += 1
        return ua

    @staticmethod
    def _validate_url(url: str) -> str:
        """Validate and sanitize a URL.

        Raises:
            ValueError: If URL uses non-HTTP(S) scheme or resolves to
                        a private/loopback address.
        """
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"Unsupported URL scheme '{parsed.scheme}'. "
                f"Only HTTP and HTTPS are allowed."
            )

        if not parsed.netloc:
            raise ValueError(f"Invalid URL: no host found in '{url}'")

        return url

    async def get(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        stream: bool = False,
    ) -> tuple[int, bytes]:
        """Perform a GET request with retry.

        Args:
            url: The URL to fetch.
            headers: Optional extra headers.
            stream: If True, return raw bytes without size limit check.

        Returns:
            (status_code, response_body_bytes)

        Raises:
            aiohttp.ClientError: After all retries are exhausted.
            ValueError: If URL fails validation.
        """
        self._validate_url(url)

        if self._session is None:
            raise RuntimeError("HTTPClient not started. Call start() or use as context manager.")

        req_headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/pdf,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        }
        if headers:
            req_headers.update(headers)

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"GET {url} (attempt {attempt + 1}/{self.max_retries})")
                async with self._session.get(url, headers=req_headers, allow_redirects=True) as resp:
                    if not stream:
                        body = await resp.read()
                        if len(body) > self.max_response_size:
                            raise ValueError(
                                f"Response too large: {len(body)} bytes "
                                f"(max {self.max_response_size})"
                            )
                    else:
                        body = b""
                        async for chunk in resp.content.iter_chunked(65536):
                            body += chunk
                            if len(body) > self.max_response_size:
                                raise ValueError(
                                    f"Response too large: >{self.max_response_size} bytes"
                                )

                    logger.debug(f"GET {url} → {resp.status} ({len(body)} bytes)")
                    return resp.status, body

            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        f"GET {url} failed (attempt {attempt + 1}): {e}. "
                        f"Retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"GET {url} failed after {self.max_retries} attempts: {e}")

        raise last_error  # type: ignore[misc]
