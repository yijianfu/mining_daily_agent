"""MCP Client setup for connecting to all three MCP servers.

Supports two transport modes:
- stdio: Spawns MCP servers as subprocesses (local dev)
- sse: Connects to already-running MCP servers via SSE (Docker)
"""

import sys
import os
from typing import Any, Optional

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

from agent.config import agent_config

# Project root for resolving server module paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_server_python_path() -> str:
    """Get the python executable path."""
    return sys.executable


def build_stdio_config() -> dict[str, dict[str, Any]]:
    """Build MCP client config for stdio transport (local development).

    Each server is spawned as a subprocess using
    `python -m servers.<server_name>.server`.

    Returns:
        Dict mapping server names to stdio connection configs.
    """
    python = get_server_python_path()

    return {
        "mining_news": {
            "command": python,
            "args": ["-m", "servers.mining_news_mcp.server"],
            "transport": "stdio",
            "cwd": PROJECT_ROOT,
        },
        "mineral_pdf": {
            "command": python,
            "args": ["-m", "servers.mineral_pdf_mcp.server"],
            "transport": "stdio",
            "cwd": PROJECT_ROOT,
        },
        "lme_price": {
            "command": python,
            "args": ["-m", "servers.lme_price_mcp.server"],
            "transport": "stdio",
            "cwd": PROJECT_ROOT,
        },
    }


def build_sse_config() -> dict[str, dict[str, Any]]:
    """Build MCP client config for SSE transport (Docker/remote).

    Connects to already-running MCP servers via HTTP SSE endpoints.

    Returns:
        Dict mapping server names to SSE connection configs.
    """
    return {
        "mining_news": {
            "url": agent_config.mcp_news_url,
            "transport": "sse",
        },
        "mineral_pdf": {
            "url": agent_config.mcp_pdf_url,
            "transport": "sse",
        },
        "lme_price": {
            "url": agent_config.mcp_lme_url,
            "transport": "sse",
        },
    }


async def create_mcp_client():
    """Create and initialize a MultiServerMCPClient.

    Auto-detects transport mode from AGENT_CONFIG, or defaults to stdio
    when running locally and sse when MCP_*_URL env vars are set.

    Returns:
        Initialized MultiServerMCPClient with all tools loaded.
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    transport = agent_config.mcp_transport

    if transport == "sse":
        config = build_sse_config()
        logger.info("Connecting to MCP servers via SSE transport")
    else:
        config = build_stdio_config()
        logger.info("Starting MCP servers via stdio transport")

    logger.info(f"MCP servers: {list(config.keys())}")

    client = MultiServerMCPClient(config)

    # Load tools from all servers
    try:
        tools = await client.get_tools()
        logger.info(f"Loaded {len(tools)} tools from MCP servers:")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description[:80]}...")
    except Exception as e:
        logger.error(f"Failed to load MCP tools: {e}")
        raise

    return client


async def get_tools_for_agent():
    """Get MCP tools pre-filtered for the agent.

    Returns:
        Tuple of (client, tools_list).
    """
    client = await create_mcp_client()
    tools = await client.get_tools()
    return client, tools
