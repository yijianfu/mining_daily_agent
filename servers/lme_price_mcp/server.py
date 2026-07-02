"""LME Price MCP Server — entry point.

Provides tools for querying commodity metal prices and price trends.
Supports stdio (local) and SSE (Docker/remote) transports.

Usage:
    # Local (stdio):
    python -m servers.lme_price_mcp.server

    # Docker (SSE):
    MCP_TRANSPORT=sse MCP_PORT=8000 python -m servers.lme_price_mcp.server
"""

import sys
import os

# Ensure project root is on path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server.fastmcp import FastMCP
from loguru import logger

from servers.shared.logging_base import setup_logging
from servers.shared.base_server import BaseMCPServer
from servers.lme_price_mcp.tools import get_price, get_trend

# ── Initialize ───────────────────────────────────────────────────────────────

setup_logging("lme-price-mcp", use_stderr=True)

mcp = FastMCP(
    name="lme-price-mcp",
    description="LME and commodity metal price data — current prices and trends",
)

server = BaseMCPServer(
    mcp=mcp,
    name="lme-price-mcp",
    description="Commodity metal prices via LME and other exchanges",
)

# ── Register Tools ───────────────────────────────────────────────────────────


@mcp.tool()
def tool_get_price(commodity: str, date: str | None = None) -> str:
    """Get the current or historical price for a commodity.

    Supported commodities: copper, lithium, nickel, gold, silver,
    iron ore, zinc, aluminum, uranium, cobalt, tin, lead.

    Args:
        commodity: Commodity name (case-insensitive, e.g. "copper", "Lithium").
        date: Optional date in YYYY-MM-DD format. Defaults to today.
    """
    logger.info(f"Tool call: get_price(commodity={commodity!r}, date={date!r})")
    return get_price(commodity=commodity, date=date)


@mcp.tool()
def tool_get_trend(commodity: str, days: int = 30) -> str:
    """Get price trend for a commodity over a number of days.

    Includes price series and statistical summary (change %, min/max,
    volatility, trend direction).

    Args:
        commodity: Commodity name (case-insensitive).
        days: Calendar days to look back. Defaults to 30.
    """
    logger.info(f"Tool call: get_trend(commodity={commodity!r}, days={days})")
    return get_trend(commodity=commodity, days=days)


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("LME Price MCP Server starting")
    server.run()
