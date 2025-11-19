"""
HTML parser for SEC filings
"""
import re
from typing import Optional, List, Tuple
from bs4 import BeautifulSoup, Tag, NavigableString
import structlog

logger = structlog.get_logger()


class HTMLParser:
    """
    Parse SEC HTML filings and extract clean text
    
    Handles:
    - XBRL tags and attributes
    - HTML tables (optional removal)
    - Excessive whitespace
    - Navigation elements
    - Style and script tags
    """
    
    def __init__(
        self,
        remove_tables: bool = False,
        preserve_line_breaks: bool = True,
    ):
        """
        Initialize HTML parser
        
        Args:
            remove_tables: Remove table elements from text extraction
            preserve_line_breaks: Preserve paragraph breaks in output
        """
        self.remove_tables = remove_tables
        self.preserve_line_breaks = preserve_line_breaks
        
    def parse(self, html_content: str) -> str:
        """
        Parse HTML and extract clean text
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            Clean text content
        """
        if not html_content:
            logger.warning("empty_html_content")
            return ""
        
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Remove unwanted elements
            self._remove_unwanted_elements(soup)
            
            # Remove XBRL attributes
            self._clean_xbrl_tags(soup)
            
            # Extract text
            text = self._extract_text(soup)
            
            # Clean and normalize
            text = self._clean_text(text)
            
            logger.info(
                "parsed_html",
                original_length=len(html_content),
                clean_length=len(text)
            )
            
            return text
            
        except Exception as e:
            logger.error("html_parsing_failed", error=str(e))
            raise
    
    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """Remove script, style, and navigation elements"""
        # Remove scripts and styles
        for element in soup(['script', 'style', 'meta', 'link']):
            element.decompose()
        
        # Remove common navigation elements
        for element in soup.find_all(class_=re.compile(r'(nav|menu|header|footer)', re.I)):
            element.decompose()
        
        # Remove tables if configured
        if self.remove_tables:
            for table in soup.find_all('table'):
                table.decompose()
    
    def _clean_xbrl_tags(self, soup: BeautifulSoup) -> None:
        """Remove XBRL namespaces and attributes"""
        # XBRL namespaces to remove
        xbrl_attrs = [
            'contextref', 'unitref', 'decimals', 'id',
            'escape', 'name', 'format', 'style'
        ]
        
        for tag in soup.find_all():
            # Remove XBRL attributes
            for attr in xbrl_attrs:
                if attr in tag.attrs:
                    del tag.attrs[attr]
            
            # Remove namespaced attributes (e.g., ix:*)
            attrs_to_remove = [
                attr for attr in tag.attrs 
                if ':' in attr
            ]
            for attr in attrs_to_remove:
                del tag.attrs[attr]
    
    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract text with preserved structure"""
        if self.preserve_line_breaks:
            # Add newlines for block elements
            for element in soup.find_all(['p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                if element.name == 'br':
                    element.replace_with('\n')
                else:
                    element.append('\n')
        
        # Get text
        text = soup.get_text(separator=' ' if not self.preserve_line_breaks else '')
        return text
    
    def _find_table_caption(self, table) -> Optional[str]:
        """
        Find caption for table by looking at preceding elements
        
        SEC filings often have table captions in:
        - Bold text immediately before table
        - Heading tags (h3, h4, h5) before table
        - Div elements with specific text content
        
        Tables are typically wrapped in divs, so we need to search
        the parent's previous siblings, not the table's.
        
        Args:
            table: BeautifulSoup table element
            
        Returns:
            Caption text if found, None otherwise
        """
        # First try table's immediate previous siblings (unlikely but worth checking)
        prev = table.previous_sibling
        attempts = 0
        max_attempts = 3
        
        while prev and attempts < max_attempts:
            attempts += 1
            if hasattr(prev, 'name') and prev.name:
                caption = self._extract_caption_from_element(prev)
                if caption:
                    return caption
            prev = prev.previous_sibling
        
        # Tables are usually wrapped - search parent's previous siblings
        parent = table.parent
        if parent:
            prev = parent.previous_sibling
            attempts = 0
            max_attempts = 10  # Search more siblings at parent level
            
            while prev and attempts < max_attempts:
                attempts += 1
                if hasattr(prev, 'name') and prev.name:
                    caption = self._extract_caption_from_element(prev)
                    if caption:
                        return caption
                prev = prev.previous_sibling
        
        return None
    
    def _extract_caption_from_element(self, element) -> Optional[str]:
        """
        Extract caption text from a single element if it looks like a caption.
        
        Args:
            element: BeautifulSoup element to check
            
        Returns:
            Caption text if element contains caption-like text, None otherwise
        """
        # Check if it's a heading
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            text = element.get_text(strip=True)
            if text and len(text) < 200:  # Reasonable caption length
                return text
        
        # Check if it's a div or p
        if element.name in ['div', 'p']:
            # Look for bold/strong tags
            bold_elements = element.find_all(['b', 'strong'])
            if bold_elements:
                text = ' '.join([b.get_text(strip=True) for b in bold_elements])
                if text and len(text) < 200:
                    return text
            
            # Get element text
            text = element.get_text(strip=True)
            if text and len(text) < 200:
                # Check if it has bold styling
                style = element.get('style', '')
                if 'font-weight' in style.lower() and ('bold' in style.lower() or '700' in style):
                    return text
                
                # Check if it contains financial statement keywords
                text_lower = text.lower()
                if any(keyword in text_lower for keyword in [
                    'consolidated statements',
                    'consolidated balance',
                    'balance sheet',
                    'income statement',
                    'cash flows',
                    'shareholders equity',
                    'statement of operations',
                    'statement of financial position',
                    'statement of cash flows',
                    'statements of operations',
                    'statements of comprehensive income'
                ]):
                    return text
        
        return None
    
    def _detect_header_rows(self, rows: List[List[str]]) -> int:
        """
        Detect how many rows at the beginning are headers (including multi-level headers).
        
        Uses heuristics to identify header rows:
        - Rows with year/date patterns (e.g., "2024", "September 28, 2024")
        - Rows with period indicators ("Years ended", "Three months ended")
        - Rows before the first row with majority numeric/currency values
        
        Args:
            rows: List of table rows
            
        Returns:
            Number of header rows (minimum 1, maximum 5)
        """
        if not rows or len(rows) < 2:
            return 1  # Default to single header row
        
        import re
        
        # Patterns for identifying header content
        year_pattern = re.compile(r'\b(19|20)\d{2}\b')  # Years like 2024, 2023
        date_pattern = re.compile(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{4}')
        period_pattern = re.compile(r'(years?|months?|quarters?)\s+(ended|ending)', re.IGNORECASE)
        currency_pattern = re.compile(r'^\$?[\(\-]?[\d,]+\.?\d*[\)]?$')
        
        header_count = 0
        max_header_rows = min(5, len(rows))  # Check up to 5 rows
        
        for i in range(max_header_rows):
            row = rows[i]
            is_header = False
            
            # Count cells with various indicators
            date_cells = 0
            empty_cells = 0
            numeric_cells = 0
            
            for cell in row:
                cell_stripped = cell.strip()
                
                # Empty cell
                if not cell_stripped or cell_stripped in ['', '—', '-']:
                    empty_cells += 1
                    continue
                
                # Check for date/year patterns
                if year_pattern.search(cell_stripped) or date_pattern.search(cell_stripped):
                    date_cells += 1
                    is_header = True
                    continue
                
                # Check for period indicators
                if period_pattern.search(cell_stripped):
                    is_header = True
                    continue
                
                # Check for numeric/currency values (indicates data row)
                if currency_pattern.match(cell_stripped):
                    numeric_cells += 1
            
            # Determine if this row is a header
            non_empty_cells = len(row) - empty_cells
            
            if non_empty_cells == 0:
                # All empty - might be separator, continue checking
                continue
            
            # If majority of cells have dates/years, it's a header row
            if date_cells >= non_empty_cells * 0.5:
                is_header = True
            
            # If row has period indicators, it's a header
            if period_pattern.search(' '.join(row)):
                is_header = True
            
            # If row has mostly numeric values, it's a data row (stop)
            if numeric_cells >= non_empty_cells * 0.5:
                break
            
            # If row has no dates and has numeric cells, likely data row
            if date_cells == 0 and numeric_cells > 0:
                break
            
            if is_header:
                header_count = i + 1
            else:
                # First non-header row, stop
                break
        
        # Always return at least 1 header row
        return max(1, header_count)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        # Remove excessive whitespace
        text = re.sub(r' +', ' ', text)
        
        # Normalize line breaks
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        # Remove empty lines at start and end
        text = text.strip()
        
        return text
    
    def extract_tables(self, html_content: str) -> List[Tuple[Optional[str], List[List[str]]]]:
        """
        Extract tables from HTML
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            List of (caption, rows) tuples
        """
        soup = BeautifulSoup(html_content, 'lxml')
        tables = []
        
        for idx, table in enumerate(soup.find_all('table')):
            # Get caption if present
            caption = None
            caption_tag = table.find('caption')
            if caption_tag:
                caption = caption_tag.get_text(strip=True)
            else:
                # Try to find caption in preceding elements
                caption = self._find_table_caption(table)
            
            # Extract rows
            rows = []
            for row in table.find_all('tr'):
                cells = []
                for cell in row.find_all(['td', 'th']):
                    # Handle colspan/rowspan
                    colspan = int(cell.get('colspan', 1))
                    cell_text = cell.get_text(strip=True)
                    
                    # Add cell text (repeat for colspan)
                    for _ in range(colspan):
                        cells.append(cell_text)
                
                if cells:
                    rows.append(cells)
            
            if rows:
                tables.append((caption, rows))
                logger.debug(
                    "extracted_table",
                    table_index=idx,
                    caption=caption,
                    row_count=len(rows)
                )
        
        return tables
