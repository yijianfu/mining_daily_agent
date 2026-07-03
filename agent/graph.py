"""LangGraph StateGraph definition for the Mining Daily Agent.

Builds the 5-node pipeline: plan → fetch_news → fetch_resources →
fetch_prices → synthesize.
"""

from typing import Any, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

from agent.state import AgentState
from agent.nodes import (
    plan_node,
    fetch_news_node,
    fetch_resources_node,
    fetch_prices_node,
    synthesize_node,
)


def build_graph(
    mcp_tools: Optional[list[Any]] = None,
) -> StateGraph:
    """Build and compile the Mining Daily Agent graph.

    Pipeline:
        START → plan → fetch_news → fetch_resources → fetch_prices → synthesize → END

    Each fetch node receives MCP tools via closure binding.

    Args:
        mcp_tools: Pre-loaded MCP tools from MultiServerMCPClient.
                   If None, nodes will operate in degraded mode.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    builder = StateGraph(AgentState)

    # Wrap fetch nodes with MCP tools via closure
    async def fetch_news_wrapper(
        state: AgentState,
        config=None,
    ) -> dict[str, Any]:
        return await fetch_news_node(state, config, mcp_tools)

    async def fetch_resources_wrapper(
        state: AgentState,
        config=None,
    ) -> dict[str, Any]:
        return await fetch_resources_node(state, config, mcp_tools)

    async def fetch_prices_wrapper(
        state: AgentState,
        config=None,
    ) -> dict[str, Any]:
        return await fetch_prices_node(state, config, mcp_tools)

    # Register nodes
    builder.add_node("plan", plan_node)
    builder.add_node("fetch_news", fetch_news_wrapper)
    builder.add_node("fetch_resources", fetch_resources_wrapper)
    builder.add_node("fetch_prices", fetch_prices_wrapper)
    builder.add_node("synthesize", synthesize_node)

    # Define edges — linear pipeline
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "fetch_news")
    builder.add_edge("fetch_news", "fetch_resources")
    builder.add_edge("fetch_resources", "fetch_prices")
    builder.add_edge("fetch_prices", "synthesize")
    builder.add_edge("synthesize", END)

    # Compile with memory checkpointer for conversation continuity
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)

    logger.info(f"Graph compiled: {len(graph.nodes)} nodes")
    return graph
