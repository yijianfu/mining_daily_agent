"""Shared utilities for all MCP servers.

Provides:
- TTLCache: In-memory time-to-live cache
- Logging: Structured logging via loguru
- HTTPClient: Async HTTP client with retry and backoff
- BaseMCPServer: FastMCP server wrapper with lifecycle hooks
"""

from servers.shared.cache_base import TTLCache
from servers.shared.logging_base import setup_logging
from servers.shared.http_client import HTTPClient
from servers.shared.base_server import BaseMCPServer

__all__ = ["TTLCache", "setup_logging", "HTTPClient", "BaseMCPServer"]
