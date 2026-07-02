"""Mock price provider with realistic commodity price baselines.

Generates plausible price data using historical baselines plus a small
random walk. No API key required — used as the default fallback.
"""

import random
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from servers.lme_price_mcp.models import CommodityPrice, PricePoint
from servers.lme_price_mcp.providers.base import PriceProvider

# Realistic baseline prices for common mining commodities (July 2026 reference)
# Format: (price_per_unit, currency, unit)
BASELINE_PRICES: dict[str, tuple[float, str, str]] = {
    "copper": (9850.0, "USD", "per metric tonne"),
    "lithium": (14500.0, "USD", "per metric tonne (Li2CO3)"),
    "nickel": (16800.0, "USD", "per metric tonne"),
    "gold": (2680.0, "USD", "per troy ounce"),
    "silver": (32.5, "USD", "per troy ounce"),
    "iron ore": (112.0, "USD", "per dry metric tonne"),
    "zinc": (2950.0, "USD", "per metric tonne"),
    "aluminum": (2650.0, "USD", "per metric tonne"),
    "uranium": (85.0, "USD", "per pound U3O8"),
    "cobalt": (28500.0, "USD", "per metric tonne"),
    "tin": (32500.0, "USD", "per metric tonne"),
    "lead": (2180.0, "USD", "per metric tonne"),
}

# Daily volatility per commodity (standard deviation of daily returns)
VOLATILITY: dict[str, float] = {
    "copper": 0.012,
    "lithium": 0.025,
    "nickel": 0.018,
    "gold": 0.008,
    "silver": 0.015,
    "iron ore": 0.014,
    "zinc": 0.016,
    "aluminum": 0.011,
    "uranium": 0.020,
    "cobalt": 0.022,
    "tin": 0.013,
    "lead": 0.014,
}


class MockProvider(PriceProvider):
    """Generates realistic synthetic commodity price data.

    Uses a deterministic seed per commodity+date for reproducibility,
    while still producing plausible random-walk price movements.
    """

    def __init__(self, seed: int = 42) -> None:
        """Initialize the mock provider.

        Args:
            seed: Base random seed for reproducibility.
        """
        self.seed = seed

    @property
    def provider_name(self) -> str:
        return "mock"

    def _seed_for(self, commodity: str, date_str: str) -> int:
        """Generate a deterministic seed from commodity + date."""
        key = f"{commodity}:{date_str}:{self.seed}"
        return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    def _get_baseline(self, commodity: str) -> tuple[float, str, str]:
        """Get baseline price info, with fuzzy matching."""
        norm = commodity.lower().strip()

        # Direct match
        if norm in BASELINE_PRICES:
            return BASELINE_PRICES[norm]

        # Substring match
        for key, val in BASELINE_PRICES.items():
            if key in norm or norm in key:
                return val

        # Default fallback
        logger.warning(
            f"Unknown commodity '{commodity}', using default baseline"
        )
        return (1000.0, "USD", "per metric tonne")

    async def get_current_price(
        self, commodity: str, date: Optional[str] = None
    ) -> CommodityPrice:
        """Get a simulated current price."""
        date_str = date or datetime.now().strftime("%Y-%m-%d")
        baseline, currency, unit = self._get_baseline(commodity)
        vol = VOLATILITY.get(commodity.lower(), 0.015)

        rng = random.Random(self._seed_for(commodity, date_str))
        # Random daily return: ~ N(0, vol)
        daily_return = rng.gauss(0, vol)
        price = round(baseline * (1 + daily_return), 2)

        logger.info(
            f"Mock price for {commodity} on {date_str}: "
            f"{price} {currency} {unit}"
        )

        return CommodityPrice(
            commodity=commodity,
            price=price,
            currency=currency,
            unit=unit,
            date=date_str,
            source="mock",
            is_delayed=True,
        )

    async def get_history(
        self, commodity: str, days: int
    ) -> list[PricePoint]:
        """Generate a simulated price history using random walk."""
        if days < 2:
            days = 2

        baseline, _, _ = self._get_baseline(commodity)
        vol = VOLATILITY.get(commodity.lower(), 0.015)

        points: list[PricePoint] = []
        current_price = baseline
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        for i in range(days + 1):
            date = start_date + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")

            if i > 0:
                rng = random.Random(self._seed_for(commodity, date_str))
                daily_return = rng.gauss(0, vol)
                current_price *= (1 + daily_return)

            points.append(PricePoint(
                date=date_str,
                price=round(current_price, 2),
            ))

        logger.info(
            f"Mock history for {commodity}: {len(points)} points over {days} days"
        )
        return points
