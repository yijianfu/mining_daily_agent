"""Tool implementations for the Mineral PDF MCP server.

Provides:
- extract_resources: Parse NI 43-101 PDF and extract mineral resource data
"""

import json
import sys
import os
import hashlib
import tempfile
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger

from servers.shared.cache_base import TTLCache
from servers.shared.http_client import HTTPClient
from servers.shared.async_utils import run_async
from servers.mineral_pdf_mcp.config import pdf_config
from servers.mineral_pdf_mcp.schemas import MineralResourceReport
from servers.mineral_pdf_mcp.extractors.pdf_parser import PDFParser
from servers.mineral_pdf_mcp.extractors.table_extractor import TableExtractor
from servers.mineral_pdf_mcp.extractors.resource_parser import ResourceParser

# Cache: keyed on SHA256(pdf_url)
_cache = TTLCache[str, str](
    ttl_seconds=pdf_config.cache_ttl, max_size=100
)


def _cache_key_for_url(url: str) -> str:
    """Generate a cache key from a URL."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"extract:{url_hash}"


def extract_resources(pdf_url: str) -> str:
    """Extract mineral resource estimates from an NI 43-101 PDF report.

    Downloads the PDF, parses it for resource tables and text, and
    extracts Measured, Indicated, and Inferred resource data
    (tonnage, grade, contained metal) for each commodity.

    Falls back to mock data when a real PDF cannot be obtained.

    Args:
        pdf_url: URL of the NI 43-101 PDF report.

    Returns:
        JSON string with MineralResourceReport (deposits, commodities,
        tonnage, grade, contained metal, confidence, warnings).
    """
    cache_key = _cache_key_for_url(pdf_url)

    # Check cache
    cached = _cache.get(cache_key)
    if cached:
        logger.debug(f"Extraction cache hit: {cache_key}")
        return cached

    logger.info(f"Extracting resources from: {pdf_url}")

    try:
        # Download and parse
        http = HTTPClient(
            max_retries=2,
            read_timeout=pdf_config.download_timeout,
            max_response_size_mb=pdf_config.max_pdf_size_mb,
        )

        result = run_async(_do_extract(pdf_url, http))
        json_str = result.model_dump_json(indent=2)
        _cache.set(cache_key, json_str)
        return json_str

    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")

        # Fallback: return mock data for known projects
        logger.info("Falling back to mock data")
        mock_result = ResourceParser.mock_report(pdf_url)
        json_str = mock_result.model_dump_json(indent=2)
        _cache.set(cache_key, json_str)
        return json_str


async def _do_extract(
    pdf_url: str,
    http: HTTPClient,
) -> MineralResourceReport:
    """Execute the full PDF download and extraction pipeline.

    Args:
        pdf_url: URL of the PDF.
        http: HTTP client instance.

    Returns:
        MineralResourceReport with extracted data.
    """
    try:
        await http.start()

        # Step 1: Download PDF
        status, data = await http.get(pdf_url)

        if status != 200:
            raise ValueError(f"HTTP {status} downloading PDF")

        if not data.startswith(b"%PDF"):
            raise ValueError("Response is not a valid PDF file")

        # Step 2: Write to temp file
        tmp_path: Optional[str] = None
        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False, prefix="ni43_101_"
            )
            tmp.write(data)
            tmp.close()
            tmp_path = tmp.name

            logger.info(
                f"PDF downloaded: {len(data)} bytes → {tmp_path}"
            )

            # Step 3: Extract full text (for context + text-based parsing)
            with PDFParser(tmp_path) as parser:
                full_text = parser.extract_full_text()
                logger.info(
                    f"Extracted {len(full_text)} chars from {parser.page_count} pages"
                )

                # Step 4: Try table-based extraction
                tables = TableExtractor.find_resource_tables(tmp_path)
                logger.info(f"Found {len(tables)} resource tables")

                if tables:
                    report = ResourceParser.parse_from_tables(
                        tables, pdf_url, full_text
                    )
                else:
                    # Step 5: Fallback to text-based parsing
                    logger.info("No tables found, trying text-based extraction")
                    report = ResourceParser.parse_from_text(
                        full_text, pdf_url
                    )

                return report

        finally:
            # Clean up temp file
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
                logger.debug(f"Cleaned up temp file: {tmp_path}")

    finally:
        await http.close()
