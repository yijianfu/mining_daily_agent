"""Abstract base class for commodity price data providers."""

from abc import ABC, abstractmethod
from typing import Optional

from servers.lme_price_mcp.models import CommodityPrice, PricePoint


class PriceProvider(ABC):
    """Abstract interface for commodity price data sources.

    Implementations provide current and historical commodity prices
    from various data sources (LME, iTick, mock data, etc.).
    """

    @abstractmethod
    async def get_current_price(
        self, commodity: str, date: Optional[str] = None
    ) -> CommodityPrice:
        """Get the current (or historical) price for a commodity.

        Args:
            commodity: Normalized commodity name.
            date: Optional specific date (YYYY-MM-DD). None = latest.

        Returns:
            CommodityPrice with price, currency, unit, and metadata.
        """
        ...

    @abstractmethod
    async def get_history(
        self, commodity: str, days: int
    ) -> list[PricePoint]:
        """Get price history for a commodity.

        Args:
            commodity: Normalized commodity name.
            days: Number of calendar days to look back.

        Returns:
            List of PricePoint objects, sorted by date ascending.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for attribution."""
        ...

    async def close(self) -> None:
        """Optional cleanup hook. Called on server shutdown."""
        pass
