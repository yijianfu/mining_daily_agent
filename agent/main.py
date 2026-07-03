"""Mining Daily Agent — CLI entry point.

Usage:
    # Interactive mode (default):
    python -m agent.main

    # One-shot mode:
    python -m agent.main "Generate a briefing on Pilbara lithium"

    # Standalone (no MCP servers, no API key):
    python -m agent.main --standalone

    # Save to file:
    python -m agent.main "Gold mining in Nevada" -o report.md
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

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

BANNER = r"""
+------------------------------------------------------+
|        Mining Daily Agent                            |
|                                                      |
|  Ask me anything about mining — I'll search news,    |
|  extract NI 43-101 resource data, track prices,      |
|  and synthesize a professional daily briefing.       |
|                                                      |
|  Commands: /help  /models  /quit  /save <path>       |
+------------------------------------------------------+
"""

HELP_TEXT = """
Commands:
  /help          Show this help
  /models        Show LLM provider status
  /quit          Exit
  /save <path>   Save last report to file

Example queries:
  Pilbara lithium daily briefing
  Gold mining in Nevada outlook
  Copper price trend and news
  Iron ore supply chain analysis
  NI 43-101 resource data for Pilgangoora
"""


def _safe_print(text: str) -> None:
    """Print to stdout, falling back to raw bytes on Windows encoding errors."""
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8") + b"\n")


# ── Pipeline runner (shared by one-shot and interactive modes) ───────────────

async def run_agent(
    query: str,
    output_file: Optional[str] = None,
    verbose: bool = False,
    mcp_client=None,
    mcp_tools=None,
    graph=None,
) -> str:
    """Run the Mining Daily Agent pipeline once.

    When mcp_client/tools/graph are passed in, they are reused
    across calls (used by interactive mode).  Otherwise created fresh.
    """
    setup_logging("mining-agent", use_stderr=verbose)
    logger.info(f"Query: {query}")

    own_client = False

    try:
        if mcp_tools is None:
            logger.info("Connecting to MCP servers...")
            try:
                mcp_client = await create_mcp_client()
                mcp_tools = await mcp_client.get_tools()
                own_client = True
                logger.info(f"Connected: {len(mcp_tools)} tools")
            except Exception as e:
                logger.warning(f"MCP connection failed ({e}), running degraded")
                mcp_tools = None

        if graph is None:
            graph = build_graph(mcp_tools=mcp_tools)

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

        logger.info("Running pipeline...")
        tid = f"session-{datetime.now().timestamp()}"
        final_state = await graph.ainvoke(initial_state, {"configurable": {"thread_id": tid}})

        report = final_state.get("report_markdown", "")
        if not report:
            report = "**Error**: Failed to generate briefing report."

        logger.info(f"Report: {len(report)} chars")

        if output_file:
            Path(output_file).write_text(report, encoding="utf-8")
            logger.info(f"Saved to: {output_file}")

        return report

    finally:
        if own_client and mcp_client:
            try:
                await mcp_client.close()
            except Exception:
                pass


# ── Standalone runner (no MCP subprocesses) ──────────────────────────────────

async def run_standalone(query: str) -> str:
    """Run without MCP servers, using built-in mock data internally."""
    from servers.mining_news_mcp.tools import search_mining_news
    from servers.mineral_pdf_mcp.tools import extract_resources
    from servers.lme_price_mcp.tools import get_price, get_trend
    from agent.nodes import _fallback_extract, _build_fallback_report
    from agent.prompts import SYNTHESIS_PROMPT

    topic, commodities = _fallback_extract(query)

    # News
    news_parts = []
    try:
        news_parts.append(f"### {topic}\n\n{search_mining_news(query=topic, days=7, max_results=5)}")
    except Exception:
        pass
    for c in commodities:
        try:
            news_parts.append(f"### {c}\n\n{search_mining_news(query=f'{c} mining', days=7, max_results=3)}")
        except Exception:
            pass
    news_summary = "\n\n".join(news_parts) if news_parts else "No data"

    # Resources
    try:
        slug = topic.lower().replace(" ", "-")
        resource_data = extract_resources(pdf_url=f"https://sedar.com/ni43-101/{slug}.pdf")
    except Exception:
        resource_data = "No data"

    # Prices
    price_parts = []
    for c in commodities:
        try:
            price_parts.append(f"### {c}\n\n{get_price(commodity=c)}")
            price_parts.append(f"### {c}\n\n{get_trend(commodity=c, days=30)}")
        except Exception:
            pass
    price_data = "\n\n".join(price_parts) if price_parts else "No data"

    # Synthesize
    try:
        from agent.llm import get_model
        model = get_model()
        prompt = SYNTHESIS_PROMPT.format(
            user_query=query, topic=topic,
            commodities=", ".join(commodities),
            news_summary=news_summary[:8000],
            resource_data=resource_data[:5000],
            price_data=price_data[:5000],
            errors="None",
        )
        response = await model.ainvoke([HumanMessage(content=prompt)])
        return response.content if hasattr(response, "content") else str(response)
    except Exception:
        state: AgentState = {
            "messages": [], "user_query": query, "topic": topic,
            "commodities": commodities, "news_summary": news_summary,
            "resource_data": resource_data, "price_data": price_data,
            "risk_warnings": [], "report_markdown": "",
            "phase": "synthesizing", "errors": [],
        }
        return _build_fallback_report(state)


# ── Interactive REPL ─────────────────────────────────────────────────────────

async def run_interactive(standalone: bool = False) -> None:
    """Interactive dialogue loop. Keeps MCP connections alive across queries."""
    _safe_print(BANNER)

    mcp_client = None
    mcp_tools = None
    graph = None
    last_report = ""

    if not standalone:
        try:
            print("Connecting to MCP servers...")
            mcp_client = await create_mcp_client()
            mcp_tools = await mcp_client.get_tools()
            print(f"Connected: {len(mcp_tools)} tools\n")
        except Exception as e:
            print(f"MCP connection failed ({e}), running degraded\n")

    try:
        graph = build_graph(mcp_tools=mcp_tools)

        while True:
            try:
                query = input("Mining> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not query:
                continue

            # Commands
            if query.startswith("/"):
                cmd, _, arg = query[1:].partition(" ")
                cmd = cmd.lower()

                if cmd in ("quit", "exit"):
                    print("Goodbye!")
                    break
                elif cmd == "help":
                    print(HELP_TEXT)
                elif cmd == "models":
                    from agent.llm import list_providers
                    print(list_providers())
                elif cmd == "save":
                    path = arg.strip() or f"report-{datetime.now():%Y%m%d-%H%M%S}.md"
                    Path(path).write_text(last_report, encoding="utf-8")
                    print(f"Report saved to: {path}")
                else:
                    print(f"Unknown: /{cmd}  (type /help)")
                continue

            # Run the query
            print(f"\nGenerating briefing: {query}\n")
            try:
                if standalone:
                    report = await run_standalone(query)
                else:
                    report = await run_agent(
                        query=query, verbose=False,
                        mcp_client=mcp_client, mcp_tools=mcp_tools, graph=graph,
                    )

                last_report = report
                print("-" * 60)
                _safe_print(report)
                print("-" * 60)
                print()

            except Exception as e:
                logger.error(f"Error generating report: {e}")
                print(f"\nError: {e}\n")

    finally:
        if mcp_client:
            try:
                await mcp_client.close()
            except Exception:
                pass


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Mining Daily Briefing Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent.main                    # interactive dialogue mode
  python -m agent.main "Copper market"    # one-shot mode
  python -m agent.main --standalone       # offline mode (no API key needed)
  python -m agent.main -o report.md       # save output to file
        """,
    )
    parser.add_argument(
        "query", nargs="?", default=None,
        help="Briefing request (no argument = interactive mode)",
    )
    parser.add_argument("-o", "--output", default=None, help="Output file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logs")
    parser.add_argument("--standalone", action="store_true", help="Offline mode")
    parser.add_argument("--list-models", action="store_true", help="List LLM providers")

    args = parser.parse_args()

    if args.list_models:
        from agent.llm import list_providers
        print(list_providers())
        return

    async def _run():
        if args.query:
            # One-shot
            if args.standalone:
                report = await run_standalone(args.query)
            else:
                report = await run_agent(
                    query=args.query, output_file=args.output, verbose=args.verbose,
                )
            if not args.output:
                print("\n" + "=" * 80)
                _safe_print(report)
                print("=" * 80)
        else:
            # Interactive
            await run_interactive(standalone=args.standalone)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
