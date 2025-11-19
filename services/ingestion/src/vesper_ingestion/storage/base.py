"""
Base storage interface
"""
from abc import ABC, abstractmethod
from vesper_ingestion.models.filing import Filing


class BaseStorage(ABC):
    """
    Abstract base class for storage backends
    """
    
    @abstractmethod
    def upload_filing(self, filing: Filing, prefix: str = "") -> str:
        """
        Upload a filing to storage
        
        Args:
            filing: Filing object with content
            prefix: Optional prefix for the storage path
            
        Returns:
            Storage path/key of the uploaded filing
        """
        pass
    
    @abstractmethod
    def download_filing(self, key: str) -> Filing:
        """
        Download a filing from storage
        
        Args:
            key: Storage path/key
            
        Returns:
            Filing object with content
        """
        pass
    
    @abstractmethod
    def filing_exists(self, key: str) -> bool:
        """
        Check if a filing exists in storage
        
        Args:
            key: Storage path/key
            
        Returns:
            True if filing exists
        """
        pass
    
    @abstractmethod
    def list_filings(self, prefix: str = "") -> list[str]:
        """
        List all filings in storage
        
        Args:
            prefix: Optional prefix to filter by
            
        Returns:
            List of storage keys
        """
        pass
