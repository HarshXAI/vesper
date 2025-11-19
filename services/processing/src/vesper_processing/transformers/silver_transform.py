"""
Silver Layer Transformation Service

Transforms Bronze layer raw filings into Silver layer normalized and enriched data.
"""

import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path

from ..html_parser import HTMLParser
from ..section_extractor import SectionExtractor
from ..table_extractor import TableExtractor
from ..table_classifier import TableClassifier
from .html_cleaner import HTMLCleaner, extract_text_stats
from .cik_ticker_mapper import CIKTickerMapper


class SilverFiling:
    """Represents a filing in the Silver layer"""
    
    def __init__(self):
        # Primary Keys & Identifiers
        self.filing_id: Optional[str] = None
        self.accession_number: Optional[str] = None
        self.cik: Optional[str] = None
        self.ticker: Optional[str] = None
        self.company_name: Optional[str] = None
        
        # Filing Metadata
        self.form_type: Optional[str] = None
        self.filing_date: Optional[str] = None
        self.period_end: Optional[str] = None
        self.fiscal_year: Optional[int] = None
        self.fiscal_quarter: Optional[int] = None
        
        # Normalized Content
        self.normalized_text: Optional[str] = None
        self.text_length: int = 0
        self.word_count: int = 0
        
        # Document Structure
        self.section_count: int = 0
        self.table_count: int = 0
        self.has_financials: bool = False
        
        # Enrichment
        self.industry_sector: Optional[str] = None
        self.market_cap_tier: Optional[str] = None
        
        # Provenance & Lineage
        self.bronze_s3_path: Optional[str] = None
        self.document_hash: Optional[str] = None
        self.transform_version: str = "1.0"
        self.transform_timestamp: Optional[str] = None
        
        # Data Quality
        self.quality_score: float = 0.0
        self.has_parsing_errors: bool = False
        self.parsing_error_details: Optional[str] = None
        
        # Metadata
        self.created_at: Optional[str] = None
        self.updated_at: Optional[str] = None
        
        # Additional data
        self.sections: List[Dict] = []
        self.tables: List[Dict] = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        return {
            'filing_id': self.filing_id,
            'accession_number': self.accession_number,
            'cik': self.cik,
            'ticker': self.ticker,
            'company_name': self.company_name,
            'form_type': self.form_type,
            'filing_date': self.filing_date,
            'period_end': self.period_end,
            'fiscal_year': self.fiscal_year,
            'fiscal_quarter': self.fiscal_quarter,
            'normalized_text': self.normalized_text,
            'text_length': self.text_length,
            'word_count': self.word_count,
            'section_count': self.section_count,
            'table_count': self.table_count,
            'has_financials': self.has_financials,
            'industry_sector': self.industry_sector,
            'market_cap_tier': self.market_cap_tier,
            'bronze_s3_path': self.bronze_s3_path,
            'document_hash': self.document_hash,
            'transform_version': self.transform_version,
            'transform_timestamp': self.transform_timestamp or timestamp,
            'quality_score': self.quality_score,
            'has_parsing_errors': self.has_parsing_errors,
            'parsing_error_details': self.parsing_error_details,
            'created_at': self.created_at or timestamp,
            'updated_at': self.updated_at or timestamp,
            'sections': self.sections,
            'tables': self.tables,
        }


class SilverTransformer:
    """Transforms Bronze layer filings to Silver layer"""
    
    def __init__(self, cik_mapper: Optional[CIKTickerMapper] = None):
        """
        Initialize the Silver transformer
        
        Args:
            cik_mapper: Optional CIK to ticker mapper (uses default if None)
        """
        self.html_cleaner = HTMLCleaner()
        self.html_parser = HTMLParser()
        self.section_extractor = SectionExtractor()
        self.table_extractor = TableExtractor()
        self.table_classifier = TableClassifier()
        self.cik_mapper = cik_mapper or CIKTickerMapper()
        
        self.errors: List[str] = []
    
    def transform(self, bronze_filing: dict, bronze_s3_path: str) -> SilverFiling:
        """
        Transform a Bronze filing to Silver
        
        Args:
            bronze_filing: Dictionary with Bronze filing data
                           Must contain: 'html_content', 'metadata'
            bronze_s3_path: S3 path to the Bronze filing
            
        Returns:
            SilverFiling object
            
        Example:
            >>> transformer = SilverTransformer()
            >>> bronze = {'html_content': '<html>...</html>', 'metadata': {...}}
            >>> silver = transformer.transform(bronze, 's3://bucket/path')
            >>> assert silver.ticker is not None
        """
        self.errors = []
        silver = SilverFiling()
        
        try:
            # Extract metadata
            metadata = bronze_filing.get('metadata', {})
            html_content = bronze_filing.get('html_content', '')
            
            # Set basic identifiers
            silver.accession_number = metadata.get('accession_number')
            silver.cik = metadata.get('cik', '').zfill(10)
            silver.filing_id = f"{silver.cik}_{silver.accession_number}"
            
            # Map CIK to ticker and get company metadata
            cik_metadata = self.cik_mapper.get_metadata(silver.cik)
            if cik_metadata:
                silver.ticker = cik_metadata.get('ticker')
                silver.company_name = cik_metadata.get('name') or metadata.get('company_name')
                silver.industry_sector = cik_metadata.get('sector')
            else:
                silver.company_name = metadata.get('company_name')
            
            # Set filing metadata
            silver.form_type = metadata.get('form_type')
            silver.filing_date = metadata.get('filing_date')
            silver.period_end = metadata.get('period_end')
            
            # Extract fiscal year/quarter from period_end
            if silver.period_end:
                silver.fiscal_year, silver.fiscal_quarter = self._parse_fiscal_period(silver.period_end)
            
            # Clean HTML content
            silver.normalized_text = self.html_cleaner.clean(html_content)
            
            # Calculate text statistics
            text_stats = extract_text_stats(silver.normalized_text)
            silver.text_length = text_stats['text_length']
            silver.word_count = text_stats['word_count']
            
            # Calculate document hash for provenance
            silver.document_hash = self._calculate_hash(silver.normalized_text)
            
            # Extract sections
            try:
                sections = self.section_extractor.extract_sections(html_content)
                silver.sections = [self._section_to_dict(s, silver.filing_id) for s in sections]
                silver.section_count = len(sections)
            except Exception as e:
                self.errors.append(f"Section extraction error: {str(e)}")
            
            # Extract tables
            try:
                parsed = self.html_parser.parse(html_content)
                tables = parsed.tables
                
                # Classify tables
                classified_tables = []
                for i, table in enumerate(tables):
                    try:
                        table_type = self.table_classifier.classify(table)
                        table_dict = self._table_to_dict(table, silver.filing_id, i, table_type)
                        classified_tables.append(table_dict)
                        
                        # Check if financial table
                        if table_type in ['balance_sheet', 'income_statement', 'cash_flow']:
                            silver.has_financials = True
                    except Exception as e:
                        self.errors.append(f"Table {i} classification error: {str(e)}")
                
                silver.tables = classified_tables
                silver.table_count = len(tables)
            except Exception as e:
                self.errors.append(f"Table extraction error: {str(e)}")
            
            # Set provenance
            silver.bronze_s3_path = bronze_s3_path
            silver.transform_timestamp = datetime.utcnow().isoformat() + 'Z'
            
            # Calculate quality score
            silver.quality_score = self._calculate_quality_score(silver)
            
            # Set error flags
            if self.errors:
                silver.has_parsing_errors = True
                silver.parsing_error_details = json.dumps(self.errors)
            
        except Exception as e:
            self.errors.append(f"Critical transformation error: {str(e)}")
            silver.has_parsing_errors = True
            silver.parsing_error_details = json.dumps(self.errors)
            silver.quality_score = 0.0
        
        return silver
    
    def _parse_fiscal_period(self, period_end: str) -> tuple[Optional[int], Optional[int]]:
        """
        Parse fiscal year and quarter from period end date
        
        Args:
            period_end: Date string (YYYY-MM-DD)
            
        Returns:
            Tuple of (fiscal_year, fiscal_quarter)
        """
        try:
            # Parse date
            if isinstance(period_end, str):
                from datetime import datetime as dt
                date = dt.fromisoformat(period_end.replace('Z', '+00:00'))
            else:
                date = period_end
            
            fiscal_year = date.year
            
            # Determine quarter based on month
            month = date.month
            if month in [1, 2, 3]:
                fiscal_quarter = 1
            elif month in [4, 5, 6]:
                fiscal_quarter = 2
            elif month in [7, 8, 9]:
                fiscal_quarter = 3
            else:
                fiscal_quarter = 4
            
            return fiscal_year, fiscal_quarter
        except Exception:
            return None, None
    
    def _calculate_hash(self, text: str) -> str:
        """Calculate SHA-256 hash of text"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _section_to_dict(self, section: Any, filing_id: str) -> dict:
        """Convert section object to dictionary"""
        section_type = getattr(section, 'section_type', 'OTHER')
        sequence = getattr(section, 'sequence', 0)
        
        return {
            'section_id': f"{filing_id}_{section_type}_{sequence}",
            'filing_id': filing_id,
            'section_type': section_type,
            'section_title': getattr(section, 'title', None),
            'section_number': getattr(section, 'number', None),
            'sequence_order': sequence,
            'normalized_text': getattr(section, 'text', ''),
            'text_length': len(getattr(section, 'text', '')),
            'word_count': len(getattr(section, 'text', '').split()),
            'document_hash': self._calculate_hash(getattr(section, 'text', '')),
        }
    
    def _table_to_dict(self, table: Any, filing_id: str, sequence: int, table_type: str) -> dict:
        """Convert table object to dictionary"""
        # Extract table data
        table_data = []
        if hasattr(table, 'rows'):
            for row in table.rows:
                if hasattr(row, 'cells'):
                    table_data.append([cell.text if hasattr(cell, 'text') else str(cell) 
                                     for cell in row.cells])
        
        return {
            'table_id': f"{filing_id}_table_{sequence}",
            'filing_id': filing_id,
            'table_type': table_type,
            'table_type_confidence': 0.8,  # Placeholder
            'caption': getattr(table, 'caption', None),
            'sequence_order': sequence,
            'num_rows': len(table_data),
            'num_columns': len(table_data[0]) if table_data else 0,
            'has_multiindex_headers': hasattr(table, 'has_multiindex_headers') and table.has_multiindex_headers,
            'header_levels': getattr(table, 'header_levels', 1),
            'table_data_json': json.dumps(table_data),
            'document_hash': self._calculate_hash(json.dumps(table_data)),
        }
    
    def _calculate_quality_score(self, silver: SilverFiling) -> float:
        """
        Calculate data quality score (0.0 to 1.0)
        
        Checks:
        - Has ticker (20%)
        - Has period_end (20%)
        - Has normalized_text (20%)
        - Text length > 1000 (20%)
        - No parsing errors (20%)
        """
        score = 0.0
        
        # Check ticker
        if silver.ticker:
            score += 0.2
        
        # Check period_end
        if silver.period_end:
            score += 0.2
        
        # Check normalized_text
        if silver.normalized_text:
            score += 0.2
        
        # Check text length
        if silver.text_length > 1000:
            score += 0.2
        
        # Check parsing errors
        if not silver.has_parsing_errors:
            score += 0.2
        
        return round(score, 2)


def transform_to_silver(bronze_filing: dict, bronze_s3_path: str, 
                       cik_mapper: Optional[CIKTickerMapper] = None) -> SilverFiling:
    """
    Convenience function to transform a Bronze filing to Silver
    
    Args:
        bronze_filing: Dictionary with Bronze filing data
        bronze_s3_path: S3 path to the Bronze filing
        cik_mapper: Optional CIK to ticker mapper
        
    Returns:
        SilverFiling object
    """
    transformer = SilverTransformer(cik_mapper)
    return transformer.transform(bronze_filing, bronze_s3_path)
