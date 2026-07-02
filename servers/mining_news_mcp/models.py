"""Data models for the Mining News MCP server."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    """A single news article from search results."""

    title: str = Field(description="Article headline")
    url: str = Field(description="Article URL")
    source: str = Field(description="News source/publication name")
    published_date: Optional[str] = Field(
        default=None, description="Publication date in ISO format"
    )
    snippet: Optional[str] = Field(
        default=None, description="Short excerpt or summary"
    )


class SearchResult(BaseModel):
    """Result of a news search query."""

    query: str = Field(description="Original search query")
    searched_days: int = Field(description="Days spanned by the search")
    total_results: int = Field(description="Number of articles found")
    articles: list[NewsArticle] = Field(
        default_factory=list, description="Matching articles"
    )
    sources_searched: list[str] = Field(
        default_factory=list,
        description="List of sources that were queried",
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="When these results were generated",
    )


class ArticleBody(BaseModel):
    """Full text of a fetched news article."""

    url: str = Field(description="Article URL")
    title: str = Field(description="Article headline")
    publisher: Optional[str] = Field(default=None, description="Publisher name")
    author: Optional[str] = Field(default=None, description="Article author")
    published_date: Optional[str] = Field(
        default=None, description="Publication date"
    )
    text: str = Field(description="Full article body text")
    text_length: int = Field(description="Character count of article text")
    fetch_method: str = Field(
        default="trafilatura",
        description="Method used to extract article body",
    )
