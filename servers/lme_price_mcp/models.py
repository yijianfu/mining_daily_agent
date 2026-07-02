"""Data models for the LME Price MCP server."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CommodityPrice(BaseModel):
    """Current or historical price for a single commodity."""

    commodity: str = Field(description="Normalized commodity name")
    price: float = Field(description="Price value")
    currency: str = Field(description="Currency code, e.g. USD")
    unit: str = Field(
        description="Price unit, e.g. 'per metric tonne', 'per oz', 'per lb'"
    )
    date: str = Field(description="Date of the price in YYYY-MM-DD format")
    source: str = Field(description="Data source identifier")
    is_delayed: bool = Field(
        default=False,
        description="Whether the price is delayed (non-real-time)",
    )


class PricePoint(BaseModel):
    """A single data point in a price time series."""

    date: str = Field(description="Date in YYYY-MM-DD format")
    price: float = Field(description="Price on that date")


class TrendSummary(BaseModel):
    """Statistical summary of a price trend series."""

    start_price: float = Field(description="Price at the start of the period")
    end_price: float = Field(description="Price at the end of the period")
    change_percent: float = Field(description="Percentage change over the period")
    min_price: float = Field(description="Minimum price in the period")
    max_price: float = Field(description="Maximum price in the period")
    avg_price: float = Field(description="Average price over the period")
    trend_direction: str = Field(
        description="Trend direction: 'up', 'down', or 'flat'"
    )
    volatility_percent: float = Field(
        description="Price volatility as percentage (std/mean)"
    )


class PriceTrend(BaseModel):
    """Complete price trend data for a commodity."""

    commodity: str
    days: int
    currency: str
    unit: str
    series: list[PricePoint]
    summary: TrendSummary
    source: str
    generated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="When this trend data was generated",
    )
