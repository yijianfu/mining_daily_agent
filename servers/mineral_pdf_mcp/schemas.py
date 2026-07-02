"""NI 43-101 data schemas and models for mineral resource reporting.

Defines the structured data types for mineral resource estimates
as they appear in National Instrument 43-101 technical reports.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ResourceCategory(str, Enum):
    """Mineral resource classification per NI 43-101 / CIM standards."""

    MEASURED = "Measured"
    INDICATED = "Indicated"
    INFERRED = "Inferred"
    M_I = "Measured & Indicated"
    PROVEN = "Proven"        # Mineral Reserve
    PROBABLE = "Probable"    # Mineral Reserve


class CommodityResource(BaseModel):
    """Resource estimate for a single commodity within a deposit."""

    commodity: str = Field(
        description="Commodity name, e.g. 'Lithium', 'Gold', 'Copper'"
    )
    category: ResourceCategory = Field(
        description="Resource classification category"
    )
    tonnage_mt: Optional[float] = Field(
        default=None, description="Tonnage in millions of metric tonnes"
    )
    grade: Optional[str] = Field(
        default=None, description="Grade, e.g. '1.2% Li2O', '4.5 g/t Au'"
    )
    contained_metal: Optional[str] = Field(
        default=None,
        description="Contained metal, e.g. '120,000 t Li2CO3'",
    )
    cut_off_grade: Optional[str] = Field(
        default=None, description="Cut-off grade used for the estimate"
    )


class DepositResources(BaseModel):
    """Aggregated mineral resource data for a single deposit/mine."""

    deposit_name: str = Field(description="Deposit or project name")
    report_title: Optional[str] = Field(
        default=None, description="Title of the source NI 43-101 report"
    )
    report_date: Optional[str] = Field(
        default=None, description="Date the report was filed"
    )
    effective_date: Optional[str] = Field(
        default=None, description="Effective date of the resource estimate"
    )
    commodities: list[CommodityResource] = Field(
        default_factory=list,
        description="List of commodity resource estimates",
    )
    notes: Optional[str] = Field(
        default=None, description="Additional notes or caveats"
    )
    qualified_person: Optional[str] = Field(
        default=None, description="Name of the Qualified Person (QP)"
    )


class MineralResourceReport(BaseModel):
    """Complete mineral resource extraction result from a PDF."""

    pdf_url: str = Field(description="URL of the source PDF")
    extraction_method: str = Field(
        description="Method used: 'tables', 'text_heuristic', or 'mock'"
    )
    deposits: list[DepositResources] = Field(
        default_factory=list,
        description="All deposits found in the report",
    )
    confidence: str = Field(
        default="medium",
        description="Extraction confidence: 'high', 'medium', or 'low'",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about data quality or extraction issues",
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="When this report was generated",
    )
