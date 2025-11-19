"""
SEC EDGAR API Connector

Fetches financial filings from the SEC EDGAR database.
Implements rate limiting and retry logic to comply with SEC guidelines.
"""
import time
from datetime import datetime
from typing import List, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog

from vesper_ingestion.connectors.base import BaseConnector
from vesper_ingestion.models.filing import Filing

logger = structlog.get_logger()


class SECEdgarConnector(BaseConnector):
    """
    Connector for SEC EDGAR API
    
    Reference: https://www.sec.gov/edgar/sec-api-documentation
    """
    
    BASE_URL = "https://data.sec.gov"
    SUBMISSIONS_URL = f"{BASE_URL}/submissions"
    
    def __init__(
        self,
        user_agent: str,
        rate_limit_delay: float = 0.1  # SEC requires 10 requests per second max
    ):
        """
        Initialize SEC EDGAR connector
        
        Args:
            user_agent: User agent string (required by SEC, should include email)
            rate_limit_delay: Delay between requests in seconds
        """
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "user_agent must include your name and email "
                "(e.g., 'Your Name your@email.com')"
            )
        
        self.user_agent = user_agent
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate"
        }
        
        logger.info("sec_edgar_connector_initialized", user_agent=user_agent)
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_request
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError))
    )
    def _make_request(self, url: str, params: Optional[dict] = None) -> requests.Response:
        """
        Make HTTP request with rate limiting and retries
        
        Args:
            url: URL to request
            params: Optional query parameters
            
        Returns:
            Response object
        """
        # Apply rate limiting
        self._rate_limit()
        
        response = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response
    
    def _get_company_filings(
        self,
        cik: str,
        form_types: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: int = 100
    ) -> list[dict]:
        """
        Get filings for a specific company
        
        Args:
            cik: Company CIK number (with or without leading zeros)
            form_types: List of form types to filter by (e.g., ['10-K', '10-Q'])
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            count: Maximum number of filings to retrieve
            
        Returns:
            List of filing metadata dictionaries
        """
        # Normalize CIK to 10 digits with leading zeros
        cik_padded = cik.zfill(10)
        
        # Build submissions API URL
        url = f"{self.BASE_URL}/submissions/CIK{cik_padded}.json"
        
        logger.info(
            "fetching_company_filings",
            cik=cik,
            form_types=form_types,
            start_date=start_date,
            end_date=end_date,
            count=count
        )
        
        try:
            response = self._make_request(url)
            data = response.json()
            
            # Extract company name
            company_name = data.get('name', 'Unknown')
            
            # Extract recent filings
            recent_filings = data.get('filings', {}).get('recent', {})
            
            if not recent_filings:
                logger.warning("no_filings_found", cik=cik)
                return []
            
            # Get filing arrays
            accession_numbers = recent_filings.get('accessionNumber', [])
            filing_dates = recent_filings.get('filingDate', [])
            forms = recent_filings.get('form', [])
            primary_documents = recent_filings.get('primaryDocument', [])
            
            # Combine into list of dicts
            filings = []
            for i in range(len(accession_numbers)):
                form_type = forms[i]
                filing_date = filing_dates[i]
                
                # Filter by form type
                if form_types and form_type not in form_types:
                    continue
                
                # Filter by date range
                if start_date and filing_date < start_date:
                    continue
                if end_date and filing_date > end_date:
                    continue
                
                filings.append({
                    'cik': cik,
                    'company_name': company_name,
                    'accession_number': accession_numbers[i],
                    'filing_date': filing_date,
                    'form_type': form_type,
                    'primary_document': primary_documents[i]
                })
                
                # Stop if we hit count limit
                if len(filings) >= count:
                    break
            
            logger.info("fetched_company_filings", cik=cik, count=len(filings))
            return filings
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning("company_not_found", cik=cik)
                return []
            logger.error("failed_to_fetch_filings", cik=cik, error=str(e))
            raise
    
    def _parse_filing(self, filing_metadata: dict) -> Filing:
        """
        Parse filing metadata and download document content
        
        Args:
            filing_metadata: Filing metadata dictionary
            
        Returns:
            Filing object with content
        """
        cik = filing_metadata['cik']
        company_name = filing_metadata['company_name']
        accession_number = filing_metadata['accession_number']
        primary_document = filing_metadata['primary_document']
        filing_date_str = filing_metadata['filing_date']
        
        # Convert filing date string to datetime
        filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")
        
        # Remove dashes from accession number for URL
        accession_clean = accession_number.replace('-', '')
        
        # Build document URL (note: documents are on www.sec.gov, not data.sec.gov)
        document_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/"
            f"{accession_clean}/{primary_document}"
        )
        
        logger.info(
            "downloading_filing_document",
            cik=cik,
            accession_number=accession_number,
            url=document_url
        )
        
        try:
            # Download document content
            response = self._make_request(document_url)
            html_content = response.text
            content_length = len(html_content)
            
            # Create Filing object
            filing = Filing(
                cik=cik,
                company_name=company_name,
                accession_number=accession_number,
                filing_date=filing_date,
                form_type=filing_metadata['form_type'],
                document_url=document_url,
                html_content=html_content,
                file_size=content_length,
                content_length=content_length
            )
            
            logger.info(
                "parsed_filing",
                cik=cik,
                accession_number=accession_number,
                content_length=content_length
            )
            
            return filing
            
        except Exception as e:
            logger.error(
                "failed_to_parse_filing",
                cik=cik,
                accession_number=accession_number,
                error=str(e)
            )
            raise
    
    def fetch_filings(
        self,
        cik_list: Optional[list[str]] = None,
        form_types: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_per_cik: int = 100
    ) -> list[Filing]:
        """
        Fetch filings from SEC EDGAR
        
        Args:
            cik_list: List of CIK numbers to fetch
            form_types: List of form types to fetch (e.g., ['10-K', '10-Q'])
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            max_per_cik: Maximum filings per CIK
            
        Returns:
            List of Filing objects with content
        """
        if not cik_list:
            raise ValueError("Must provide at least one CIK")
        
        logger.info(
            "fetching_filings",
            cik_count=len(cik_list),
            form_types=form_types,
            start_date=start_date,
            end_date=end_date,
            max_per_cik=max_per_cik
        )
        
        all_filings = []
        
        for cik in cik_list:
            try:
                # Get filing metadata for this CIK
                filing_metadata_list = self._get_company_filings(
                    cik=cik,
                    form_types=form_types,
                    start_date=start_date,
                    end_date=end_date,
                    count=max_per_cik
                )
                
                # Download and parse each filing
                for filing_metadata in filing_metadata_list:
                    try:
                        filing = self._parse_filing(filing_metadata)
                        all_filings.append(filing)
                    except Exception as e:
                        logger.error(
                            "failed_to_parse_individual_filing",
                            cik=cik,
                            accession_number=filing_metadata.get('accession_number'),
                            error=str(e)
                        )
                        # Continue with other filings
                        continue
                
            except Exception as e:
                logger.error("failed_to_fetch_cik_filings", cik=cik, error=str(e))
                # Continue with other CIKs
                continue
        
        logger.info("fetched_all_filings", total_count=len(all_filings))
        return all_filings
    
    def validate_connection(self) -> bool:
        """
        Validate connection to SEC EDGAR API
        
        Returns:
            True if connection is valid
        """
        try:
            # Try to fetch a known company (Apple Inc.)
            url = f"{self.BASE_URL}/submissions/CIK0000320193.json"
            response = self._make_request(url)
            
            if response.status_code == 200:
                logger.info("sec_edgar_connection_validated")
                return True
            
            return False
            
        except Exception as e:
            logger.error("sec_edgar_connection_failed", error=str(e))
            return False
