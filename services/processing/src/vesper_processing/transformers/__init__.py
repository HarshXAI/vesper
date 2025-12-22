"""
VESPER Data Transformation Services

This package contains data transformation logic for converting Bronze layer
raw data into Silver layer normalized and enriched data.

Supports multiple domains via ENV DOMAIN=finance|healthcare
"""

import os

from .silver_transform import SilverTransformer, transform_to_silver
from .html_cleaner import HTMLCleaner, clean_html
from .cik_ticker_mapper import CIKTickerMapper
from .healthcare_connector import HealthcareConnector, get_domain_connector
from .healthcare_transformer import (
    HealthcareTransformer,
    DomainTransformer,
    get_entity_filter,
)

# Domain toggle
DOMAIN = os.getenv("DOMAIN", "finance")

__all__ = [
    # Core transformers
    'SilverTransformer',
    'transform_to_silver',
    'HTMLCleaner',
    'clean_html',
    'CIKTickerMapper',
    # Healthcare domain
    'HealthcareConnector',
    'HealthcareTransformer',
    # Domain utilities
    'DomainTransformer',
    'get_domain_connector',
    'get_entity_filter',
    'DOMAIN',
]
