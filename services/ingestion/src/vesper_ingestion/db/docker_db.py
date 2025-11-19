"""
Docker-based database operations for macOS compatibility

This module provides a workaround for macOS-specific connection issues
by executing SQL commands directly in the PostgreSQL container.
"""
import json
import subprocess
from datetime import datetime
from typing import Optional, List, Dict, Any

import structlog

logger = structlog.get_logger(__name__)


class DockerDBClient:
    """Database client that executes SQL through docker exec"""
    
    def __init__(self, container_name: str = "vesper-postgres", user: str = "vesper", database: str = "vesper"):
        self.container_name = container_name
        self.user = user
        self.database = database
    
    def _execute(self, sql: str, params: Optional[List] = None) -> Optional[str]:
        """Execute SQL command in container"""
        try:
            # For parameterized queries, we need to escape values properly
            if params:
                # Simple parameter substitution (for basic use cases)
                for param in params:
                    if isinstance(param, str):
                        param_escaped = param.replace("'", "''")
                        sql = sql.replace("?", f"'{param_escaped}'", 1)
                    elif isinstance(param, (int, float)):
                        sql = sql.replace("?", str(param), 1)
                    elif isinstance(param, datetime):
                        sql = sql.replace("?", f"'{param.isoformat()}'", 1)
                    elif isinstance(param, dict):
                        json_str = json.dumps(param).replace("'", "''")
                        sql = sql.replace("?", f"'{json_str}'::jsonb", 1)
                    elif param is None:
                        sql = sql.replace("?", "NULL", 1)
            
            cmd = [
                "docker", "exec", "-i", self.container_name,
                "psql", "-U", self.user, "-d", self.database,
                "-t",  # Tuples only
                "-A",  # Unaligned output
                "-c", sql
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            return result.stdout.strip() if result.stdout else None
            
        except subprocess.CalledProcessError as e:
            logger.error("sql_execution_failed", sql=sql[:100], error=e.stderr)
            raise RuntimeError(f"SQL execution failed: {e.stderr}")
    
    def insert_filing(
        self,
        cik: str,
        company_name: str,
        accession_number: str,
        form_type: str,
        filing_date: datetime,
        report_date: Optional[datetime],
        s3_key: str,
        document_url: str,
        file_size: Optional[int],
        content_length: Optional[int],
        filing_metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """Insert a filing record"""
        sql = """
        INSERT INTO bronze.filings (
            cik, company_name, accession_number, form_type,
            filing_date, report_date, s3_key, document_url,
            file_size, content_length, filing_metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (accession_number) DO NOTHING
        """
        
        try:
            # Convert datetime objects to ISO format strings in metadata
            if filing_metadata:
                metadata_copy = {}
                for key, value in filing_metadata.items():
                    if isinstance(value, datetime):
                        metadata_copy[key] = value.isoformat()
                    else:
                        metadata_copy[key] = value
                filing_metadata = metadata_copy
            
            self._execute(sql, [
                cik, company_name, accession_number, form_type,
                filing_date, report_date, s3_key, document_url,
                file_size, content_length, filing_metadata
            ])
            return True
        except Exception as e:
            logger.error("failed_to_insert_filing", accession_number=accession_number, error=str(e))
            return False
    
    def filing_exists(self, accession_number: str) -> bool:
        """Check if a filing already exists"""
        sql = "SELECT COUNT(*) FROM bronze.filings WHERE accession_number = ?"
        
        try:
            result = self._execute(sql, [accession_number])
            return int(result) > 0 if result else False
        except Exception:
            return False
    
    def create_job(
        self,
        source: str,
        cik_list: Optional[List[str]],
        form_types: Optional[List[str]],
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> Optional[int]:
        """Create an ingestion job record"""
        cik_str = ",".join(cik_list) if cik_list else None
        form_str = ",".join(form_types) if form_types else None
        
        sql = """
        INSERT INTO bronze.ingestion_jobs (
            source, cik_list, form_types, start_date, end_date, status
        ) VALUES (?, ?, ?, ?, ?, 'running')
        RETURNING id
        """
        
        try:
            result = self._execute(sql, [source, cik_str, form_str, start_date, end_date])
            if result:
                # Extract just the integer ID from the result
                # psql output might be "1\nINSERT 0 1" or just "1"
                lines = result.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and line.isdigit():
                        return int(line)
            return None
        except Exception as e:
            logger.error("failed_to_create_job", error=str(e))
            return None
    
    def complete_job(
        self,
        job_id: int,
        status: str,
        total_filings: int,
        successful_filings: int,
        failed_filings: int,
        error_message: Optional[str] = None
    ) -> bool:
        """Mark a job as complete"""
        sql = """
        UPDATE bronze.ingestion_jobs
        SET status = ?,
            completed_at = NOW(),
            duration_seconds = EXTRACT(EPOCH FROM (NOW() - created_at)),
            total_filings = ?,
            successful_filings = ?,
            failed_filings = ?,
            error_message = ?
        WHERE id = ?
        """
        
        try:
            self._execute(sql, [
                status, total_filings, successful_filings,
                failed_filings, error_message, job_id
            ])
            return True
        except Exception as e:
            logger.error("failed_to_complete_job", job_id=job_id, error=str(e))
            return False
    
    def get_recent_filings(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent filings"""
        sql = f"""
        SELECT cik, company_name, form_type, filing_date, accession_number
        FROM bronze.filings
        ORDER BY filing_date DESC
        LIMIT {limit}
        """
        
        try:
            result = self._execute(sql)
            if not result:
                return []
            
            filings = []
            for line in result.split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        filings.append({
                            'cik': parts[0],
                            'company_name': parts[1],
                            'form_type': parts[2],
                            'filing_date': parts[3],
                            'accession_number': parts[4]
                        })
            return filings
        except Exception as e:
            logger.error("failed_to_get_recent_filings", error=str(e))
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            # Total filings
            total = self._execute("SELECT COUNT(*) FROM bronze.filings")
            
            # Filings by form type
            form_counts = self._execute("""
                SELECT form_type, COUNT(*) 
                FROM bronze.filings 
                GROUP BY form_type
                ORDER BY COUNT(*) DESC
            """)
            
            # Recent jobs
            job_count = self._execute("SELECT COUNT(*) FROM bronze.ingestion_jobs")
            
            stats = {
                'total_filings': int(total) if total else 0,
                'total_jobs': int(job_count) if job_count else 0,
                'filings_by_form': {}
            }
            
            if form_counts:
                for line in form_counts.split('\n'):
                    if line and '|' in line:
                        form_type, count = line.split('|')
                        stats['filings_by_form'][form_type] = int(count)
            
            return stats
        except Exception as e:
            logger.error("failed_to_get_stats", error=str(e))
            return {}
