"""
Repository pattern for database operations

Provides clean API for database interactions.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
import structlog

from vesper_ingestion.db.models import FilingRecord, IngestionJobRecord
from vesper_ingestion.models.filing import Filing

logger = structlog.get_logger()


class FilingRepository:
    """Repository for filing database operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(
        self,
        filing: Filing,
        s3_key: str,
        file_size: Optional[int] = None
    ) -> FilingRecord:
        """
        Create a new filing record
        
        Args:
            filing: Filing object with metadata
            s3_key: S3 storage key where filing is stored
            file_size: Size of the file in bytes
            
        Returns:
            Created FilingRecord
        """
        record = FilingRecord(
            cik=filing.cik,
            company_name=filing.company_name,
            accession_number=filing.accession_number,
            form_type=filing.form_type,
            filing_date=filing.filing_date,
            report_date=filing.report_date,
            s3_key=s3_key,
            document_url=filing.document_url,
            file_size=file_size,
            content_length=len(filing.html_content) if filing.html_content else None,
            metadata=filing.metadata
        )
        
        self.session.add(record)
        self.session.flush()  # Get the ID
        
        logger.info(
            "filing_record_created",
            id=record.id,
            cik=filing.cik,
            accession_number=filing.accession_number
        )
        
        return record
    
    def get_by_accession(self, accession_number: str) -> Optional[FilingRecord]:
        """
        Get filing by accession number
        
        Args:
            accession_number: Unique accession number
            
        Returns:
            FilingRecord if found, None otherwise
        """
        stmt = select(FilingRecord).where(
            FilingRecord.accession_number == accession_number
        )
        return self.session.scalar(stmt)
    
    def exists(self, accession_number: str) -> bool:
        """
        Check if filing exists
        
        Args:
            accession_number: Unique accession number
            
        Returns:
            True if exists, False otherwise
        """
        stmt = select(func.count()).select_from(FilingRecord).where(
            FilingRecord.accession_number == accession_number
        )
        count = self.session.scalar(stmt)
        return count > 0
    
    def get_by_cik(
        self,
        cik: str,
        form_type: Optional[str] = None,
        limit: int = 100
    ) -> List[FilingRecord]:
        """
        Get filings by CIK
        
        Args:
            cik: Central Index Key
            form_type: Optional form type filter
            limit: Maximum number of results
            
        Returns:
            List of FilingRecords
        """
        stmt = select(FilingRecord).where(FilingRecord.cik == cik)
        
        if form_type:
            stmt = stmt.where(FilingRecord.form_type == form_type)
        
        stmt = stmt.order_by(FilingRecord.filing_date.desc()).limit(limit)
        
        return list(self.session.scalars(stmt))
    
    def get_recent(
        self,
        limit: int = 100,
        form_type: Optional[str] = None
    ) -> List[FilingRecord]:
        """
        Get recent filings
        
        Args:
            limit: Maximum number of results
            form_type: Optional form type filter
            
        Returns:
            List of FilingRecords
        """
        stmt = select(FilingRecord)
        
        if form_type:
            stmt = stmt.where(FilingRecord.form_type == form_type)
        
        stmt = stmt.order_by(FilingRecord.created_at.desc()).limit(limit)
        
        return list(self.session.scalars(stmt))
    
    def count_by_form_type(self) -> dict:
        """
        Count filings by form type
        
        Returns:
            Dictionary mapping form_type to count
        """
        stmt = select(
            FilingRecord.form_type,
            func.count(FilingRecord.id)
        ).group_by(FilingRecord.form_type)
        
        results = self.session.execute(stmt).all()
        return {form_type: count for form_type, count in results}


class IngestionJobRepository:
    """Repository for ingestion job database operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(
        self,
        source: str,
        cik_list: Optional[List[str]] = None,
        form_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_per_cik: Optional[int] = None
    ) -> IngestionJobRecord:
        """
        Create a new ingestion job record
        
        Args:
            source: Data source (e.g., 'sec-edgar')
            cik_list: List of CIKs to fetch
            form_types: List of form types
            start_date: Start date filter
            end_date: End date filter
            max_per_cik: Maximum filings per CIK
            
        Returns:
            Created IngestionJobRecord
        """
        record = IngestionJobRecord(
            source=source,
            cik_list=cik_list,
            form_types=form_types,
            start_date=start_date,
            end_date=end_date,
            max_per_cik=max_per_cik,
            status='running'
        )
        
        self.session.add(record)
        self.session.flush()
        
        logger.info("ingestion_job_created", id=record.id, source=source)
        
        return record
    
    def update_progress(
        self,
        job_id: int,
        total: int,
        successful: int,
        failed: int
    ):
        """
        Update job progress
        
        Args:
            job_id: Job ID
            total: Total filings processed
            successful: Successfully ingested
            failed: Failed to ingest
        """
        job = self.session.get(IngestionJobRecord, job_id)
        if job:
            job.total_filings = total
            job.successful = successful
            job.failed = failed
            self.session.flush()
    
    def complete(
        self,
        job_id: int,
        status: str = 'completed',
        error_message: Optional[str] = None,
        error_details: Optional[dict] = None
    ):
        """
        Mark job as complete
        
        Args:
            job_id: Job ID
            status: Final status ('completed' or 'failed')
            error_message: Optional error message
            error_details: Optional error details
        """
        job = self.session.get(IngestionJobRecord, job_id)
        if job:
            job.status = status
            job.completed_at = datetime.utcnow()
            
            if job.created_at:
                duration = (job.completed_at - job.created_at).total_seconds()
                job.duration_seconds = duration
            
            if error_message:
                job.error_message = error_message
                job.error_details = error_details
            
            self.session.flush()
            
            logger.info(
                "ingestion_job_completed",
                id=job_id,
                status=status,
                total=job.total_filings,
                successful=job.successful,
                failed=job.failed,
                duration=job.duration_seconds
            )
    
    def get_recent_jobs(self, limit: int = 50) -> List[IngestionJobRecord]:
        """
        Get recent ingestion jobs
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of IngestionJobRecords
        """
        stmt = select(IngestionJobRecord).order_by(
            IngestionJobRecord.created_at.desc()
        ).limit(limit)
        
        return list(self.session.scalars(stmt))
