"""
Base connector interface
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from vesper_ingestion.models.filing import Filing


class BaseConnector(ABC):
    """
    Abstract base class for data connectors
    """
    
    @abstractmethod
    def fetch_filings(
        self,
        cik_list: Optional[List[str]] = None,
        form_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_per_cik: int = 100
    ) -> List[Filing]:
        """
        Fetch filings from the data source
        
        Args:
            cik_list: List of CIK numbers to fetch
            form_types: List of form types to fetch (e.g., ['10-K', '10-Q'])
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            max_per_cik: Maximum filings per CIK
            
        Returns:
            List of Filing objects with content
        """
        pass
    
    @abstractmethod
    def validate_connection(self) -> bool:
        """
        Validate that the connector can reach the data source
        
        Returns:
            True if connection is valid
        """
        pass
