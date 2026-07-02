"""Configuration for the Mineral PDF MCP server."""

import os


class PDFConfig:
    """Server configuration loaded from environment variables."""

    @property
    def max_pdf_size_mb(self) -> int:
        """Maximum PDF file size in MB."""
        return int(os.getenv("PDF_MAX_SIZE_MB", "50"))

    @property
    def cache_ttl(self) -> int:
        """Cache TTL for extracted resource data (seconds). Default: 86400s (1 day)."""
        return int(os.getenv("PDF_CACHE_TTL", "86400"))

    @property
    def download_timeout(self) -> int:
        """PDF download timeout in seconds."""
        return int(os.getenv("PDF_DOWNLOAD_TIMEOUT", "60"))

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")


pdf_config = PDFConfig()
