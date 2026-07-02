"""Agent state definition for the Mining Daily briefing graph.

The state object flows through all nodes in the LangGraph pipeline,
accumulating data at each stage before final synthesis.
"""

from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State container for the Mining Daily Agent graph.

    Attributes:
        messages: Conversation history (accumulated via add_messages).
        user_query: The original user briefing request.
        topic: Extracted topic/region/mine name.
        commodities: List of relevant commodities identified.
        news_summary: Compiled news search + article fetch results.
        resource_data: NI 43-101 extraction results.
        price_data: LME price + trend results for each commodity.
        risk_warnings: Generated risk analysis bullet points.
        report_markdown: Final synthesized markdown report.
        phase: Current pipeline phase.
        errors: Accumulated non-fatal errors for graceful degradation.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    topic: Optional[str]
    commodities: list[str]
    news_summary: str
    resource_data: str
    price_data: str
    risk_warnings: list[str]
    report_markdown: str
    phase: str
    errors: list[str]
