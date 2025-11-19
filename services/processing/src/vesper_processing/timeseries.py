"""
Time series extraction and alignment for financial documents.

Extracts quarterly and annual periods from financial text,
aligns them to standard dates, and calculates growth rates.
"""

from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum
from typing import Optional
import re


class PeriodType(Enum):
    """Type of financial reporting period"""
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    SEMI_ANNUAL = "semi_annual"
    MONTHLY = "monthly"
    UNKNOWN = "unknown"


class FiscalYearEnd(Enum):
    """Common fiscal year end months"""
    JANUARY = 1
    FEBRUARY = 2
    MARCH = 3
    APRIL = 4
    MAY = 5
    JUNE = 6
    JULY = 7
    AUGUST = 8
    SEPTEMBER = 9
    OCTOBER = 10
    NOVEMBER = 11
    DECEMBER = 12


@dataclass
class TimePeriod:
    """
    Represents a financial reporting period.
    
    Attributes:
        period_type: Type of period (quarterly, annual, etc.)
        start_date: Period start date (YYYY-MM-DD)
        end_date: Period end date (YYYY-MM-DD)
        fiscal_year: Fiscal year (e.g., 2023)
        fiscal_quarter: Fiscal quarter (1-4) if applicable
        calendar_year: Calendar year (e.g., 2023)
        calendar_quarter: Calendar quarter (1-4) if applicable
        label: Human-readable label (e.g., "Q3 2023", "FY 2023")
    """
    period_type: PeriodType
    start_date: date
    end_date: date
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    calendar_year: Optional[int] = None
    calendar_quarter: Optional[int] = None
    label: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'period_type': self.period_type.value,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'fiscal_year': self.fiscal_year,
            'fiscal_quarter': self.fiscal_quarter,
            'calendar_year': self.calendar_year,
            'calendar_quarter': self.calendar_quarter,
            'label': self.label,
        }
    
    def duration_days(self) -> int:
        """Calculate period duration in days"""
        return (self.end_date - self.start_date).days + 1


@dataclass
class TimeSeriesValue:
    """
    A financial metric value at a specific time period.
    
    Attributes:
        period: Time period for this value
        value: Numeric value
        metric_name: Name of the metric (e.g., "Revenue", "Net Income")
        unit: Unit of measurement (e.g., "USD", "millions")
    """
    period: TimePeriod
    value: float
    metric_name: str
    unit: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'period': self.period.to_dict(),
            'value': self.value,
            'metric_name': self.metric_name,
            'unit': self.unit,
        }


class TimeSeriesExtractor:
    """
    Extract and align time series data from financial documents.
    
    Supports:
    - Quarterly periods: Q1 2023, 1Q23, First Quarter 2023
    - Annual periods: FY 2023, Fiscal Year 2023, Year Ended Dec 31, 2023
    - Semi-annual periods: H1 2023, First Half 2023
    - Custom fiscal year ends
    - Growth rate calculations (YoY, QoQ)
    """
    
    # Regex patterns for period extraction
    QUARTER_PATTERNS = [
        # Q1 2023, Q1-2023, Q1'23
        r'\b([Qq])([1-4])[,\s\-\']*(\d{2,4})\b',
        # 1Q 2023, 1Q23
        r'\b([1-4])([Qq])[,\s\-\']*(\d{2,4})\b',
        # First Quarter 2023, Second Quarter 2023
        r'\b(First|Second|Third|Fourth)\s+Quarter\s+(\d{4})\b',
        # Three Months Ended March 31, 2023
        r'\bThree\s+Months\s+Ended\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b',
    ]
    
    ANNUAL_PATTERNS = [
        # FY 2023, FY2023, FY'23
        r'\b[Ff][Yy][,\s\-\']*(\d{2,4})\b',
        # Fiscal Year 2023
        r'\b[Ff]iscal\s+[Yy]ear\s+(\d{4})\b',
        # Year Ended December 31, 2023
        r'\b[Yy]ear\s+Ended\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b',
        # 12 Months Ended December 31, 2023
        r'\b12\s+Months?\s+Ended\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b',
    ]
    
    SEMI_ANNUAL_PATTERNS = [
        # H1 2023, H2 2023
        r'\b([Hh])([1-2])[,\s\-\']*(\d{2,4})\b',
        # First Half 2023, Second Half 2023
        r'\b(First|Second)\s+Half\s+(\d{4})\b',
        # Six Months Ended June 30, 2023
        r'\bSix\s+Months?\s+Ended\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b',
    ]
    
    # Month name mappings
    MONTH_NAMES = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12,
    }
    
    QUARTER_NAMES = {
        'first': 1,
        'second': 2,
        'third': 3,
        'fourth': 4,
    }
    
    HALF_NAMES = {
        'first': 1,
        'second': 2,
    }
    
    def __init__(self, fiscal_year_end: FiscalYearEnd = FiscalYearEnd.DECEMBER):
        """
        Initialize time series extractor.
        
        Args:
            fiscal_year_end: Month when fiscal year ends (default: December)
        """
        self.fiscal_year_end = fiscal_year_end
    
    def extract_periods(self, text: str) -> list[TimePeriod]:
        """
        Extract all time periods from text.
        
        Args:
            text: Text to extract periods from
            
        Returns:
            List of TimePeriod objects
        """
        periods = []
        
        # Extract quarterly periods
        for pattern in self.QUARTER_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                period = self._parse_quarter_match(match)
                if period:
                    periods.append(period)
        
        # Extract annual periods
        for pattern in self.ANNUAL_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                period = self._parse_annual_match(match)
                if period:
                    periods.append(period)
        
        # Extract semi-annual periods
        for pattern in self.SEMI_ANNUAL_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                period = self._parse_semi_annual_match(match)
                if period:
                    periods.append(period)
        
        # Remove duplicates (keep first occurrence)
        seen = set()
        unique_periods = []
        for period in periods:
            key = (period.start_date, period.end_date, period.period_type)
            if key not in seen:
                seen.add(key)
                unique_periods.append(period)
        
        return unique_periods
    
    def _parse_quarter_match(self, match: re.Match) -> Optional[TimePeriod]:
        """Parse a quarterly period match"""
        groups = match.groups()
        
        # Determine quarter number and year
        quarter = None
        year = None
        
        if len(groups) == 2:
            # Pattern: First Quarter 2023
            quarter_name = groups[0].lower()
            quarter = self.QUARTER_NAMES.get(quarter_name)
            year = int(groups[1])
        elif len(groups) == 3:
            # Check if it's Q1 2023 or 1Q 2023 format
            if groups[0].lower() == 'q' or groups[1].lower() == 'q':
                if groups[0].lower() == 'q':
                    quarter = int(groups[1])
                    year = self._normalize_year(groups[2])
                elif groups[1].lower() == 'q':
                    quarter = int(groups[0])
                    year = self._normalize_year(groups[2])
            else:
                # Pattern: Three Months Ended March 31, 2023
                month_name = groups[0].lower()
                month = self.MONTH_NAMES.get(month_name)
                year = int(groups[2])
                if month:
                    quarter = (month - 1) // 3 + 1
        
        if not quarter or not year:
            return None
        
        # Calculate start and end dates based on fiscal year end
        return self._create_fiscal_quarter_period(year, quarter)
    
    def _parse_annual_match(self, match: re.Match) -> Optional[TimePeriod]:
        """Parse an annual period match"""
        groups = match.groups()
        
        if len(groups) == 1:
            # Pattern: FY 2023 or Fiscal Year 2023
            year = self._normalize_year(groups[0])
        elif len(groups) == 3:
            # Pattern: Year Ended December 31, 2023
            year = int(groups[2])
        else:
            return None
        
        # Calculate fiscal year dates
        return self._create_fiscal_year_period(year)
    
    def _parse_semi_annual_match(self, match: re.Match) -> Optional[TimePeriod]:
        """Parse a semi-annual period match"""
        groups = match.groups()
        
        half = None
        year = None
        
        if len(groups) == 3:
            # Pattern: H1 2023
            half = int(groups[1])
            year = self._normalize_year(groups[2])
        elif len(groups) == 2:
            # Pattern: First Half 2023
            half_name = groups[0].lower()
            half = self.HALF_NAMES.get(half_name)
            year = int(groups[1])
        elif len(groups) >= 3:
            # Pattern: Six Months Ended June 30, 2023
            month_name = groups[0].lower()
            month = self.MONTH_NAMES.get(month_name)
            year = int(groups[2])
            if month:
                half = 1 if month <= 6 else 2
        
        if not half or not year:
            return None
        
        return self._create_fiscal_half_period(year, half)
    
    def _create_fiscal_quarter_period(self, fiscal_year: int, quarter: int) -> TimePeriod:
        """Create a fiscal quarter period"""
        # Calculate quarter start month based on fiscal year end
        fy_end_month = self.fiscal_year_end.value
        
        # Quarter 1 starts in month: (fy_end_month + 1) % 12 or 12
        q1_start_month = (fy_end_month % 12) + 1
        
        # Calculate this quarter's start month
        quarter_start_month = ((q1_start_month + (quarter - 1) * 3 - 1) % 12) + 1
        
        # Determine calendar year for this quarter
        if quarter_start_month > fy_end_month:
            # Quarter starts before fiscal year end
            calendar_year = fiscal_year - 1
        else:
            calendar_year = fiscal_year
        
        # Calculate start and end dates
        start_date = date(calendar_year, quarter_start_month, 1)
        
        # End date is last day of third month
        end_month = ((quarter_start_month + 2 - 1) % 12) + 1
        end_year = calendar_year if end_month >= quarter_start_month else calendar_year + 1
        
        # Get last day of end month
        if end_month == 12:
            end_date = date(end_year, 12, 31)
        else:
            next_month_start = date(end_year + (1 if end_month == 12 else 0), 
                                   (end_month % 12) + 1, 1)
            end_date = date(next_month_start.year, next_month_start.month - 1, 
                          self._last_day_of_month(next_month_start.year, next_month_start.month - 1))
        
        # Calculate calendar quarter
        calendar_quarter = (start_date.month - 1) // 3 + 1
        
        return TimePeriod(
            period_type=PeriodType.QUARTERLY,
            start_date=start_date,
            end_date=end_date,
            fiscal_year=fiscal_year,
            fiscal_quarter=quarter,
            calendar_year=start_date.year,
            calendar_quarter=calendar_quarter,
            label=f"Q{quarter} {fiscal_year}"
        )
    
    def _create_fiscal_year_period(self, fiscal_year: int) -> TimePeriod:
        """Create a fiscal year period"""
        fy_end_month = self.fiscal_year_end.value
        
        # Fiscal year starts in month after end month
        start_month = (fy_end_month % 12) + 1
        
        # If fiscal year ends in December, it's a calendar year
        if fy_end_month == 12:
            start_date = date(fiscal_year, 1, 1)
            end_date = date(fiscal_year, 12, 31)
        else:
            # Fiscal year spans two calendar years
            start_date = date(fiscal_year - 1, start_month, 1)
            end_date = date(fiscal_year, fy_end_month, 
                          self._last_day_of_month(fiscal_year, fy_end_month))
        
        return TimePeriod(
            period_type=PeriodType.ANNUAL,
            start_date=start_date,
            end_date=end_date,
            fiscal_year=fiscal_year,
            fiscal_quarter=None,
            calendar_year=end_date.year,
            calendar_quarter=None,
            label=f"FY {fiscal_year}"
        )
    
    def _create_fiscal_half_period(self, fiscal_year: int, half: int) -> TimePeriod:
        """Create a semi-annual period"""
        fy_end_month = self.fiscal_year_end.value
        start_month = (fy_end_month % 12) + 1
        
        if half == 1:
            # First half
            h_start_month = start_month
            h_end_month = (start_month + 5) % 12 if (start_month + 5) % 12 != 0 else 12
        else:
            # Second half
            h_start_month = (start_month + 6 - 1) % 12 + 1
            h_end_month = fy_end_month
        
        # Determine calendar years
        if h_start_month > fy_end_month:
            start_year = fiscal_year - 1
        else:
            start_year = fiscal_year
        
        if h_end_month > fy_end_month or (half == 2 and fy_end_month != 12):
            end_year = fiscal_year
        else:
            end_year = start_year if h_end_month >= h_start_month else start_year + 1
        
        start_date = date(start_year, h_start_month, 1)
        end_date = date(end_year, h_end_month, 
                       self._last_day_of_month(end_year, h_end_month))
        
        return TimePeriod(
            period_type=PeriodType.SEMI_ANNUAL,
            start_date=start_date,
            end_date=end_date,
            fiscal_year=fiscal_year,
            fiscal_quarter=None,
            calendar_year=end_date.year,
            calendar_quarter=None,
            label=f"H{half} {fiscal_year}"
        )
    
    def _normalize_year(self, year_str: str) -> int:
        """Normalize 2-digit or 4-digit year to 4-digit"""
        year = int(year_str)
        if year < 100:
            # Assume 2000s for 00-50, 1900s for 51-99
            year = 2000 + year if year <= 50 else 1900 + year
        return year
    
    def _last_day_of_month(self, year: int, month: int) -> int:
        """Get the last day of a month"""
        if month == 2:
            # Check for leap year
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                return 29
            return 28
        elif month in [4, 6, 9, 11]:
            return 30
        else:
            return 31
    
    def calculate_yoy_growth(self, current: TimeSeriesValue, previous: TimeSeriesValue) -> Optional[float]:
        """
        Calculate year-over-year growth rate.
        
        Args:
            current: Current period value
            previous: Previous year same period value
            
        Returns:
            Growth rate as decimal (e.g., 0.15 for 15% growth), or None if invalid
        """
        if previous.value == 0:
            return None
        
        # Verify periods are one year apart
        years_diff = current.period.fiscal_year - previous.period.fiscal_year
        if years_diff != 1:
            return None
        
        # Verify same period type
        if current.period.period_type != previous.period.period_type:
            return None
        
        # For quarterly, verify same quarter
        if current.period.period_type == PeriodType.QUARTERLY:
            if current.period.fiscal_quarter != previous.period.fiscal_quarter:
                return None
        
        growth = (current.value - previous.value) / previous.value
        return growth
    
    def calculate_qoq_growth(self, current: TimeSeriesValue, previous: TimeSeriesValue) -> Optional[float]:
        """
        Calculate quarter-over-quarter growth rate.
        
        Args:
            current: Current quarter value
            previous: Previous quarter value
            
        Returns:
            Growth rate as decimal (e.g., 0.10 for 10% growth), or None if invalid
        """
        if previous.value == 0:
            return None
        
        # Verify both are quarterly
        if (current.period.period_type != PeriodType.QUARTERLY or 
            previous.period.period_type != PeriodType.QUARTERLY):
            return None
        
        # Verify sequential quarters
        if current.period.fiscal_year == previous.period.fiscal_year:
            quarter_diff = current.period.fiscal_quarter - previous.period.fiscal_quarter
            if quarter_diff != 1:
                return None
        elif current.period.fiscal_year == previous.period.fiscal_year + 1:
            if current.period.fiscal_quarter != 1 or previous.period.fiscal_quarter != 4:
                return None
        else:
            return None
        
        growth = (current.value - previous.value) / previous.value
        return growth
    
    def align_to_calendar_quarter(self, fiscal_period: TimePeriod) -> TimePeriod:
        """
        Align a fiscal period to the nearest calendar quarter.
        
        Args:
            fiscal_period: Fiscal period to align
            
        Returns:
            Calendar quarter period
        """
        if fiscal_period.period_type != PeriodType.QUARTERLY:
            raise ValueError("Can only align quarterly periods")
        
        # Determine calendar quarter from start date
        calendar_quarter = (fiscal_period.start_date.month - 1) // 3 + 1
        calendar_year = fiscal_period.start_date.year
        
        # Calculate calendar quarter dates
        start_month = (calendar_quarter - 1) * 3 + 1
        start_date = date(calendar_year, start_month, 1)
        
        end_month = start_month + 2
        end_date = date(calendar_year, end_month, 
                       self._last_day_of_month(calendar_year, end_month))
        
        return TimePeriod(
            period_type=PeriodType.QUARTERLY,
            start_date=start_date,
            end_date=end_date,
            fiscal_year=fiscal_period.fiscal_year,
            fiscal_quarter=fiscal_period.fiscal_quarter,
            calendar_year=calendar_year,
            calendar_quarter=calendar_quarter,
            label=f"CQ{calendar_quarter} {calendar_year}"
        )
