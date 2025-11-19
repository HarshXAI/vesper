"""
SQLAlchemy database models for filing metadata

Stores metadata about ingested filings for tracking and querying.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, Text, JSON, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


class FilingRecord(Base):
    """
    Database record for SEC filing metadata
    
    Tracks which filings have been ingested and where they are stored.
    """
    __tablename__ = "filings"
    __table_args__ = (
        Index('idx_filings_cik', 'cik'),
        Index('idx_filings_form_type', 'form_type'),
        Index('idx_filings_filing_date', 'filing_date'),
        Index('idx_filings_accession', 'accession_number', unique=True),
        {'schema': 'bronze'}
    )
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Filing identifiers
    cik: Mapped[str] = mapped_column(String(10), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    form_type: Mapped[str] = mapped_column(String(10), nullable=False)
    
    # Filing dates
    filing_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    report_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Storage location
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    document_url: Mapped[str] = mapped_column(Text, nullable=False)
    
    # File metadata
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Additional metadata as JSON
    filing_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return (
            f"<FilingRecord(id={self.id}, cik={self.cik}, "
            f"form={self.form_type}, accession={self.accession_number})>"
        )


class IngestionJobRecord(Base):
    """
    Database record for ingestion job runs
    
    Tracks ingestion job execution for monitoring and debugging.
    """
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        Index('idx_jobs_status', 'status'),
        Index('idx_jobs_created', 'created_at'),
        {'schema': 'bronze'}
    )
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Job configuration
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 'sec-edgar'
    cik_list: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    form_types: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    max_per_cik: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Job results
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='running'
    )  # running, completed, failed
    total_filings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    def __repr__(self) -> str:
        return (
            f"<IngestionJobRecord(id={self.id}, source={self.source}, "
            f"status={self.status}, total={self.total_filings})>"
        )
