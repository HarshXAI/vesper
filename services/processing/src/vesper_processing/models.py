"""
Data models for document processing
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class DocumentType(str, Enum):
    """Document type enumeration"""
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    FORM_20F = "20-F"
    OTHER = "OTHER"


class SectionType(str, Enum):
    """SEC filing section types"""
    ITEM_1 = "Item 1"  # Business
    ITEM_1A = "Item 1A"  # Risk Factors
    ITEM_1B = "Item 1B"  # Unresolved Staff Comments
    ITEM_2 = "Item 2"  # Properties
    ITEM_3 = "Item 3"  # Legal Proceedings
    ITEM_4 = "Item 4"  # Mine Safety Disclosures
    ITEM_5 = "Item 5"  # Market for Registrant's Common Equity
    ITEM_6 = "Item 6"  # Selected Financial Data
    ITEM_7 = "Item 7"  # MD&A
    ITEM_7A = "Item 7A"  # Quantitative and Qualitative Disclosures
    ITEM_8 = "Item 8"  # Financial Statements
    ITEM_9 = "Item 9"  # Changes in and Disagreements
    ITEM_9A = "Item 9A"  # Controls and Procedures
    ITEM_9B = "Item 9B"  # Other Information
    ITEM_10 = "Item 10"  # Directors and Officers
    ITEM_11 = "Item 11"  # Executive Compensation
    ITEM_12 = "Item 12"  # Security Ownership
    ITEM_13 = "Item 13"  # Certain Relationships
    ITEM_14 = "Item 14"  # Principal Accountant Fees
    ITEM_15 = "Item 15"  # Exhibits
    OTHER = "Other"


class ProcessedSection(BaseModel):
    """Processed document section"""
    section_type: SectionType
    title: str
    content: str
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class TableType(str, Enum):
    """Types of financial tables"""
    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    CASH_FLOW = "cash_flow"
    SHAREHOLDERS_EQUITY = "shareholders_equity"
    SEGMENT_REPORTING = "segment_reporting"
    REVENUE_BREAKDOWN = "revenue_breakdown"
    STOCK_COMPENSATION = "stock_compensation"
    DEBT_SCHEDULE = "debt_schedule"
    LEASE_OBLIGATIONS = "lease_obligations"
    OTHER = "other"


class ProcessedTable(BaseModel):
    """Processed HTML table"""
    table_id: str
    caption: Optional[str] = None
    headers: List[str]  # Flattened headers for backward compatibility
    header_rows: Optional[List[List[str]]] = None  # Multi-level headers if detected
    rows: List[List[str]]
    section: Optional[str] = None
    position: int
    table_type: Optional[str] = None  # TableType classification
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProcessedDocument(BaseModel):
    """Fully processed document"""
    filing_id: str  # accession_number
    cik: str
    company_name: str
    form_type: DocumentType
    filing_date: datetime
    
    # Raw content
    html_content: Optional[str] = None
    
    # Processed content
    clean_text: str
    sections: List[ProcessedSection] = Field(default_factory=list)
    tables: List[ProcessedTable] = Field(default_factory=list)
    
    # Metadata
    word_count: int = 0
    character_count: int = 0
    table_count: int = 0
    section_count: int = 0
    
    # Processing info
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    processing_version: str = "0.1.0"
    
    # Storage
    s3_key: Optional[str] = None
    
    class Config:
        use_enum_values = True


class DocumentChunk(BaseModel):
    """Document chunk for embedding"""
    chunk_id: str
    filing_id: str
    section: Optional[str] = None
    content: str
    chunk_index: int
    total_chunks: int
    
    # Position in original document
    start_char: int
    end_char: int
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Relationships
    previous_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None
