"""NI 43-101 mineral resource parser.

Parses structured tables and free-form text to extract mineral resource
estimates (Measured, Indicated, Inferred) with tonnage, grade, and
contained metal data.

Combines table-based extraction with regex heuristics for paragraph text.
"""

import re
from typing import Optional

from loguru import logger

from servers.mineral_pdf_mcp.extractors.table_extractor import ResourceTable
from servers.mineral_pdf_mcp.schemas import (
    CommodityResource,
    DepositResources,
    MineralResourceReport,
    ResourceCategory,
)


class ResourceParser:
    """Parse NI 43-101 resource data from tables and text.

    Uses a multi-stage pipeline:
    1. Try to parse structured tables (high confidence)
    2. Apply regex heuristics to full text (medium confidence)
    3. Fall back to empty result with warnings
    """

    # Regex patterns for NI 43-101 standard phrasing
    PATTERNS = {
        "measured": re.compile(
            r"measured\s*(?:mineral\s*)?resources?\s*(?:of|totalling|total|:)?\s*"
            r"(\d[\d,.]*)\s*(?:million\s*)?(?:metric\s*)?(tonnes?|Mt|t)",
            re.IGNORECASE,
        ),
        "indicated": re.compile(
            r"indicated\s*(?:mineral\s*)?resources?\s*(?:of|totalling|total|:)?\s*"
            r"(\d[\d,.]*)\s*(?:million\s*)?(?:metric\s*)?(tonnes?|Mt|t)",
            re.IGNORECASE,
        ),
        "inferred": re.compile(
            r"inferred\s*(?:mineral\s*)?resources?\s*(?:of|totalling|total|:)?\s*"
            r"(\d[\d,.]*)\s*(?:million\s*)?(?:metric\s*)?(tonnes?|Mt|t)",
            re.IGNORECASE,
        ),
        "grade_li2o": re.compile(
            r"(\d[\d.]*)\s*%\s*Li2?O",
            re.IGNORECASE,
        ),
        "grade_au": re.compile(
            r"(\d[\d.]*)\s*g/t\s*(?:Au|gold)",
            re.IGNORECASE,
        ),
        "grade_cu": re.compile(
            r"(\d[\d.]*)\s*%\s*Cu",
            re.IGNORECASE,
        ),
        "contained": re.compile(
            r"(?:containing|contained)\s*(?:metal|metal\s*content)?\s*(?:of)?\s*"
            r"([\d,]+)\s*(tonnes?|t|oz|ounces?|lbs?|pounds?)\s*(?:of\s*)?"
            r"(\w+(?:\s*\w+)*)",
            re.IGNORECASE,
        ),
        "deposit_name": re.compile(
            r"(?:deposit|project|mine|property)\s*(?:name|:)?\s*(?:is|:)?\s*"
            r"([A-Z][\w\s\-']+)",
            re.IGNORECASE,
        ),
    }

    # Known deposit names for context matching
    KNOWN_DEPOSITS = [
        "Pilgangoora", "Greenbushes", "Wodgina", "Mt Marion",
        "Bald Hill", "Mt Cattlin", "Ngungaju", "Pilbara",
        "Nevada", "Clayton Valley", "Thacker Pass", "Rhyolite Ridge",
        "Sal de Vida", "Cauchari-Olaroz", "Olaroz", "Rincon",
        "James Bay", "Whabouchi", "Rose", "Corvette",
        "Arcadia", "Bikita", "Manono", "Goulamina",
    ]

    @classmethod
    def parse_from_tables(
        cls,
        tables: list[ResourceTable],
        pdf_url: str,
        full_text: str = "",
    ) -> MineralResourceReport:
        """Parse mineral resource data from structured tables.

        This is the primary (high-confidence) extraction path.

        Args:
            tables: List of resource tables extracted from the PDF.
            pdf_url: Source PDF URL for attribution.
            full_text: Full PDF text for context (deposit name detection).

        Returns:
            MineralResourceReport with parsed deposits and resources.
        """
        deposits: list[DepositResources] = []
        warnings: list[str] = []

        if not tables:
            return MineralResourceReport(
                pdf_url=pdf_url,
                extraction_method="tables",
                deposits=[],
                confidence="low",
                warnings=["No resource tables found in the PDF"],
            )

        # Detect deposit name from text
        deposit_name = cls._detect_deposit_name(full_text)

        for table in tables:
            try:
                resources = cls._parse_single_table(table, full_text)
                if resources:
                    deposits.append(DepositResources(
                        deposit_name=deposit_name or "Unknown Deposit",
                        report_title=cls._extract_report_title(full_text),
                        commodities=resources,
                    ))
            except Exception as e:
                logger.warning(f"Failed to parse table on page {table.page}: {e}")
                warnings.append(f"Table on page {table.page} parse error: {e}")

        confidence = cls._assess_confidence(deposits, warnings)

        return MineralResourceReport(
            pdf_url=pdf_url,
            extraction_method="tables",
            deposits=deposits,
            confidence=confidence,
            warnings=warnings,
        )

    @classmethod
    def parse_from_text(
        cls,
        full_text: str,
        pdf_url: str,
    ) -> MineralResourceReport:
        """Parse mineral resource data from free-form text using regex.

        This is the fallback (medium-confidence) extraction path used
        when no structured tables are found.

        Args:
            full_text: Full PDF text content.
            pdf_url: Source PDF URL for attribution.

        Returns:
            MineralResourceReport with heuristically extracted data.
        """
        deposits: list[DepositResources] = []
        warnings: list[str] = []

        deposit_name = cls._detect_deposit_name(full_text)
        commodities: list[CommodityResource] = []

        # Search for resource statements by category
        for category, pattern in [
            (ResourceCategory.MEASURED, cls.PATTERNS["measured"]),
            (ResourceCategory.INDICATED, cls.PATTERNS["indicated"]),
            (ResourceCategory.INFERRED, cls.PATTERNS["inferred"]),
        ]:
            match = pattern.search(full_text)
            if match:
                tonnage_str = match.group(1).replace(",", "")
                try:
                    tonnage = float(tonnage_str)
                except ValueError:
                    tonnage = None
                    warnings.append(
                        f"Could not parse {category.value} tonnage: {tonnage_str}"
                    )

                # Try to find a matching grade
                grade = cls._extract_grade(full_text)
                contained = cls._extract_contained(full_text)
                commodity = cls._detect_commodity(full_text)

                commodities.append(CommodityResource(
                    commodity=commodity,
                    category=category,
                    tonnage_mt=tonnage,
                    grade=grade,
                    contained_metal=contained,
                ))

        if commodities:
            deposits.append(DepositResources(
                deposit_name=deposit_name or "Unknown Deposit",
                commodities=commodities,
            ))
        else:
            warnings.append(
                "No mineral resource data found in text. "
                "The PDF may not contain resource estimates, or they "
                "may be in a non-standard format."
            )

        confidence = cls._assess_confidence(deposits, warnings)

        return MineralResourceReport(
            pdf_url=pdf_url,
            extraction_method="text_heuristic",
            deposits=deposits,
            confidence=confidence,
            warnings=warnings,
        )

    @classmethod
    def _parse_single_table(
        cls, table: ResourceTable, full_text: str = ""
    ) -> list[CommodityResource]:
        """Parse a single resource table into commodity resource entries."""
        resources: list[CommodityResource] = []
        commodity = cls._detect_commodity(
            " ".join(table.headers) + " " + full_text
        )

        for row in table.rows:
            row_text = " ".join(row).lower()

            category: Optional[ResourceCategory] = None
            if "measured" in row_text and "indicated" in row_text:
                category = ResourceCategory.M_I
            elif "measured" in row_text:
                category = ResourceCategory.MEASURED
            elif "indicated" in row_text:
                category = ResourceCategory.INDICATED
            elif "inferred" in row_text:
                category = ResourceCategory.INFERRED
            elif "proven" in row_text:
                category = ResourceCategory.PROVEN
            elif "probable" in row_text:
                category = ResourceCategory.PROBABLE
            else:
                # Check headers for category context
                header_text = " ".join(table.headers).lower()
                if "measured" in header_text:
                    category = ResourceCategory.MEASURED
                elif "indicated" in header_text:
                    category = ResourceCategory.INDICATED
                elif "inferred" in header_text:
                    category = ResourceCategory.INFERRED

            if category is None:
                continue

            # Extract numeric values from row
            tonnage = cls._extract_tonnage_from_row(row)
            grade = cls._extract_grade_from_row(row, table.headers)

            resources.append(CommodityResource(
                commodity=commodity,
                category=category,
                tonnage_mt=tonnage,
                grade=grade,
            ))

        return resources

    @classmethod
    def _extract_tonnage_from_row(cls, row: list[str]) -> Optional[float]:
        """Extract tonnage value from a table row."""
        for cell in row:
            # Match patterns like "123.4", "1,234.5", "1234567"
            match = re.search(r"(\d[\d,.]*)\s*(?:Mt|t|tonnes?)?", cell)
            if match:
                val = match.group(1).replace(",", "")
                try:
                    return float(val)
                except ValueError:
                    continue
        return None

    @classmethod
    def _extract_grade_from_row(
        cls, row: list[str], headers: list[str]
    ) -> Optional[str]:
        """Extract grade value from a table row."""
        # Look for cells containing % or g/t
        for cell in row:
            if re.search(r"\d[\d.]*\s*%", cell):
                return cell.strip()
            if re.search(r"\d[\d.]*\s*g/t", cell, re.IGNORECASE):
                return cell.strip()
            if re.search(r"\d[\d.]*\s*ppm", cell, re.IGNORECASE):
                return cell.strip()
        return None

    @classmethod
    def _detect_deposit_name(cls, text: str) -> Optional[str]:
        """Try to identify the deposit/project name from text."""
        # Check known deposits first
        text_lower = text.lower()
        for deposit in cls.KNOWN_DEPOSITS:
            if deposit.lower() in text_lower:
                return deposit

        # Try regex
        match = cls.PATTERNS["deposit_name"].search(text)
        if match:
            return match.group(1).strip()

        return None

    @classmethod
    def _detect_commodity(cls, text: str) -> str:
        """Detect the primary commodity from text."""
        text_lower = text.lower()
        if "lithium" in text_lower or "li2o" in text_lower or "spodumene" in text_lower:
            return "Lithium"
        if "gold" in text_lower or " au " in text_lower:
            return "Gold"
        if "copper" in text_lower or " cu " in text_lower:
            return "Copper"
        if "nickel" in text_lower or " ni " in text_lower:
            return "Nickel"
        if "silver" in text_lower or " ag " in text_lower:
            return "Silver"
        if "iron" in text_lower or "fe " in text_lower:
            return "Iron Ore"
        if "zinc" in text_lower or " zn " in text_lower:
            return "Zinc"
        if "uranium" in text_lower or "u3o8" in text_lower:
            return "Uranium"
        if "cobalt" in text_lower:
            return "Cobalt"
        return "Unknown"

    @classmethod
    def _extract_grade(cls, text: str) -> Optional[str]:
        """Extract grade information from text."""
        for pat_name in ["grade_li2o", "grade_au", "grade_cu"]:
            match = cls.PATTERNS[pat_name].search(text)
            if match:
                return match.group(0).strip()

        # Generic grade patterns
        grade_match = re.search(
            r"(\d[\d.]*\s*%\s*\w+(?:\s*\w+)*|\d[\d.]*\s*g/t\s*\w*)",
            text,
            re.IGNORECASE,
        )
        if grade_match:
            return grade_match.group(0).strip()
        return None

    @classmethod
    def _extract_contained(cls, text: str) -> Optional[str]:
        """Extract contained metal information from text."""
        match = cls.PATTERNS["contained"].search(text)
        if match:
            return match.group(0).strip()
        return None

    @classmethod
    def _extract_report_title(cls, text: str) -> Optional[str]:
        """Extract the NI 43-101 report title from text."""
        # Look for common title patterns
        patterns = [
            r"(NI\s*43[-–]101\s*(?:Technical\s*)?Report[^.]*(?:\.|$))",
            r"(Technical\s*Report[^.]*(?:NI\s*43[-–]101[^.]*)?(?:\.|$))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]
        # Fallback: first meaningful line
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 20]
        return lines[0][:200] if lines else None

    @classmethod
    def _assess_confidence(
        cls,
        deposits: list[DepositResources],
        warnings: list[str],
    ) -> str:
        """Assess extraction confidence based on results."""
        if not deposits:
            return "low"
        total_resources = sum(len(d.commodities) for d in deposits)
        if total_resources >= 3 and not warnings:
            return "high"
        if total_resources >= 1:
            return "medium"
        return "low"

    # ── Mock Data ─────────────────────────────────────────────────────────

    @classmethod
    def mock_report(cls, pdf_url: str) -> MineralResourceReport:
        """Generate a realistic mock NI 43-101 extraction result.

        Used when a real PDF cannot be downloaded or parsed.

        Args:
            pdf_url: The PDF URL that was attempted.

        Returns:
            A MineralResourceReport with hardcoded realistic data.
        """
        # Determine which deposit to mock based on URL hints
        url_lower = pdf_url.lower()

        if "pilgangoora" in url_lower or "pilbara" in url_lower:
            return cls._mock_pilgangoora(pdf_url)
        elif "greenbushes" in url_lower:
            return cls._mock_greenbushes(pdf_url)
        elif "wodgina" in url_lower:
            return cls._mock_wodgina(pdf_url)
        else:
            # Default: generic Pilbara lithium mock
            return cls._mock_pilgangoora(pdf_url)

    @classmethod
    def _mock_pilgangoora(cls, pdf_url: str) -> MineralResourceReport:
        """Mock data for Pilgangoora Lithium-Tantalum Project."""
        return MineralResourceReport(
            pdf_url=pdf_url,
            extraction_method="mock",
            confidence="medium",
            warnings=["This is mock/synthetic data for demonstration purposes"],
            deposits=[
                DepositResources(
                    deposit_name="Pilgangoora",
                    report_title=(
                        "NI 43-101 Technical Report — Pilgangoora "
                        "Lithium-Tantalum Project, Western Australia"
                    ),
                    report_date="2025-08-15",
                    effective_date="2025-06-30",
                    qualified_person="Mr. John Smith, P.Geo. (QP)",
                    commodities=[
                        CommodityResource(
                            commodity="Lithium",
                            category=ResourceCategory.MEASURED,
                            tonnage_mt=108.2,
                            grade="1.25% Li2O",
                            contained_metal="1.35 Mt Li2O",
                            cut_off_grade="0.5% Li2O",
                        ),
                        CommodityResource(
                            commodity="Lithium",
                            category=ResourceCategory.INDICATED,
                            tonnage_mt=106.8,
                            grade="1.17% Li2O",
                            contained_metal="1.25 Mt Li2O",
                            cut_off_grade="0.5% Li2O",
                        ),
                        CommodityResource(
                            commodity="Lithium",
                            category=ResourceCategory.INFERRED,
                            tonnage_mt=94.0,
                            grade="1.10% Li2O",
                            contained_metal="1.03 Mt Li2O",
                            cut_off_grade="0.5% Li2O",
                        ),
                        CommodityResource(
                            commodity="Tantalum",
                            category=ResourceCategory.M_I,
                            tonnage_mt=215.0,
                            grade="120 ppm Ta2O5",
                            contained_metal="25,800 t Ta2O5",
                        ),
                    ],
                    notes=(
                        "Total Measured + Indicated + Inferred: 309.0 Mt @ "
                        "1.17% Li2O. Open pit constrained resources."
                    ),
                ),
            ],
        )

    @classmethod
    def _mock_greenbushes(cls, pdf_url: str) -> MineralResourceReport:
        """Mock data for Greenbushes Lithium Mine."""
        return MineralResourceReport(
            pdf_url=pdf_url,
            extraction_method="mock",
            confidence="medium",
            warnings=["This is mock/synthetic data for demonstration purposes"],
            deposits=[
                DepositResources(
                    deposit_name="Greenbushes",
                    report_title=(
                        "NI 43-101 Technical Report — Greenbushes Lithium "
                        "Operations, Western Australia"
                    ),
                    commodities=[
                        CommodityResource(
                            commodity="Lithium",
                            category=ResourceCategory.MEASURED,
                            tonnage_mt=86.4,
                            grade="2.35% Li2O",
                            contained_metal="2.03 Mt Li2O",
                            cut_off_grade="0.5% Li2O",
                        ),
                        CommodityResource(
                            commodity="Lithium",
                            category=ResourceCategory.INDICATED,
                            tonnage_mt=42.7,
                            grade="1.87% Li2O",
                            contained_metal="0.80 Mt Li2O",
                            cut_off_grade="0.5% Li2O",
                        ),
                        CommodityResource(
                            commodity="Lithium",
                            category=ResourceCategory.INFERRED,
                            tonnage_mt=33.1,
                            grade="1.52% Li2O",
                            contained_metal="0.50 Mt Li2O",
                            cut_off_grade="0.5% Li2O",
                        ),
                    ],
                    notes="World's largest hard-rock lithium mine. Joint venture: Tianqi/IGO (51%), Albemarle (49%).",
                ),
            ],
        )

    @classmethod
    def _mock_wodgina(cls, pdf_url: str) -> MineralResourceReport:
        """Mock data for Wodgina Lithium Project."""
        return MineralResourceReport(
            pdf_url=pdf_url,
            extraction_method="mock",
            confidence="medium",
            warnings=["This is mock/synthetic data for demonstration purposes"],
            deposits=[
                DepositResources(
                    deposit_name="Wodgina",
                    report_title=(
                        "NI 43-101 Technical Report — Wodgina Lithium "
                        "Project, Western Australia"
                    ),
                    commodities=[
                        CommodityResource(
                            commodity="Lithium",
                            category=ResourceCategory.MEASURED,
                            tonnage_mt=57.8,
                            grade="1.17% Li2O",
                            contained_metal="0.68 Mt Li2O",
                        ),
                        CommodityResource(
                            commodity="Lithium",
                            category=ResourceCategory.INDICATED,
                            tonnage_mt=44.3,
                            grade="1.14% Li2O",
                            contained_metal="0.50 Mt Li2O",
                        ),
                        CommodityResource(
                            commodity="Lithium",
                            category=ResourceCategory.INFERRED,
                            tonnage_mt=49.1,
                            grade="1.10% Li2O",
                            contained_metal="0.54 Mt Li2O",
                        ),
                    ],
                ),
            ],
        )
