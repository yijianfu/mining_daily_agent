"""PDF text extraction using PyMuPDF (fitz).

Extracts all text blocks with coordinate metadata from a PDF file
for downstream NI 43-101 resource table and paragraph parsing.
"""

import tempfile
import os
from typing import Optional

from loguru import logger


class PDFTextBlock:
    """A single text block extracted from a PDF page."""

    def __init__(
        self,
        text: str,
        page: int,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> None:
        self.text = text.strip()
        self.page = page
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

    def __repr__(self) -> str:
        return (
            f"PDFTextBlock(page={self.page}, x0={self.x0:.0f}, "
            f"y0={self.y0:.0f}, text='{self.text[:50]}...')"
        )


class PDFParser:
    """Parse a PDF file and extract structured text blocks.

    Uses PyMuPDF for fast and accurate text extraction with
    positional metadata, which is critical for table detection
    and section identification in NI 43-101 reports.
    """

    def __init__(self, pdf_path: str) -> None:
        """Initialize the parser for a PDF file.

        Args:
            pdf_path: Path to the PDF file on disk.
        """
        self.pdf_path = pdf_path
        self._doc = None

    def __enter__(self) -> "PDFParser":
        import fitz  # PyMuPDF
        self._doc = fitz.open(self.pdf_path)
        return self

    def __exit__(self, *args) -> None:
        if self._doc:
            self._doc.close()
            self._doc = None

    @property
    def page_count(self) -> int:
        """Total number of pages in the PDF."""
        if self._doc is None:
            raise RuntimeError("PDF not opened. Use as context manager.")
        return len(self._doc)

    def extract_text_blocks(self) -> list[PDFTextBlock]:
        """Extract all text blocks from all pages with coordinates.

        Returns:
            List of PDFTextBlock objects sorted by page then y-position.
        """
        if self._doc is None:
            raise RuntimeError("PDF not opened. Use as context manager.")

        all_blocks: list[PDFTextBlock] = []

        for page_num, page in enumerate(self._doc):
            # Get text blocks with positions
            blocks = page.get_text("blocks")
            for block in blocks:
                # block = (x0, y0, x1, y1, text, block_no, block_type)
                x0, y0, x1, y1 = block[0], block[1], block[2], block[3]
                text = block[4] if len(block) > 4 else ""

                if text.strip():
                    all_blocks.append(PDFTextBlock(
                        text=text,
                        page=page_num + 1,
                        x0=x0,
                        y0=y0,
                        x1=x1,
                        y1=y1,
                    ))

        # Sort by page, then vertical position
        all_blocks.sort(key=lambda b: (b.page, b.y0, b.x0))

        logger.info(
            f"Extracted {len(all_blocks)} text blocks from "
            f"{self.page_count} pages"
        )
        return all_blocks

    def extract_full_text(self) -> str:
        """Extract full text from all pages (no coordinate data).

        Returns:
            All text concatenated with page separators.
        """
        if self._doc is None:
            raise RuntimeError("PDF not opened. Use as context manager.")

        pages_text: list[str] = []
        for page in self._doc:
            text = page.get_text()
            if text.strip():
                pages_text.append(text)

        return "\n\n--- PAGE BREAK ---\n\n".join(pages_text)

    def find_section(
        self,
        keywords: list[str],
        context_pages: int = 1,
    ) -> Optional[str]:
        """Find a specific section by keyword and return surrounding text.

        Useful for locating "Mineral Resource Estimate" sections in
        NI 43-101 reports.

        Args:
            keywords: Keywords to search for (case-insensitive).
            context_pages: How many pages after the match to include.

        Returns:
            Text of the matching section, or None if not found.
        """
        blocks = self.extract_text_blocks()

        # Find the first block matching any keyword
        match_page: Optional[int] = None
        for block in blocks:
            text_lower = block.text.lower()
            if any(kw.lower() in text_lower for kw in keywords):
                match_page = block.page
                break

        if match_page is None:
            return None

        # Collect text from match page + context pages
        section_blocks = [
            b for b in blocks
            if match_page <= b.page <= match_page + context_pages
        ]
        return "\n".join(b.text for b in section_blocks)

    @staticmethod
    def download_and_parse(
        pdf_url: str,
        http_client,
    ) -> "PDFParser":
        """Download a PDF and create a parser for it.

        Args:
            pdf_url: URL of the PDF to download.
            http_client: An HTTPClient instance.

        Returns:
            PDFParser instance with the downloaded PDF.

        Raises:
            ValueError: If download fails or content is not a PDF.
        """
        from servers.shared.async_utils import run_async

        logger.info(f"Downloading PDF: {pdf_url}")
        status, data = run_async(http_client.get(pdf_url))

        if status != 200:
            raise ValueError(f"HTTP {status} downloading PDF: {pdf_url}")

        # Validate PDF magic bytes
        if not data.startswith(b"%PDF"):
            raise ValueError(
                f"URL does not return a valid PDF (first bytes: {data[:20]!r})"
            )

        # Write to temp file
        tmp = tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, prefix="ni43_101_"
        )
        try:
            tmp.write(data)
            tmp.close()
            logger.info(f"PDF saved to temp: {tmp.name} ({len(data)} bytes)")
            return PDFParser(tmp.name)
        except Exception:
            os.unlink(tmp.name)
            raise
