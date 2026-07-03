"""Mineral PDF MCP Server — entry point.

Provides tools for extracting NI 43-101 mineral resource data from PDFs.
Supports stdio (local) and SSE (Docker/remote) transports.

Usage:
    # Local (stdio):
    python -m servers.mineral_pdf_mcp.server

    # Docker (SSE):
    MCP_TRANSPORT=sse MCP_PORT=8000 python -m servers.mineral_pdf_mcp.server
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server.fastmcp import FastMCP
from loguru import logger

from servers.shared.logging_base import setup_logging
from servers.shared.base_server import BaseMCPServer
from servers.mineral_pdf_mcp.tools import extract_resources

# ── Initialize ───────────────────────────────────────────────────────────────

setup_logging("mineral-pdf-mcp", use_stderr=True)

mcp = FastMCP(name="mineral-pdf-mcp")

server = BaseMCPServer(
    mcp=mcp,
    name="mineral-pdf-mcp",
    description="Extract mineral resource data from NI 43-101 technical report PDFs",
)

# ── Register Tools ───────────────────────────────────────────────────────────


@mcp.tool()
def tool_extract_resources(pdf_url: str) -> str:
    """Extract mineral resource estimates from an NI 43-101 technical report PDF.

    Parses the PDF for resource tables and text, extracting Measured,
    Indicated, and Inferred resource categories with tonnage, grade,
    and contained metal data. Falls back to mock data for known deposits
    when the PDF is unavailable.

    Args:
        pdf_url: URL of the NI 43-101 PDF report to parse.
    """
    logger.info(f"Tool call: extract_resources(pdf_url={pdf_url!r})")
    return extract_resources(pdf_url=pdf_url)


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Mineral PDF MCP Server starting")
    server.run()
