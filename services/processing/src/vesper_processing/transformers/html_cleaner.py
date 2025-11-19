"""
HTML Cleaning Utilities

Provides functions to clean and normalize HTML content from SEC filings.
Removes boilerplate, fixes encodings, and normalizes whitespace.
"""

import re
import html
import unicodedata
from typing import Optional
from bs4 import BeautifulSoup, Comment, NavigableString


class HTMLCleaner:
    """Cleans and normalizes HTML content from SEC filings"""
    
    # Tags to remove completely (including content)
    REMOVE_TAGS = [
        'script', 'style', 'noscript', 'iframe', 'embed', 'object',
        'applet', 'link', 'meta', 'head'
    ]
    
    # Navigation/boilerplate patterns to remove
    BOILERPLATE_PATTERNS = [
        r'Table of Contents',
        r'Return to Index',
        r'Back to Table of Contents',
        r'^\s*\d+\s*$',  # Page numbers alone on a line
        r'UNITED STATES\s+SECURITIES AND EXCHANGE COMMISSION',
        r'Washington,?\s+D\.?C\.?\s+\d{5}',
        r'Commission File Number:?\s*\d+-\d+',
    ]
    
    def __init__(self):
        self.boilerplate_regex = re.compile(
            '|'.join(self.BOILERPLATE_PATTERNS),
            re.IGNORECASE | re.MULTILINE
        )
    
    def clean(self, html_content: str) -> str:
        """
        Clean HTML content and return normalized text
        
        Args:
            html_content: Raw HTML string
            
        Returns:
            Cleaned, normalized text
            
        Example:
            >>> cleaner = HTMLCleaner()
            >>> text = cleaner.clean("<p>Hello &nbsp; World</p>")
            >>> assert text == "Hello World"
        """
        if not html_content:
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted tags
        for tag_name in self.REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        # Remove HTML comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # Remove hidden elements
        for tag in soup.find_all(style=re.compile(r'display:\s*none', re.I)):
            tag.decompose()
        
        # Get text content
        text = soup.get_text(separator=' ', strip=False)
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Normalize Unicode characters
        text = self._normalize_unicode(text)
        
        # Remove boilerplate patterns
        text = self._remove_boilerplate(text)
        
        # Normalize whitespace
        text = self._normalize_whitespace(text)
        
        return text.strip()
    
    def _normalize_unicode(self, text: str) -> str:
        """Normalize Unicode characters to standard forms"""
        # Normalize to NFKC (compatibility decomposition + canonical composition)
        text = unicodedata.normalize('NFKC', text)
        
        # Replace common problematic characters
        replacements = {
            '\u00a0': ' ',      # Non-breaking space
            '\u200b': '',       # Zero-width space
            '\u2018': "'",      # Left single quote
            '\u2019': "'",      # Right single quote
            '\u201c': '"',      # Left double quote
            '\u201d': '"',      # Right double quote
            '\u2013': '-',      # En dash
            '\u2014': '--',     # Em dash
            '\u2026': '...',    # Ellipsis
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    def _remove_boilerplate(self, text: str) -> str:
        """Remove common SEC filing boilerplate text"""
        # Remove boilerplate patterns
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip lines that match boilerplate patterns
            if self.boilerplate_regex.search(line):
                continue
            
            # Skip very short lines (likely page numbers or artifacts)
            if len(line.strip()) < 3:
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text"""
        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)
        
        # Replace tabs with spaces
        text = text.replace('\t', ' ')
        
        # Replace multiple newlines with double newline (paragraph break)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove spaces at start/end of lines
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text
    
    def extract_metadata(self, html_content: str) -> dict:
        """
        Extract metadata from HTML filing
        
        Args:
            html_content: Raw HTML string
            
        Returns:
            Dictionary with metadata fields
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        metadata = {}
        
        # Try to extract company name
        company_tag = soup.find(string=re.compile(r'COMPANY CONFORMED NAME:', re.I))
        if company_tag:
            parent = company_tag.find_parent()
            if parent:
                metadata['company_name'] = parent.get_text().split(':', 1)[-1].strip()
        
        # Try to extract CIK
        cik_tag = soup.find(string=re.compile(r'CENTRAL INDEX KEY:', re.I))
        if cik_tag:
            parent = cik_tag.find_parent()
            if parent:
                cik_text = parent.get_text().split(':', 1)[-1].strip()
                metadata['cik'] = cik_text.zfill(10)  # Zero-pad to 10 digits
        
        # Try to extract form type
        form_tag = soup.find(string=re.compile(r'CONFORMED SUBMISSION TYPE:', re.I))
        if form_tag:
            parent = form_tag.find_parent()
            if parent:
                metadata['form_type'] = parent.get_text().split(':', 1)[-1].strip()
        
        # Try to extract filing date
        date_tag = soup.find(string=re.compile(r'FILED AS OF DATE:', re.I))
        if date_tag:
            parent = date_tag.find_parent()
            if parent:
                metadata['filing_date'] = parent.get_text().split(':', 1)[-1].strip()
        
        # Try to extract fiscal year end
        fiscal_tag = soup.find(string=re.compile(r'FISCAL YEAR END:', re.I))
        if fiscal_tag:
            parent = fiscal_tag.find_parent()
            if parent:
                metadata['fiscal_year_end'] = parent.get_text().split(':', 1)[-1].strip()
        
        return metadata


def clean_html(html_content: str) -> str:
    """
    Convenience function to clean HTML content
    
    Args:
        html_content: Raw HTML string
        
    Returns:
        Cleaned, normalized text
        
    Example:
        >>> text = clean_html("<p>Hello &nbsp; World</p>")
        >>> assert text == "Hello World"
    """
    cleaner = HTMLCleaner()
    return cleaner.clean(html_content)


def extract_text_stats(text: str) -> dict:
    """
    Calculate statistics about text content
    
    Args:
        text: Text to analyze
        
    Returns:
        Dictionary with text statistics
    """
    return {
        'text_length': len(text),
        'word_count': len(text.split()),
        'line_count': len(text.split('\n')),
        'paragraph_count': len([p for p in text.split('\n\n') if p.strip()]),
    }
