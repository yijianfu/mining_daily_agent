"""Table extraction from PDFs using pdfplumber.

Specialized in finding and parsing mineral resource estimate tables
from NI 43-101 technical reports.
"""

import re
from typing import Optional

from loguru import logger


class ResourceTable:
    """A structured mineral resource table extracted from a PDF."""

    def __init__(
        self,
        headers: list[str],
        rows: list[list[str]],
        page: int,
        caption: str = "",
    ) -> None:
        """Initialize a resource table.

        Args:
            headers: Column header strings.
            rows: Data rows (each row is a list of cell strings).
            page: Page number where the table was found.
            caption: Table caption or surrounding context text.
        """
        self.headers = headers
        self.rows = rows
        self.page = page
        self.caption = caption

    def to_dict(self) -> dict:
        """Convert to a plain dict for serialization."""
        return {
            "headers": self.headers,
            "rows": self.rows,
            "page": self.page,
            "caption": self.caption,
        }

    def __repr__(self) -> str:
        return (
            f"ResourceTable(page={self.page}, headers={self.headers}, "
            f"rows={len(self.rows)})"
        )


class TableExtractor:
    """Extract structured tables from PDF pages using pdfplumber.

    Focuses on locating tables that contain mineral resource data
    by searching for NI 43-101 keywords (Measured, Indicated, Inferred).
    """

    # NI 43-101 resource table indicators
    RESOURCE_KEYWORDS = [
        "measured", "indicated", "inferred",
        "resource category", "mineral resource",
        "tonnage", "grade", "contained",
        "cut-off", "cutoff",
    ]

    @staticmethod
    def find_resource_tables(
        pdf_path: str,
        min_keyword_matches: int = 2,
    ) -> list[ResourceTable]:
        """Find and parse tables from a PDF that likely contain resource data.

        Args:
            pdf_path: Path to the PDF file.
            min_keyword_matches: Minimum number of resource keywords that
                                 must appear in a table to be included.

        Returns:
            List of ResourceTable objects sorted by relevance.
        """
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed, skipping table extraction")
            return []

        tables: list[ResourceTable] = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()

                for table_idx, table_data in enumerate(page_tables):
                    if not table_data or len(table_data) < 2:
                        continue

                    # First row is typically headers
                    headers = [
                        str(c).strip() if c else ""
                        for c in table_data[0]
                    ]
                    rows = [
                        [str(c).strip() if c else "" for c in row]
                        for row in table_data[1:]
                    ]

                    # Remove empty rows
                    rows = [
                        r for r in rows
                        if any(c.strip() for c in r)
                    ]

                    if not rows:
                        continue

                    # Check for resource keywords
                    all_text = " ".join(headers).lower()
                    for row in rows:
                        all_text += " " + " ".join(row).lower()

                    keyword_hits = sum(
                        1 for kw in TableExtractor.RESOURCE_KEYWORDS
                        if kw in all_text
                    )

                    if keyword_hits >= min_keyword_matches:
                        # Extract surrounding text as caption
                        caption = TableExtractor._get_table_context(
                            page, table_idx
                        )

                        tables.append(ResourceTable(
                            headers=headers,
                            rows=rows,
                            page=page_num + 1,
                            caption=caption,
                        ))

        logger.info(
            f"Found {len(tables)} resource tables across "
            f"{len(tables[0].rows) if tables else 0} rows"
        )
        return tables

    @staticmethod
    def _get_table_context(page, table_index: int) -> str:
        """Get text surrounding a table for context."""
        try:
            # Get all text on the page, limited to first 500 chars
            text = page.extract_text()
            if text:
                return text[:500].replace("\n", " ")
        except Exception:
            pass
        return ""

    @staticmethod
    def tables_from_pdfplumber(pdf_path: str) -> list[list[list[str]]]:
        """Extract ALL tables from a PDF as raw nested lists.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of tables, each table is a list of rows, each row a
            list of cell strings.
        """
        try:
            import pdfplumber
        except ImportError:
            return []

        all_tables: list[list[list[str]]] = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for t in tables:
                    if t and len(t) > 1:
                        cleaned = [
                            [str(c).strip() if c else "" for c in row]
                            for row in t
                        ]
                        all_tables.append(cleaned)

        return all_tables
