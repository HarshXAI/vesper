"""
PDF document parsing with text and table extraction.

Extracts text with layout preservation and tables from PDF documents
using pdfplumber, with parity to HTML parsing capabilities.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, BinaryIO
import pdfplumber
import re


@dataclass
class PDFTable:
    """
    Represents a table extracted from a PDF.
    
    Attributes:
        page_number: Page number (1-indexed)
        bbox: Bounding box (x0, top, x1, bottom)
        rows: List of rows, each row is a list of cell values
        num_rows: Number of rows
        num_cols: Number of columns
    """
    page_number: int
    bbox: tuple[float, float, float, float]
    rows: list[list[str]]
    num_rows: int
    num_cols: int
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'page_number': self.page_number,
            'bbox': self.bbox,
            'rows': self.rows,
            'num_rows': self.num_rows,
            'num_cols': self.num_cols,
        }
    
    def to_markdown(self) -> str:
        """Convert table to Markdown format"""
        if not self.rows:
            return ""
        
        lines = []
        
        # Header row
        if self.num_rows > 0:
            header = "| " + " | ".join(str(cell) for cell in self.rows[0]) + " |"
            lines.append(header)
            
            # Separator
            separator = "|" + "|".join([" --- "] * self.num_cols) + "|"
            lines.append(separator)
            
            # Data rows
            for row in self.rows[1:]:
                data_row = "| " + " | ".join(str(cell) for cell in row) + " |"
                lines.append(data_row)
        
        return "\n".join(lines)


@dataclass
class PDFSection:
    """
    Represents a section of a PDF document.
    
    Attributes:
        page_number: Starting page number (1-indexed)
        heading: Section heading text
        content: Section content text
        level: Heading level (1-6)
    """
    page_number: int
    heading: str
    content: str
    level: int
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'page_number': self.page_number,
            'heading': self.heading,
            'content': self.content,
            'level': self.level,
        }


@dataclass
class PDFDocument:
    """
    Represents a parsed PDF document.
    
    Attributes:
        num_pages: Total number of pages
        text: Full text content
        sections: List of sections
        tables: List of tables
        metadata: PDF metadata
    """
    num_pages: int
    text: str
    sections: list[PDFSection]
    tables: list[PDFTable]
    metadata: dict
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'num_pages': self.num_pages,
            'text': self.text,
            'sections': [s.to_dict() for s in self.sections],
            'tables': [t.to_dict() for t in self.tables],
            'metadata': self.metadata,
        }


class PDFParser:
    """
    Parse PDF documents with text and table extraction.
    
    Features:
    - Text extraction with layout preservation
    - Table extraction with cell detection
    - Section detection by heading patterns
    - Multi-column layout support
    - Metadata extraction
    """
    
    # Heading patterns (similar to HTML heading detection)
    HEADING_PATTERNS = [
        # Numbered sections: "1. Introduction", "1.1 Overview"
        r'^(\d+\.)+\s+[A-Z]',
        # All caps headings: "INTRODUCTION", "FINANCIAL STATEMENTS"
        r'^[A-Z][A-Z\s]+$',
        # Item headings: "Item 1. Business", "Item 7. Management"
        r'^Item\s+\d+[A-Z]?\.\s+',
        # Part headings: "Part I", "Part II"
        r'^Part\s+[IVX]+\s*\.?\s*$',
    ]
    
    def __init__(
        self,
        table_settings: Optional[dict] = None,
        min_table_rows: int = 2,
        min_table_cols: int = 2,
    ):
        """
        Initialize PDF parser.
        
        Args:
            table_settings: Custom table extraction settings for pdfplumber
            min_table_rows: Minimum rows for valid table
            min_table_cols: Minimum columns for valid table
        """
        self.table_settings = table_settings or {
            "vertical_strategy": "lines_strict",
            "horizontal_strategy": "lines_strict",
            "intersection_tolerance": 3,
        }
        self.min_table_rows = min_table_rows
        self.min_table_cols = min_table_cols
    
    def parse_file(self, pdf_path: str | Path) -> PDFDocument:
        """
        Parse a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            PDFDocument object with extracted content
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        with pdfplumber.open(pdf_path) as pdf:
            return self._parse_pdf(pdf)
    
    def parse_bytes(self, pdf_bytes: bytes) -> PDFDocument:
        """
        Parse a PDF from bytes.
        
        Args:
            pdf_bytes: PDF content as bytes
            
        Returns:
            PDFDocument object with extracted content
        """
        import io
        
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return self._parse_pdf(pdf)
    
    def _parse_pdf(self, pdf: pdfplumber.PDF) -> PDFDocument:
        """Parse a pdfplumber PDF object"""
        # Extract metadata
        metadata = pdf.metadata or {}
        
        # Extract text and tables from all pages
        all_text = []
        all_tables = []
        
        for page_num, page in enumerate(pdf.pages, start=1):
            # Extract text
            page_text = page.extract_text() or ""
            all_text.append(page_text)
            
            # Extract tables
            tables = page.extract_tables(table_settings=self.table_settings)
            for table_data in tables:
                if self._is_valid_table(table_data):
                    # Get table bounding box
                    table_bbox = self._get_table_bbox(page, table_data)
                    
                    pdf_table = PDFTable(
                        page_number=page_num,
                        bbox=table_bbox,
                        rows=table_data,
                        num_rows=len(table_data),
                        num_cols=len(table_data[0]) if table_data else 0,
                    )
                    all_tables.append(pdf_table)
        
        # Combine all text
        full_text = "\n\n".join(all_text)
        
        # Detect sections
        sections = self._detect_sections(all_text)
        
        return PDFDocument(
            num_pages=len(pdf.pages),
            text=full_text,
            sections=sections,
            tables=all_tables,
            metadata=metadata,
        )
    
    def _is_valid_table(self, table_data: list[list]) -> bool:
        """Check if table data is valid"""
        if not table_data:
            return False
        
        num_rows = len(table_data)
        if num_rows < self.min_table_rows:
            return False
        
        # Check columns
        num_cols = len(table_data[0]) if table_data else 0
        if num_cols < self.min_table_cols:
            return False
        
        # Check if table has mostly empty cells (likely not a real table)
        total_cells = num_rows * num_cols
        empty_cells = sum(
            1 for row in table_data for cell in row
            if not cell or not str(cell).strip()
        )
        
        # Reject if >50% empty
        if empty_cells / total_cells > 0.5:
            return False
        
        return True
    
    def _get_table_bbox(
        self, 
        page: pdfplumber.page.Page, 
        table_data: list[list]
    ) -> tuple[float, float, float, float]:
        """
        Get bounding box for table.
        
        For now, return placeholder bbox. In production, would calculate
        from table position on page.
        """
        # pdfplumber doesn't easily expose table bbox, so we use page dimensions
        # as placeholder. In production, could calculate from cell positions.
        return (0, 0, page.width, page.height)
    
    def _detect_sections(self, page_texts: list[str]) -> list[PDFSection]:
        """Detect sections from page texts"""
        sections = []
        
        for page_num, page_text in enumerate(page_texts, start=1):
            lines = page_text.split('\n')
            
            current_heading = None
            current_content = []
            current_level = 1
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line is a heading
                heading_match = self._is_heading(line)
                if heading_match:
                    # Save previous section
                    if current_heading:
                        sections.append(PDFSection(
                            page_number=page_num,
                            heading=current_heading,
                            content="\n".join(current_content),
                            level=current_level,
                        ))
                    
                    # Start new section
                    current_heading = line
                    current_content = []
                    current_level = heading_match['level']
                else:
                    # Add to current section content
                    if current_heading:
                        current_content.append(line)
            
            # Save last section
            if current_heading:
                sections.append(PDFSection(
                    page_number=page_num,
                    heading=current_heading,
                    content="\n".join(current_content),
                    level=current_level,
                ))
        
        return sections
    
    def _is_heading(self, line: str) -> Optional[dict]:
        """
        Check if a line is a heading.
        
        Returns:
            Dict with 'level' if heading, None otherwise
        """
        # Check numbered sections (e.g., "1. Intro", "1.1 Overview", "1.1.1 Details")
        # Pattern: one or more "number." sequences, optional space, capital letter
        match = re.match(r'^(\d+(?:\.\d+)*\.?)\s*([A-Z])', line)
        if match:
            num_part = match.group(1)
            # Count dots OR sections
            if '.' in num_part:
                # Count the number of dot-separated parts
                parts = [p for p in num_part.split('.') if p]
                return {'level': min(len(parts), 6)}
            else:
                return {'level': 1}
        
        # Check all caps (must be short, <100 chars)
        if re.match(r'^[A-Z][A-Z\s]+$', line) and len(line) < 100:
            return {'level': 1}
        
        # Check "Item N" headings
        if re.match(r'^Item\s+\d+[A-Z]?\.\s+', line):
            return {'level': 1}
        
        # Check "Part I/II/III" headings
        if re.match(r'^Part\s+[IVX]+', line):
            return {'level': 1}
        
        return None
    
    def extract_tables_only(self, pdf_path: str | Path) -> list[PDFTable]:
        """
        Extract only tables from a PDF (faster than full parsing).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of PDFTable objects
        """
        pdf_path = Path(pdf_path)
        tables = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_tables = page.extract_tables(table_settings=self.table_settings)
                
                for table_data in page_tables:
                    if self._is_valid_table(table_data):
                        table_bbox = self._get_table_bbox(page, table_data)
                        
                        pdf_table = PDFTable(
                            page_number=page_num,
                            bbox=table_bbox,
                            rows=table_data,
                            num_rows=len(table_data),
                            num_cols=len(table_data[0]) if table_data else 0,
                        )
                        tables.append(pdf_table)
        
        return tables
    
    def extract_text_only(self, pdf_path: str | Path) -> str:
        """
        Extract only text from a PDF (faster than full parsing).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Full text content
        """
        pdf_path = Path(pdf_path)
        all_text = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                all_text.append(page_text)
        
        return "\n\n".join(all_text)
    
    def get_page_count(self, pdf_path: str | Path) -> int:
        """
        Get number of pages in a PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Number of pages
        """
        pdf_path = Path(pdf_path)
        
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)
