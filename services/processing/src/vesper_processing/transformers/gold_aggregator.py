"""
Gold Layer Aggregation Service

Extracts KPIs from Silver layer tables and creates Gold layer fact tables.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class GoldKPI:
    """Base class for Gold layer KPIs"""
    kpi_id: str
    ticker: str
    cik: str
    period: str
    period_end: str
    fiscal_year: int
    fiscal_quarter: Optional[int]
    currency: str = 'USD'
    units: str = 'millions'
    source_filing_id: str = ''
    source_table_id: str = ''
    extraction_confidence: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        timestamp = datetime.utcnow().isoformat() + 'Z'
        return {
            'kpi_id': self.kpi_id,
            'ticker': self.ticker,
            'cik': self.cik,
            'period': self.period,
            'period_end': self.period_end,
            'fiscal_year': self.fiscal_year,
            'fiscal_quarter': self.fiscal_quarter,
            'currency': self.currency,
            'units': self.units,
            'source_filing_id': self.source_filing_id,
            'source_table_id': self.source_table_id,
            'extraction_confidence': round(self.extraction_confidence, 2),
            'created_at': self.created_at or timestamp,
            'updated_at': self.updated_at or timestamp,
        }


@dataclass
class RevenueKPI(GoldKPI):
    """Revenue KPI metrics"""
    total_revenue: Optional[Decimal] = None
    product_revenue: Optional[Decimal] = None
    services_revenue: Optional[Decimal] = None
    revenue_yoy_growth: Optional[Decimal] = None
    revenue_qoq_growth: Optional[Decimal] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            'total_revenue': float(self.total_revenue) if self.total_revenue else None,
            'product_revenue': float(self.product_revenue) if self.product_revenue else None,
            'services_revenue': float(self.services_revenue) if self.services_revenue else None,
            'revenue_yoy_growth': float(self.revenue_yoy_growth) if self.revenue_yoy_growth else None,
            'revenue_qoq_growth': float(self.revenue_qoq_growth) if self.revenue_qoq_growth else None,
        })
        return d


@dataclass
class GrossMarginKPI(GoldKPI):
    """Gross margin KPI metrics"""
    gross_profit: Optional[Decimal] = None
    cost_of_revenue: Optional[Decimal] = None
    total_revenue: Optional[Decimal] = None
    gross_margin_pct: Optional[Decimal] = None
    gross_profit_yoy_growth: Optional[Decimal] = None
    margin_yoy_change: Optional[Decimal] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            'gross_profit': float(self.gross_profit) if self.gross_profit else None,
            'cost_of_revenue': float(self.cost_of_revenue) if self.cost_of_revenue else None,
            'total_revenue': float(self.total_revenue) if self.total_revenue else None,
            'gross_margin_pct': float(self.gross_margin_pct) if self.gross_margin_pct else None,
            'gross_profit_yoy_growth': float(self.gross_profit_yoy_growth) if self.gross_profit_yoy_growth else None,
            'margin_yoy_change': float(self.margin_yoy_change) if self.margin_yoy_change else None,
        })
        return d


class FinancialValueParser:
    """Parse financial values with units and currency normalization"""
    
    # Patterns for extracting numeric values
    VALUE_PATTERNS = [
        r'\$?\s*\(?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\)?',  # $1,234.56 or (1,234.56)
        r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)',               # 1,234.56
    ]
    
    # Unit multipliers to convert to millions
    UNIT_MULTIPLIERS = {
        'thousands': Decimal('0.001'),
        'thousand': Decimal('0.001'),
        'millions': Decimal('1'),
        'million': Decimal('1'),
        'billions': Decimal('1000'),
        'billion': Decimal('1000'),
    }
    
    @classmethod
    def parse_value(cls, value_str: str, units: str = 'millions') -> Optional[Decimal]:
        """
        Parse a financial value string and normalize to millions
        
        Args:
            value_str: String like "$383,285" or "(1,234)"
            units: Units like "thousands", "millions", "billions"
            
        Returns:
            Decimal value in millions, or None if parsing fails
            
        Examples:
            >>> parse_value("$383,285", "millions")
            Decimal('383285.00')
            >>> parse_value("(1,234)", "thousands")
            Decimal('-1.234')
        """
        if not value_str or value_str == '—' or value_str == '-':
            return None
        
        # Try to extract numeric value
        for pattern in cls.VALUE_PATTERNS:
            match = re.search(pattern, str(value_str).strip())
            if match:
                value_str_clean = match.group(1).replace(',', '')
                break
        else:
            logger.warning("could_not_parse_value", value_str=value_str)
            return None
        
        try:
            value = Decimal(value_str_clean)
            
            # Handle negative values (parentheses indicate negative)
            if '(' in str(value_str) and ')' in str(value_str):
                value = -value
            
            # Normalize to millions
            multiplier = cls.UNIT_MULTIPLIERS.get(units.lower(), Decimal('1'))
            normalized = value * multiplier
            
            return normalized
            
        except (InvalidOperation, ValueError) as e:
            logger.warning("failed_to_parse_value", value_str=value_str, error=str(e))
            return None
    
    @classmethod
    def detect_units(cls, text: str) -> str:
        """
        Detect units from caption/header text
        
        Args:
            text: Text like "in millions" or "(thousands)"
            
        Returns:
            Units string: "thousands", "millions", or "billions"
        """
        text_lower = text.lower()
        
        if 'thousand' in text_lower:
            return 'thousands'
        elif 'billion' in text_lower:
            return 'billions'
        else:
            return 'millions'  # Default assumption for SEC filings


class PeriodParser:
    """Parse period strings from financial tables"""
    
    @classmethod
    def parse_period(cls, period_str: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        """
        Parse a period string to extract fiscal year, quarter, and period type
        
        Args:
            period_str: String like "Three Months Ended September 30, 2023"
            
        Returns:
            Tuple of (fiscal_year, fiscal_quarter, period_type)
            
        Examples:
            >>> parse_period("Three Months Ended September 30, 2023")
            (2023, 3, "Q3 2023")
            >>> parse_period("Year Ended December 31, 2023")
            (2023, None, "FY 2023")
        """
        if not period_str:
            return None, None, None
        
        text = period_str.strip()
        
        # Extract year
        year_match = re.search(r'(20\d{2})', text)
        fiscal_year = int(year_match.group(1)) if year_match else None
        
        # Detect quarter
        fiscal_quarter = None
        period_type = None
        
        if 'three months' in text.lower():
            # Quarterly filing
            # Map month to quarter
            month_quarter_map = {
                'march': 1, 'mar': 1,
                'june': 2, 'jun': 2,
                'september': 3, 'sept': 3, 'sep': 3,
                'december': 4, 'dec': 4,
            }
            
            for month, quarter in month_quarter_map.items():
                if month in text.lower():
                    fiscal_quarter = quarter
                    period_type = f"Q{quarter} {fiscal_year}"
                    break
        
        elif 'year ended' in text.lower() or 'twelve months' in text.lower():
            # Annual filing
            period_type = f"FY {fiscal_year}"
        
        return fiscal_year, fiscal_quarter, period_type


class GrowthCalculator:
    """Calculate growth rates between periods"""
    
    @staticmethod
    def calculate_yoy_growth(current: Optional[Decimal], prior: Optional[Decimal]) -> Optional[Decimal]:
        """
        Calculate year-over-year growth rate
        
        Args:
            current: Current period value
            prior: Prior year same period value
            
        Returns:
            Growth rate as decimal (0.15 = 15% growth), or None
        """
        if current is None or prior is None or prior == 0:
            return None
        
        growth = (current - prior) / abs(prior)
        return growth.quantize(Decimal('0.0001'))
    
    @staticmethod
    def calculate_margin(numerator: Optional[Decimal], denominator: Optional[Decimal]) -> Optional[Decimal]:
        """
        Calculate a margin/ratio
        
        Args:
            numerator: Numerator value
            denominator: Denominator value
            
        Returns:
            Ratio as decimal, or None
        """
        if numerator is None or denominator is None or denominator == 0:
            return None
        
        margin = numerator / denominator
        return margin.quantize(Decimal('0.0001'))


class GoldAggregator:
    """Main Gold layer aggregator"""
    
    def __init__(self):
        self.value_parser = FinancialValueParser()
        self.period_parser = PeriodParser()
        self.growth_calc = GrowthCalculator()
    
    def aggregate(self, silver_filing: Dict[str, Any]) -> Dict[str, List[GoldKPI]]:
        """
        Aggregate a Silver filing into Gold KPIs
        
        Args:
            silver_filing: Dictionary with Silver filing data
            
        Returns:
            Dictionary mapping KPI type to list of KPI objects
            
        Example:
            >>> aggregator = GoldAggregator()
            >>> silver = {'filing_id': '...', 'tables': [...]}
            >>> gold_kpis = aggregator.aggregate(silver)
            >>> gold_kpis['revenue']  # List of RevenueKPI objects
        """
        result = {
            'revenue': [],
            'gross_margin': [],
            'operating_income': [],
            'eps': [],
            'free_cash_flow': [],
        }
        
        filing_id = silver_filing.get('filing_id')
        ticker = silver_filing.get('ticker')
        cik = silver_filing.get('cik')
        tables = silver_filing.get('tables', [])
        
        logger.info("aggregating_gold_kpis", filing_id=filing_id, table_count=len(tables))
        
        # Extract KPIs from tables
        for table in tables:
            table_type = table.get('table_type', '').lower()
            
            if 'income' in table_type:
                # Extract revenue and operating income KPIs
                revenue_kpi = self._extract_revenue(table, ticker, cik, filing_id)
                if revenue_kpi:
                    result['revenue'].append(revenue_kpi)
                
                margin_kpi = self._extract_gross_margin(table, ticker, cik, filing_id)
                if margin_kpi:
                    result['gross_margin'].append(margin_kpi)
            
            elif 'cash_flow' in table_type:
                # Extract cash flow KPIs
                pass  # TODO: Implement
            
            elif 'balance' in table_type:
                # Extract balance sheet KPIs if needed
                pass  # TODO: Implement
        
        logger.info("gold_kpis_extracted", 
                   revenue_count=len(result['revenue']),
                   margin_count=len(result['gross_margin']))
        
        return result
    
    def _extract_revenue(self, table: Dict, ticker: str, cik: str, filing_id: str) -> Optional[RevenueKPI]:
        """Extract revenue KPIs from an income statement table"""
        # Placeholder implementation
        # In real implementation, would parse table data JSON
        return None
    
    def _extract_gross_margin(self, table: Dict, ticker: str, cik: str, filing_id: str) -> Optional[GrossMarginKPI]:
        """Extract gross margin KPIs from an income statement table"""
        # Placeholder implementation
        return None
