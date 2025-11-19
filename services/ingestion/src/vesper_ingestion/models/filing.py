"""
Data models for the ingestion service
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class Filing(BaseModel):
    """
    Represents a financial filing document
    """
    cik: str = Field(..., description="Central Index Key")
    company_name: str = Field(..., description="Company name")
    form_type: str = Field(..., description="Form type (e.g., 10-K, 10-Q)")
    filing_date: datetime = Field(..., description="Filing date")
    accession_number: str = Field(..., description="Unique accession number")
    document_url: str = Field(..., description="URL to the document")
    
    # Optional fields
    report_date: Optional[datetime] = Field(None, description="Report period end date")
    file_number: Optional[str] = Field(None, description="File number")
    film_number: Optional[str] = Field(None, description="Film number")
    
    # Content
    html_content: Optional[str] = Field(None, description="Raw HTML content")
    text_content: Optional[str] = Field(None, description="Extracted text content")
    
    # File information
    file_size: Optional[int] = Field(None, description="Size of the file in bytes")
    content_length: Optional[int] = Field(None, description="Content length from HTTP response")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "cik": "0000320193",
                "company_name": "Apple Inc.",
                "form_type": "10-K",
                "filing_date": "2023-11-03T00:00:00",
                "accession_number": "0000320193-23-000106",
                "document_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
                "report_date": "2023-09-30T00:00:00",
            }
        }


class IngestionJob(BaseModel):
    """
    Represents an ingestion job configuration
    """
    job_id: str = Field(..., description="Unique job identifier")
    source: str = Field(..., description="Data source (e.g., sec-edgar)")
    cik: Optional[str] = Field(None, description="Company CIK")
    ciks: Optional[list[str]] = Field(None, description="List of company CIKs")
    form_type: str = Field(..., description="Form type to fetch")
    count: int = Field(default=10, description="Number of filings to fetch")
    start_date: Optional[datetime] = Field(None, description="Start date for filtering")
    end_date: Optional[datetime] = Field(None, description="End date for filtering")
    
    # Status tracking
    status: str = Field(default="pending", description="Job status")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Results
    filings_fetched: int = Field(default=0, description="Number of filings fetched")
    filings_stored: int = Field(default=0, description="Number of filings stored")
    errors: list[str] = Field(default_factory=list, description="Error messages")


class IngestionMetrics(BaseModel):
    """
    Metrics for monitoring ingestion operations
    """
    filings_fetched_total: int = 0
    filings_stored_total: int = 0
    errors_total: int = 0
    bytes_downloaded: int = 0
    bytes_uploaded: int = 0
    duration_seconds: float = 0.0
