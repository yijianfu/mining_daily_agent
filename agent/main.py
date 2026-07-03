"""Mining Daily Agent — CLI entry point.

Invokes the LangGraph agent to generate a mining industry daily briefing.

Usage:
    # Default (Pilbara lithium):
    python -m agent.main

    # Custom query:
    python -m agent.main "给我生成一份关于 Greenbushes 锂矿的今日简报"

    # Save to file:
    python -m agent.main "Gold mining in Nevada" -o report.md

    # SSE mode (connect to running Docker MCP servers):
    MCP_CLIENT_TRANSPORT=sse python -m agent.main
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# Ensure project root is on path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Auto-load .env file from project root (platform-agnostic, no shell export needed)
try:
    from dotenv import load_dotenv
    _env_file = _PROJECT_ROOT / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
except ImportError:
    pass

from langchain_core.messages import HumanMessage
from loguru import logger

from agent.config import agent_config
from agent.state import AgentState
from agent.graph import build_graph
from agent.mcp_clients import create_mcp_client
from servers.shared.logging_base import setup_logging

# Default query for demo
DEFAULT_QUERY = "给我生成一份关于 Pilbara 锂矿的今日简报"


async def run_agent(
    query: str,
    output_file: Optional[str] = None,
    verbose: bool = False,
) -> str:
    """Run the Mining Daily Agent with the given query.

    Args:
        query: Natural language briefing request.
        output_file: Optional path to save the report.
        verbose: If True, print intermediate steps.

    Returns:
        The generated markdown report string.
    """
    setup_logging("mining-agent", use_stderr=verbose)

    logger.info(f"Mining Daily Agent starting")
    logger.info(f"Query: {query}")

    mcp_client = None
    mcp_tools = None

    try:
        # Step 1: Connect to MCP servers
        logger.info("Connecting to MCP servers...")
        try:
            mcp_client = await create_mcp_client()
            mcp_tools = await mcp_client.get_tools()
            logger.info(f"Connected: {len(mcp_tools)} tools available")
        except Exception as e:
            logger.warning(f"MCP connection failed ({e}), running in degraded mode")
            mcp_tools = None

        # Step 2: Build the graph
        graph = build_graph(mcp_tools=mcp_tools)

        # Step 3: Run the graph
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query)],
            "user_query": query,
            "topic": None,
            "commodities": [],
            "news_summary": "",
            "resource_data": "",
            "price_data": "",
            "risk_warnings": [],
            "report_markdown": "",
            "phase": "planning",
            "errors": [],
        }

        logger.info("Running agent pipeline...")

        config = {"configurable": {"thread_id": "mining-daily-session"}}
        final_state = await graph.ainvoke(initial_state, config)

        report = final_state.get("report_markdown", "")

        if not report:
            logger.error("No report generated")
            report = "**Error**: Failed to generate briefing report."

        # Step 4: Output
        logger.info(f"Report generated: {len(report)} characters")

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report)
            logger.info(f"Report saved to: {output_file}")

        return report

    finally:
        # Cleanup
        if mcp_client:
            try:
                await mcp_client.close()
                logger.info("MCP client closed")
            except Exception as e:
                logger.warning(f"MCP client close error: {e}")


async def run_standalone(query: str) -> str:
    """Run the agent without MCP servers (standalone mode).

    Uses built-in mock data from each server's tools directly.

    Args:
        query: Natural language briefing request.

    Returns:
        Markdown report string.
    """
    setup_logging("mining-agent-standalone")

    logger.info(f"Running in standalone mode (no MCP servers)")
    logger.info(f"Query: {query}")

    # Import tools directly (they will use mock data internally)
    from servers.mining_news_mcp.tools import search_mining_news, fetch_article
    from servers.mineral_pdf_mcp.tools import extract_resources
    from servers.lme_price_mcp.tools import get_price, get_trend
    from agent.nodes import _fallback_extract, _build_fallback_report
    from agent.prompts import SYNTHESIS_PROMPT

    # Step 1: Extract topic and commodities
    topic, commodities = _fallback_extract(query)
    logger.info(f"Topic: {topic}, Commodities: {commodities}")

    # Step 2: Fetch news
    news_parts = []
    try:
        news_result = search_mining_news(query=topic, days=7, max_results=5)
        news_parts.append(f"### 搜索: \"{topic}\"\n\n{news_result}")

        # Try to parse articles and fetch bodies
        import json as _json
        try:
            data = _json.loads(news_result)
            for article in data.get("articles", [])[:2]:
                url = article.get("url", "")
                if url:
                    try:
                        body = fetch_article(url=url)
                        news_parts.append(f"### 文章全文\n\n{body}")
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"News search failed: {e}")

    for commodity in commodities:
        try:
            result = search_mining_news(query=f"{commodity} mining", days=7, max_results=3)
            news_parts.append(f"### {commodity} 新闻\n\n{result}")
        except Exception:
            pass

    news_summary = "\n\n".join(news_parts) if news_parts else "暂无数据"

    # Step 3: Fetch resources
    try:
        # Use known PDF URL
        resource_data = extract_resources(
            pdf_url=f"https://sedar.com/ni43-101/{topic.lower().replace(' ', '-')}.pdf"
        )
    except Exception as e:
        resource_data = f"资源提取失败: {e}"

    # Step 4: Fetch prices
    price_parts = []
    for commodity in commodities:
        try:
            price = get_price(commodity=commodity)
            price_parts.append(f"### {commodity} 当前价格\n\n{price}")
            trend = get_trend(commodity=commodity, days=30)
            price_parts.append(f"### {commodity} 30日走势\n\n{trend}")
        except Exception as e:
            logger.warning(f"Price fetch failed for {commodity}: {e}")

    price_data = "\n\n".join(price_parts) if price_parts else "暂无数据"

    # Step 5: Synthesize with LLM
    try:
        from agent.llm import get_model

        model = get_model()
        prompt = SYNTHESIS_PROMPT.format(
            user_query=query,
            topic=topic,
            commodities=", ".join(commodities),
            news_summary=news_summary[:8000],
            resource_data=resource_data[:5000],
            price_data=price_data[:5000],
            errors="无",
        )
        response = await model.ainvoke([HumanMessage(content=prompt)])
        report = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.warning(f"LLM synthesis failed ({e}), using fallback")
        # Build a basic state for fallback report
        state: AgentState = {
            "messages": [],
            "user_query": query,
            "topic": topic,
            "commodities": commodities,
            "news_summary": news_summary,
            "resource_data": resource_data,
            "price_data": price_data,
            "risk_warnings": [],
            "report_markdown": "",
            "phase": "synthesizing",
            "errors": [],
        }
        report = _build_fallback_report(state)

    return report


# ── CLI Entry Point ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Mining Daily Briefing Agent — generates mining industry daily reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent.main
  python -m agent.main "Gold mining in Nevada"
  python -m agent.main -o report.md
  python -m agent.main --standalone "铜矿市场分析"
        """,
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=DEFAULT_QUERY,
        help="Briefing request in natural language (default: Pilbara lithium)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: print to stdout)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose logs and intermediate results",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Run without MCP server subprocesses (use internal mock data)",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List supported LLM providers and exit",
    )

    args = parser.parse_args()

    if args.list_models:
        from agent.llm import list_providers
        print(list_providers())
        return

    async def _run():
        if args.standalone:
            report = await run_standalone(args.query)
        else:
            report = await run_agent(
                query=args.query,
                output_file=args.output,
                verbose=args.verbose,
            )

        if not args.output:
            print("\n" + "=" * 80)
            # Use safe printing for Windows console encoding
            try:
                print(report)
            except UnicodeEncodeError:
                sys.stdout.buffer.write(report.encode("utf-8") + b"\n")
            print("=" * 80)

        return report

    return asyncio.run(_run())


if __name__ == "__main__":
    main()
