"""Tool implementations for the LME Price MCP server.

Provides:
- get_price: Current or historical commodity price
- get_trend: Price trend over N days with summary statistics
"""

import json
import statistics
import sys
import os
from datetime import datetime
from typing import Optional

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger

from servers.shared.cache_base import TTLCache
from servers.shared.async_utils import run_async
from servers.lme_price_mcp.config import lme_config
from servers.lme_price_mcp.models import (
    CommodityPrice,
    PricePoint,
    PriceTrend,
    TrendSummary,
)
from servers.lme_price_mcp.providers.base import PriceProvider
from servers.lme_price_mcp.providers.mock_provider import MockProvider

# In-memory caches
_price_cache = TTLCache[str, str](ttl_seconds=lme_config.cache_ttl_current, max_size=500)
_trend_cache = TTLCache[str, str](ttl_seconds=lme_config.cache_ttl_history, max_size=200)

# Provider instance (lazy init)
_provider: Optional[PriceProvider] = None


def _get_provider() -> PriceProvider:
    """Get or create the price data provider."""
    global _provider
    if _provider is None:
        provider_name = lme_config.provider
        if provider_name == "itick" and lme_config.itick_api_key:
            logger.info("Using iTick price provider")
            logger.warning("iTick provider not yet implemented, falling back to mock")
            _provider = MockProvider()
        else:
            logger.info("Using mock price provider")
            _provider = MockProvider()
    return _provider


def _cache_key(*parts: str) -> str:
    """Build a cache key from parts."""
    return ":".join(parts)


def get_price(
    commodity: str,
    date: Optional[str] = None,
) -> str:
    """Get the current or historical price for a commodity.

    Supported commodities: copper, lithium, nickel, gold, silver,
    iron ore, zinc, aluminum, uranium, cobalt, tin, lead.

    Args:
        commodity: Commodity name (case-insensitive, e.g. "copper", "Lithium").
        date: Optional date in YYYY-MM-DD format. Defaults to today.

    Returns:
        JSON string with CommodityPrice data.
    """
    import asyncio

    date_str = date or datetime.now().strftime("%Y-%m-%d")
    cache_key = _cache_key("price", commodity.lower(), date_str)

    # Check cache
    cached = _price_cache.get(cache_key)
    if cached:
        logger.debug(f"Cache hit: {cache_key}")
        return cached

    logger.info(f"Getting price for {commodity} on {date_str}")

    try:
        provider = _get_provider()
        result = run_async(provider.get_current_price(commodity, date_str))
        json_str = result.model_dump_json(indent=2)
        _price_cache.set(cache_key, json_str)
        return json_str
    except Exception as e:
        logger.error(f"Failed to get price for {commodity}: {e}")
        return json.dumps({
            "error": True,
            "error_code": "PRICE_FETCH_ERROR",
            "message": str(e),
            "commodity": commodity,
            "date": date_str,
        }, ensure_ascii=False)


def get_trend(
    commodity: str,
    days: int = 30,
) -> str:
    """Get price trend for a commodity over a specified number of days.

    Includes price series and statistical summary (change %, min/max,
    volatility, trend direction).

    Args:
        commodity: Commodity name (case-insensitive).
        days: Number of calendar days to look back. Defaults to 30.

    Returns:
        JSON string with PriceTrend data (series + summary statistics).
    """
    import asyncio

    cache_key = _cache_key("trend", commodity.lower(), str(days))

    # Check cache
    cached = _trend_cache.get(cache_key)
    if cached:
        logger.debug(f"Cache hit: {cache_key}")
        return cached

    logger.info(f"Getting {days}-day trend for {commodity}")

    try:
        provider = _get_provider()
        series = run_async(provider.get_history(commodity, days))

        if not series:
            return json.dumps({
                "error": True,
                "error_code": "NO_DATA",
                "message": f"No price data available for {commodity}",
            })

        prices = [p.price for p in series]
        start_price = prices[0]
        end_price = prices[-1]
        change_pct = round((end_price - start_price) / start_price * 100, 2)
        avg_price = round(statistics.mean(prices), 2)
        min_price = min(prices)
        max_price = max(prices)

        # Trend direction
        if change_pct > 1:
            direction = "up"
        elif change_pct < -1:
            direction = "down"
        else:
            direction = "flat"

        # Volatility (coefficient of variation)
        if avg_price > 0 and len(prices) > 1:
            std_dev = statistics.stdev(prices)
            volatility = round(std_dev / avg_price * 100, 2)
        else:
            volatility = 0.0

        # Get unit info
        _, currency, unit = provider._get_baseline(commodity)  # type: ignore[union-attr]

        trend = PriceTrend(
            commodity=commodity,
            days=days,
            currency=currency,
            unit=unit,
            series=series,
            summary=TrendSummary(
                start_price=start_price,
                end_price=end_price,
                change_percent=change_pct,
                min_price=round(min_price, 2),
                max_price=round(max_price, 2),
                avg_price=avg_price,
                trend_direction=direction,
                volatility_percent=volatility,
            ),
            source=provider.provider_name,
        )

        json_str = trend.model_dump_json(indent=2)
        _trend_cache.set(cache_key, json_str)
        return json_str

    except Exception as e:
        logger.error(f"Failed to get trend for {commodity}: {e}")
        return json.dumps({
            "error": True,
            "error_code": "TREND_FETCH_ERROR",
            "message": str(e),
            "commodity": commodity,
            "days": days,
        }, ensure_ascii=False)
