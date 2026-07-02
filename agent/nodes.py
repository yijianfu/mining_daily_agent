"""LangGraph node functions for the Mining Daily Agent pipeline.

Each node represents one stage in the briefing generation pipeline:
plan → fetch_news → fetch_resources → fetch_prices → synthesize
"""

import json
import re
from datetime import datetime
from typing import Any, Optional

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger

from agent.state import AgentState
from agent.prompts import PLANNING_PROMPT, SYNTHESIS_PROMPT


# ── Node 1: Plan ─────────────────────────────────────────────────────────────

async def plan_node(
    state: AgentState,
    config: Optional[RunnableConfig] = None,
) -> dict[str, Any]:
    """Extract topic, commodities, and search queries from user input.

    Uses LLM to parse the natural language query into structured
    parameters for downstream data fetching nodes.

    Args:
        state: Current agent state.
        config: LangGraph runnable config (contains LLM model).

    Returns:
        State updates with topic, commodities, and phase.
    """
    logger.info("=== PLAN NODE: Extracting query parameters ===")
    user_query = state.get("user_query", "")

    # Quick fallback: keyword-based extraction if LLM unavailable
    try:
        model = _get_model(config)
        prompt = PLANNING_PROMPT.format(user_query=user_query)
        response = await model.ainvoke([HumanMessage(content=prompt)])

        # Extract JSON from response
        content = response.content if hasattr(response, "content") else str(response)
        plan = _extract_json(content)
        logger.info(f"LLM plan: {plan}")

        topic = plan.get("topic", user_query)
        commodities = plan.get("commodities", [])
        search_queries = plan.get("search_queries", [user_query])
        pdf_hint = plan.get("pdf_hint", "")

    except Exception as e:
        logger.warning(f"LLM planning failed ({e}), using fallback extraction")
        topic, commodities = _fallback_extract(user_query)
        search_queries = [topic] if topic else [user_query]
        pdf_hint = topic or ""

    return {
        "topic": topic,
        "commodities": commodities,
        "phase": "fetching",
        "messages": [
            AIMessage(content=json.dumps({
                "plan": {
                    "topic": topic,
                    "commodities": commodities,
                    "search_queries": search_queries,
                }
            }, ensure_ascii=False))
        ],
        "news_summary": "",  # Initialize empty
        "resource_data": "",
        "price_data": "",
        "risk_warnings": [],
        "report_markdown": "",
        "errors": [],
    }


# ── Node 2: Fetch News ───────────────────────────────────────────────────────

async def fetch_news_node(
    state: AgentState,
    config: Optional[RunnableConfig] = None,
    mcp_tools: Optional[list] = None,
) -> dict[str, Any]:
    """Search for mining news and fetch article bodies.

    Uses the mining-news MCP server to search RSS feeds for relevant
    articles, then fetches full text for the top results.

    Args:
        state: Current agent state.
        config: LangGraph runnable config.
        mcp_tools: Pre-loaded MCP tools (injected).

    Returns:
        State updates with news_summary.
    """
    logger.info("=== FETCH NEWS NODE ===")
    errors: list[str] = []

    if mcp_tools is None:
        logger.warning("No MCP tools available for news fetching")
        return {"news_summary": "**暂无相关数据** — MCP 工具不可用", "errors": errors}

    # Find the search and fetch tools
    search_tool = _find_tool(mcp_tools, "search_mining_news")
    fetch_tool = _find_tool(mcp_tools, "fetch_article")

    if search_tool is None:
        logger.warning("search_mining_news tool not found")
        return {
            "news_summary": "**暂无相关数据** — 新闻搜索工具不可用",
            "errors": ["News search tool not available"],
        }

    topic = state.get("topic", "") or state.get("user_query", "")
    commodities = state.get("commodities", [])

    # Search with topic as query
    news_parts: list[str] = []

    # Primary search by topic
    try:
        logger.info(f"Searching news for: {topic}")
        result_raw = await search_tool.ainvoke({
            "query": topic,
            "days": 7,
            "max_results": 5,
        })
        news_parts.append(f"### 搜索: \"{topic}\"\n\n{result_raw}")
        logger.info(f"News search result: {str(result_raw)[:200]}...")
    except Exception as e:
        err_msg = f"News search failed for '{topic}': {e}"
        logger.warning(err_msg)
        errors.append(err_msg)

    # Additional searches per commodity
    for commodity in commodities[:3]:
        query = f"{commodity} mining news"
        try:
            logger.info(f"Searching news for: {query}")
            result_raw = await search_tool.ainvoke({
                "query": query,
                "days": 7,
                "max_results": 3,
            })
            news_parts.append(f"### 搜索: \"{query}\"\n\n{result_raw}")
        except Exception as e:
            logger.warning(f"Commodity news search failed: {e}")

    # Try to fetch top article bodies
    try:
        search_data = _parse_json_safe(
            news_parts[0].replace(f"### 搜索: \"{topic}\"\n\n", "") if news_parts else "{}"
        )
        articles = search_data.get("articles", [])
        for article in articles[:3]:
            url = article.get("url", "")
            if url and fetch_tool:
                try:
                    logger.info(f"Fetching article: {url}")
                    body_raw = await fetch_tool.ainvoke({"url": url})
                    news_parts.append(f"### 文章全文: {url}\n\n{body_raw}")
                except Exception as e:
                    logger.warning(f"Article fetch failed for {url}: {e}")
    except Exception as e:
        logger.warning(f"Article fetching stage failed: {e}")

    news_summary = "\n\n".join(news_parts) if news_parts else "**暂无相关数据**"

    return {
        "news_summary": news_summary,
        "errors": state.get("errors", []) + errors,
    }


# ── Node 3: Fetch Resources ──────────────────────────────────────────────────

async def fetch_resources_node(
    state: AgentState,
    config: Optional[RunnableConfig] = None,
    mcp_tools: Optional[list] = None,
) -> dict[str, Any]:
    """Extract NI 43-101 mineral resource data for the topic.

    Uses the mineral-pdf MCP server to parse NI 43-101 reports.
    Constructs a PDF URL based on the topic or uses known URLs.

    Args:
        state: Current agent state.
        config: LangGraph runnable config.
        mcp_tools: Pre-loaded MCP tools (injected).

    Returns:
        State updates with resource_data.
    """
    logger.info("=== FETCH RESOURCES NODE ===")
    errors: list[str] = []

    if mcp_tools is None:
        return {
            "resource_data": "**暂无相关数据** — MCP 工具不可用",
            "errors": state.get("errors", []) + ["Resource extraction tools not available"],
        }

    extract_tool = _find_tool(mcp_tools, "extract_resources")
    if extract_tool is None:
        return {
            "resource_data": "**暂无相关数据** — 资源提取工具不可用",
            "errors": state.get("errors", []) + ["extract_resources tool not found"],
        }

    topic = state.get("topic", "") or ""
    topic_lower = topic.lower()

    # Map topic to known NI 43-101 PDF URLs
    pdf_urls = _get_known_pdf_urls(topic_lower)

    if not pdf_urls:
        # Construct a plausible URL that will trigger mock data
        safe_name = re.sub(r"[^a-z0-9]+", "-", topic_lower).strip("-")
        pdf_urls = [
            f"https://www.sedar.com/DisplayProfile.do?lang=EN&issuerType=03&issuerNo={safe_name}",
        ]

    results: list[str] = []
    for url in pdf_urls:
        try:
            logger.info(f"Extracting resources from: {url}")
            result_raw = await extract_tool.ainvoke({"pdf_url": url})
            results.append(f"### NI 43-101 报告: {url}\n\n{result_raw}")
        except Exception as e:
            err_msg = f"Resource extraction failed for {url}: {e}"
            logger.warning(err_msg)
            errors.append(err_msg)

    resource_data = "\n\n".join(results) if results else "**暂无相关数据**"

    return {
        "resource_data": resource_data,
        "errors": state.get("errors", []) + errors,
    }


# ── Node 4: Fetch Prices ─────────────────────────────────────────────────────

async def fetch_prices_node(
    state: AgentState,
    config: Optional[RunnableConfig] = None,
    mcp_tools: Optional[list] = None,
) -> dict[str, Any]:
    """Fetch commodity prices and trends for relevant commodities.

    Uses the lme-price MCP server to get current prices and N-day trends
    for each commodity identified in the planning phase.

    Args:
        state: Current agent state.
        config: LangGraph runnable config.
        mcp_tools: Pre-loaded MCP tools (injected).

    Returns:
        State updates with price_data.
    """
    logger.info("=== FETCH PRICES NODE ===")
    errors: list[str] = []

    if mcp_tools is None:
        return {
            "price_data": "**暂无相关数据** — MCP 工具不可用",
            "errors": state.get("errors", []) + ["Price tools not available"],
        }

    price_tool = _find_tool(mcp_tools, "get_price")
    trend_tool = _find_tool(mcp_tools, "get_trend")

    if price_tool is None and trend_tool is None:
        return {
            "price_data": "**暂无相关数据** — 价格工具不可用",
            "errors": state.get("errors", []) + ["No price tools available"],
        }

    commodities = state.get("commodities", [])
    if not commodities:
        # Default to common mining commodities
        commodities = ["copper", "gold", "lithium", "iron ore"]

    logger.info(f"Fetching prices for: {commodities}")

    parts: list[str] = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    for commodity in commodities:
        try:
            # Get current price
            if price_tool:
                price_raw = await price_tool.ainvoke({
                    "commodity": commodity,
                    "date": today_str,
                })
                parts.append(f"### {commodity.title()} 当前价格\n\n{price_raw}")

            # Get 30-day trend
            if trend_tool:
                trend_raw = await trend_tool.ainvoke({
                    "commodity": commodity,
                    "days": 30,
                })
                parts.append(f"### {commodity.title()} 30日走势\n\n{trend_raw}")

        except Exception as e:
            err_msg = f"Price fetch failed for {commodity}: {e}"
            logger.warning(err_msg)
            errors.append(err_msg)

    price_data = "\n\n".join(parts) if parts else "**暂无相关数据**"

    return {
        "price_data": price_data,
        "errors": state.get("errors", []) + errors,
    }


# ── Node 5: Synthesize ───────────────────────────────────────────────────────

async def synthesize_node(
    state: AgentState,
    config: Optional[RunnableConfig] = None,
) -> dict[str, Any]:
    """Synthesize all collected data into a final markdown briefing report.

    Uses LLM to compose a professional report from news, resource,
    and price data collected by previous nodes.

    Args:
        state: Current agent state with all collected data.
        config: LangGraph runnable config.

    Returns:
        State updates with report_markdown and risk_warnings.
    """
    logger.info("=== SYNTHESIZE NODE: Generating briefing report ===")

    user_query = state.get("user_query", "")
    topic = state.get("topic", "")
    commodities = state.get("commodities", [])
    news_summary = state.get("news_summary", "暂无数据")
    resource_data = state.get("resource_data", "暂无数据")
    price_data = state.get("price_data", "暂无数据")
    errors = state.get("errors", [])

    errors_text = "\n".join(f"- {e}" for e in errors) if errors else "无"

    try:
        model = _get_model(config)
        prompt = SYNTHESIS_PROMPT.format(
            user_query=user_query,
            topic=topic,
            commodities=", ".join(commodities) if commodities else "未识别",
            news_summary=news_summary[:8000],  # Truncate if too long
            resource_data=resource_data[:5000],
            price_data=price_data[:5000],
            errors=errors_text,
        )

        response = await model.ainvoke([HumanMessage(content=prompt)])
        report = response.content if hasattr(response, "content") else str(response)

    except Exception as e:
        logger.error(f"LLM synthesis failed: {e}")
        # Fallback: build a simple report from raw data
        report = _build_fallback_report(state)

    # Extract risk warnings from the report
    risk_warnings = _extract_risk_section(report)

    logger.info(f"Report generated: {len(report)} characters")

    return {
        "report_markdown": report,
        "risk_warnings": risk_warnings,
        "phase": "done",
        "messages": [
            AIMessage(content=f"Briefing report generated ({len(report)} chars)")
        ],
    }


# ── Helper Functions ─────────────────────────────────────────────────────────


def _get_model(config: Optional[RunnableConfig] = None):
    """Get the LLM model instance based on configuration.

    Tries Anthropic first, falls back to OpenAI.
    """
    from agent.config import agent_config

    provider = agent_config.model_provider
    model_name = agent_config.model_name

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
            logger.info(f"Using Anthropic model: {model_name}")
            return ChatAnthropic(
                model=model_name,
                temperature=0.3,
                max_tokens=4096,
                timeout=120,
            )
        except Exception as e:
            logger.warning(f"Anthropic init failed ({e}), trying OpenAI")

    try:
        from langchain_openai import ChatOpenAI
        logger.info(f"Using OpenAI model: {model_name}")
        return ChatOpenAI(
            model=model_name or "gpt-4o",
            temperature=0.3,
            max_tokens=4096,
            timeout=120,
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to initialize any LLM model: {e}. "
            f"Set ANTHROPIC_API_KEY or OPENAI_API_KEY."
        )


def _find_tool(tools: list, name_contains: str) -> Optional[Any]:
    """Find a tool by partial name match.

    Args:
        tools: List of MCP/LC tools.
        name_contains: Substring to search for in tool names.

    Returns:
        The matching tool, or None.
    """
    for tool in tools:
        tool_name = getattr(tool, "name", "")
        if name_contains in tool_name:
            return tool
    return None


def _extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from text that may contain markdown fences.

    Args:
        text: Text potentially containing a JSON code block.

    Returns:
        Parsed dict.

    Raises:
        ValueError: If no valid JSON is found.
    """
    # Remove markdown fence if present
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if json_match:
        text = json_match.group(1)

    # Find first { and matching }
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response")

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])

    raise ValueError("Unclosed JSON object")


def _fallback_extract(query: str) -> tuple[str, list[str]]:
    """Fallback topic/commodity extraction without LLM.

    Uses keyword matching for common mining topics.

    Args:
        query: The user query string.

    Returns:
        Tuple of (topic, commodities list).
    """
    query_lower = query.lower()

    # Topic detection
    topic_keywords = [
        "pilbara", "greenbushes", "wodgina", "nevada", "rincon",
        "goulamina", "james bay", "thacker pass", "sal de vida",
        "arcadia", "manono", "bikita",
    ]
    topic = query  # Default: whole query
    for kw in topic_keywords:
        if kw in query_lower:
            topic = kw.title()
            break

    # Commodity detection
    commodity_map = {
        "lithium": "lithium",
        "锂": "lithium",
        "gold": "gold",
        "金": "gold",
        "copper": "copper",
        "铜": "copper",
        "nickel": "nickel",
        "镍": "nickel",
        "silver": "silver",
        "银": "silver",
        "iron": "iron ore",
        "铁": "iron ore",
        "zinc": "zinc",
        "锌": "zinc",
        "uranium": "uranium",
        "铀": "uranium",
        "cobalt": "cobalt",
        "钴": "cobalt",
        "铝": "aluminum",
        "aluminum": "aluminum",
    }

    commodities = []
    for kw, commodity in commodity_map.items():
        if kw in query_lower and commodity not in commodities:
            commodities.append(commodity)

    if not commodities:
        commodities = ["lithium", "gold", "copper"]

    return topic, commodities


def _get_known_pdf_urls(topic_lower: str) -> list[str]:
    """Map topic to known NI 43-101 PDF URLs.

    Args:
        topic_lower: Lowercase topic string.

    Returns:
        List of PDF URLs, or empty list.
    """
    mapping = {
        "pilgangoora": [
            "https://pilbaraminerals.com.au/site/assets/files/1234/"
            "pilgangoora-ni43-101-technical-report-2025.pdf",
        ],
        "pilbara": [
            "https://pilbaraminerals.com.au/site/assets/files/1234/"
            "pilgangoora-ni43-101-technical-report-2025.pdf",
        ],
        "greenbushes": [
            "https://www.talisonlithium.com/reports/"
            "greenbushes-ni43-101-technical-report.pdf",
        ],
        "wodgina": [
            "https://www.mineralresources.com.au/reports/"
            "wodgina-ni43-101-2025.pdf",
        ],
    }

    for key, urls in mapping.items():
        if key in topic_lower:
            return urls

    return []


def _parse_json_safe(text: str) -> dict[str, Any]:
    """Safely parse JSON, returning empty dict on failure."""
    try:
        return json.loads(text) if isinstance(text, str) else text
    except (json.JSONDecodeError, TypeError):
        try:
            return _extract_json(str(text))
        except (ValueError, json.JSONDecodeError):
            return {}


def _build_fallback_report(state: AgentState) -> str:
    """Build a basic report from raw data when LLM synthesis fails.

    Args:
        state: Agent state with collected data.

    Returns:
        Markdown report string.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    topic = state.get("topic", "Mining")
    commodities = state.get("commodities", [])

    report = f"""# {topic} 矿业日报

**日期**: {today}
**生成方式**: 自动回退模式 (LLM 不可用)

---

## 今日新闻摘要

{state.get("news_summary", "**暂无相关数据**")}

---

## 矿产资源储量

{state.get("resource_data", "**暂无相关数据**")}

---

## 金属价格与走势

{state.get("price_data", "**暂无相关数据**")}

---

## 风险提示

- 本报告由自动回退模式生成，未经 LLM 整合分析
- 数据可能包含模拟数据 (mock data)，请核实后使用

---

## 引用来源

- 新闻数据: Mining.com, Kitco, Mining Weekly RSS feeds
- 资源数据: SEDAR / 各公司官网 NI 43-101 报告
- 价格数据: Mock provider (模拟数据)

**免责声明**: 本报告部分数据为模拟数据，不构成投资建议。
"""
    return report


def _extract_risk_section(report: str) -> list[str]:
    """Extract risk warnings from the report.

    Args:
        report: The full markdown report.

    Returns:
        List of risk warning strings.
    """
    risks: list[str] = []

    # Find the risk section
    risk_match = re.search(
        r"(?:###?\s*风险提示|###?\s*Risk\s*Analysis)(.*?)(?:###|$)",
        report,
        re.DOTALL | re.IGNORECASE,
    )

    if risk_match:
        section = risk_match.group(1)
        # Extract list items
        for line in section.strip().split("\n"):
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                risk = line.lstrip("-* ").strip()
                if risk and len(risk) > 5:
                    risks.append(risk)

    return risks
