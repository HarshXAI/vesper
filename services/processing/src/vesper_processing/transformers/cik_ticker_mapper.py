"""
CIK to Ticker Mapping

Provides functionality to map SEC CIK numbers to stock ticker symbols.
"""

import json
from typing import Optional, Dict
from pathlib import Path


class CIKTickerMapper:
    """Maps CIK numbers to ticker symbols and company metadata"""
    
    # Default mapping for common companies (can be loaded from file/database)
    DEFAULT_MAPPINGS = {
        '0000320193': {'ticker': 'AAPL', 'name': 'Apple Inc.', 'exchange': 'NASDAQ', 'sector': 'Information Technology'},
        '0001018724': {'ticker': 'AMZN', 'name': 'Amazon.com Inc.', 'exchange': 'NASDAQ', 'sector': 'Consumer Discretionary'},
        '0001652044': {'ticker': 'GOOGL', 'name': 'Alphabet Inc.', 'exchange': 'NASDAQ', 'sector': 'Communication Services'},
        '0001326801': {'ticker': 'META', 'name': 'Meta Platforms Inc.', 'exchange': 'NASDAQ', 'sector': 'Communication Services'},
        '0000789019': {'ticker': 'MSFT', 'name': 'Microsoft Corporation', 'exchange': 'NASDAQ', 'sector': 'Information Technology'},
        '0001318605': {'ticker': 'TSLA', 'name': 'Tesla Inc.', 'exchange': 'NASDAQ', 'sector': 'Consumer Discretionary'},
        '0001067983': {'ticker': 'BRK.B', 'name': 'Berkshire Hathaway Inc.', 'exchange': 'NYSE', 'sector': 'Financials'},
        '0000019617': {'ticker': 'JPM', 'name': 'JPMorgan Chase & Co.', 'exchange': 'NYSE', 'sector': 'Financials'},
        '0001403161': {'ticker': 'UNH', 'name': 'UnitedHealth Group Inc.', 'exchange': 'NYSE', 'sector': 'Health Care'},
        '0000078003': {'ticker': 'PFE', 'name': 'Pfizer Inc.', 'exchange': 'NYSE', 'sector': 'Health Care'},
        '0000066740': {'ticker': 'XOM', 'name': 'Exxon Mobil Corporation', 'exchange': 'NYSE', 'sector': 'Energy'},
        '0001408356': {'ticker': 'NFLX', 'name': 'Netflix Inc.', 'exchange': 'NASDAQ', 'sector': 'Communication Services'},
        '0000886158': {'ticker': 'NVDA', 'name': 'NVIDIA Corporation', 'exchange': 'NASDAQ', 'sector': 'Information Technology'},
        '0001045810': {'ticker': 'NVDA', 'name': 'NVIDIA Corporation', 'exchange': 'NASDAQ', 'sector': 'Information Technology'},
        '0000051143': {'ticker': 'IBM', 'name': 'International Business Machines Corporation', 'exchange': 'NYSE', 'sector': 'Information Technology'},
    }
    
    def __init__(self, mapping_file: Optional[Path] = None):
        """
        Initialize the CIK ticker mapper
        
        Args:
            mapping_file: Optional path to JSON file with CIK mappings
        """
        self.mappings: Dict[str, dict] = self.DEFAULT_MAPPINGS.copy()
        
        if mapping_file and mapping_file.exists():
            self.load_mappings(mapping_file)
    
    def get_ticker(self, cik: str) -> Optional[str]:
        """
        Get ticker symbol for a CIK
        
        Args:
            cik: Central Index Key (10 digits, zero-padded)
            
        Returns:
            Ticker symbol or None if not found
            
        Example:
            >>> mapper = CIKTickerMapper()
            >>> mapper.get_ticker('0000320193')
            'AAPL'
        """
        # Normalize CIK to 10 digits
        cik_normalized = str(cik).zfill(10)
        
        mapping = self.mappings.get(cik_normalized)
        return mapping['ticker'] if mapping else None
    
    def get_company_name(self, cik: str) -> Optional[str]:
        """
        Get company name for a CIK
        
        Args:
            cik: Central Index Key
            
        Returns:
            Company name or None if not found
        """
        cik_normalized = str(cik).zfill(10)
        mapping = self.mappings.get(cik_normalized)
        return mapping['name'] if mapping else None
    
    def get_metadata(self, cik: str) -> Optional[dict]:
        """
        Get all metadata for a CIK
        
        Args:
            cik: Central Index Key
            
        Returns:
            Dictionary with ticker, name, exchange, sector or None
            
        Example:
            >>> mapper = CIKTickerMapper()
            >>> meta = mapper.get_metadata('0000320193')
            >>> assert meta['ticker'] == 'AAPL'
            >>> assert meta['sector'] == 'Information Technology'
        """
        cik_normalized = str(cik).zfill(10)
        return self.mappings.get(cik_normalized)
    
    def add_mapping(self, cik: str, ticker: str, name: str, 
                   exchange: Optional[str] = None, 
                   sector: Optional[str] = None):
        """
        Add or update a CIK mapping
        
        Args:
            cik: Central Index Key
            ticker: Stock ticker symbol
            name: Company name
            exchange: Stock exchange (NASDAQ, NYSE, etc.)
            sector: Industry sector
        """
        cik_normalized = str(cik).zfill(10)
        self.mappings[cik_normalized] = {
            'ticker': ticker,
            'name': name,
            'exchange': exchange,
            'sector': sector,
        }
    
    def load_mappings(self, mapping_file: Path):
        """
        Load mappings from a JSON file
        
        Args:
            mapping_file: Path to JSON file
            
        JSON Format:
            {
                "0000320193": {
                    "ticker": "AAPL",
                    "name": "Apple Inc.",
                    "exchange": "NASDAQ",
                    "sector": "Information Technology"
                },
                ...
            }
        """
        try:
            with open(mapping_file, 'r') as f:
                loaded_mappings = json.load(f)
                self.mappings.update(loaded_mappings)
        except Exception as e:
            print(f"Warning: Could not load mapping file {mapping_file}: {e}")
    
    def save_mappings(self, mapping_file: Path):
        """
        Save current mappings to a JSON file
        
        Args:
            mapping_file: Path to save JSON file
        """
        with open(mapping_file, 'w') as f:
            json.dump(self.mappings, f, indent=2)
    
    def get_all_tickers(self) -> list[str]:
        """Get list of all known ticker symbols"""
        return [m['ticker'] for m in self.mappings.values() if m.get('ticker')]
    
    def get_all_ciks(self) -> list[str]:
        """Get list of all known CIKs"""
        return list(self.mappings.keys())
    
    def __len__(self) -> int:
        """Return number of mappings"""
        return len(self.mappings)
    
    def __contains__(self, cik: str) -> bool:
        """Check if CIK is in mappings"""
        cik_normalized = str(cik).zfill(10)
        return cik_normalized in self.mappings
