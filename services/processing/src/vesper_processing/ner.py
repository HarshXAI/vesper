"""
Named Entity Recognition (NER) Module for Financial Documents

This module provides entity extraction capabilities for financial documents,
identifying companies, people, dates, monetary values, percentages, and locations.
It uses spaCy's pre-trained models enhanced with custom financial patterns.

Features:
- Entity extraction: PERSON, ORG, DATE, MONEY, PERCENT, GPE, CARDINAL
- Entity linking: Company names → CIK/ticker mapping
- Financial value parsing: $1.5M, €500K, etc.
- Custom patterns for financial entities
- Batch processing for performance

Example:
    >>> from vesper_processing.ner import FinancialNER
    >>> 
    >>> ner = FinancialNER()
    >>> text = "Apple Inc. reported revenue of $383 billion in fiscal 2023."
    >>> entities = ner.extract_entities(text)
    >>> 
    >>> for entity in entities:
    ...     print(f"{entity.text}: {entity.label_} (confidence: {entity.confidence:.2f})")
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import spacy
from spacy.tokens import Span, Doc


class EntityType(str, Enum):
    """Types of entities that can be extracted"""
    PERSON = "PERSON"          # People, including fictional
    ORGANIZATION = "ORG"       # Companies, agencies, institutions
    DATE = "DATE"              # Absolute or relative dates or periods
    MONEY = "MONEY"            # Monetary values
    PERCENT = "PERCENT"        # Percentage values
    LOCATION = "GPE"           # Countries, cities, states
    CARDINAL = "CARDINAL"      # Numerals that do not fall under other types
    QUANTITY = "QUANTITY"      # Measurements like "100 shares"
    PRODUCT = "PRODUCT"        # Objects, vehicles, foods, etc.


@dataclass
class Entity:
    """
    Represents a named entity extracted from text.
    
    Attributes:
        text: The entity text
        label: Entity type (PERSON, ORG, etc.)
        start_char: Starting character position
        end_char: Ending character position
        confidence: Confidence score (0.0-1.0)
        metadata: Additional metadata (CIK, ticker, normalized value, etc.)
    """
    text: str
    label: EntityType
    start_char: int
    end_char: int
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'text': self.text,
            'label': self.label.value,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'confidence': self.confidence,
            'metadata': self.metadata
        }


class FinancialNER:
    """
    Financial Named Entity Recognition system.
    
    This class provides entity extraction optimized for financial documents,
    with support for company name linking, monetary value parsing, and
    financial-specific patterns.
    
    Args:
        model_name: spaCy model name (default: en_core_web_sm)
        enable_linking: Enable company name → CIK/ticker linking
        
    Example:
        >>> ner = FinancialNER()
        >>> entities = ner.extract_entities("Apple reported $100B revenue")
        >>> for entity in entities:
        ...     print(f"{entity.text}: {entity.label_}")
    """
    
    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        enable_linking: bool = True
    ):
        # Load spaCy model
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            # Fallback if model not found
            print(f"Warning: Model {model_name} not found, using blank English model")
            self.nlp = spacy.blank("en")
        
        self.enable_linking = enable_linking
        
        # Company name patterns (common tech/finance companies)
        self.company_patterns = {
            'apple': {'name': 'Apple Inc.', 'ticker': 'AAPL', 'cik': '0000320193'},
            'apple inc': {'name': 'Apple Inc.', 'ticker': 'AAPL', 'cik': '0000320193'},
            'microsoft': {'name': 'Microsoft Corporation', 'ticker': 'MSFT', 'cik': '0000789019'},
            'microsoft corp': {'name': 'Microsoft Corporation', 'ticker': 'MSFT', 'cik': '0000789019'},
            'amazon': {'name': 'Amazon.com, Inc.', 'ticker': 'AMZN', 'cik': '0001018724'},
            'amazon.com': {'name': 'Amazon.com, Inc.', 'ticker': 'AMZN', 'cik': '0001018724'},
            'alphabet': {'name': 'Alphabet Inc.', 'ticker': 'GOOGL', 'cik': '0001652044'},
            'google': {'name': 'Alphabet Inc.', 'ticker': 'GOOGL', 'cik': '0001652044'},
            'meta': {'name': 'Meta Platforms, Inc.', 'ticker': 'META', 'cik': '0001326801'},
            'facebook': {'name': 'Meta Platforms, Inc.', 'ticker': 'META', 'cik': '0001326801'},
            'tesla': {'name': 'Tesla, Inc.', 'ticker': 'TSLA', 'cik': '0001318605'},
            'nvidia': {'name': 'NVIDIA Corporation', 'ticker': 'NVDA', 'cik': '0001045810'},
            'jp morgan': {'name': 'JPMorgan Chase & Co.', 'ticker': 'JPM', 'cik': '0000019617'},
            'jpmorgan': {'name': 'JPMorgan Chase & Co.', 'ticker': 'JPM', 'cik': '0000019617'},
        }
        
        # Monetary value patterns
        self.money_pattern = re.compile(
            r'[\$€£¥]\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|trillion|M|B|T|K|thousand))?',
            re.IGNORECASE
        )
        
        # Percentage patterns
        self.percent_pattern = re.compile(
            r'\d+(?:\.\d+)?\s*%',
            re.IGNORECASE
        )
    
    def extract_entities(
        self,
        text: str,
        entity_types: Optional[List[EntityType]] = None
    ) -> List[Entity]:
        """
        Extract named entities from text.
        
        Args:
            text: Input text
            entity_types: Optional list of entity types to extract (default: all)
            
        Returns:
            List of Entity objects
        """
        if not text:
            return []
        
        # Process with spaCy
        doc = self.nlp(text)
        
        entities = []
        
        # Extract spaCy entities
        for ent in doc.ents:
            try:
                entity_type = EntityType(ent.label_)
            except ValueError:
                # Skip unsupported entity types
                continue
            
            # Filter by requested types
            if entity_types and entity_type not in entity_types:
                continue
            
            entity = Entity(
                text=ent.text,
                label=entity_type,
                start_char=ent.start_char,
                end_char=ent.end_char,
                confidence=1.0  # spaCy doesn't provide confidence by default
            )
            
            # Add company linking for ORG entities
            if entity_type == EntityType.ORGANIZATION and self.enable_linking:
                company_info = self._link_company(ent.text)
                if company_info:
                    entity.metadata.update(company_info)
            
            # Parse monetary values
            if entity_type == EntityType.MONEY:
                parsed_value = self._parse_money(ent.text)
                if parsed_value:
                    entity.metadata['value'] = parsed_value
            
            # Parse percentages
            if entity_type == EntityType.PERCENT:
                parsed_value = self._parse_percent(ent.text)
                if parsed_value is not None:
                    entity.metadata['value'] = parsed_value
            
            entities.append(entity)
        
        # Add custom financial patterns not caught by spaCy
        custom_entities = self._extract_custom_patterns(text, doc, entities)
        entities.extend(custom_entities)
        
        # Sort by start position
        entities.sort(key=lambda e: e.start_char)
        
        return entities
    
    def extract_entities_batch(
        self,
        texts: List[str],
        entity_types: Optional[List[EntityType]] = None
    ) -> List[List[Entity]]:
        """
        Extract entities from multiple texts in batch (faster).
        
        Args:
            texts: List of input texts
            entity_types: Optional list of entity types to extract
            
        Returns:
            List of entity lists, one per input text
        """
        # Process in batch with spaCy for better performance
        docs = list(self.nlp.pipe(texts))
        
        results = []
        for doc in docs:
            # Convert doc back to text and process
            entities = self.extract_entities(doc.text, entity_types)
            results.append(entities)
        
        return results
    
    def _link_company(self, company_name: str) -> Optional[Dict[str, str]]:
        """
        Link company name to ticker and CIK.
        
        Args:
            company_name: Company name text
            
        Returns:
            Dictionary with ticker and CIK, or None if not found
        """
        # Normalize company name
        normalized = company_name.lower().strip()
        
        # Remove common suffixes
        for suffix in [' inc.', ' inc', ' corp.', ' corp', ' corporation', ' ltd.', ' ltd', ' llc']:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        
        # Look up in patterns
        company_info = self.company_patterns.get(normalized)
        if company_info:
            return {
                'official_name': company_info['name'],
                'ticker': company_info['ticker'],
                'cik': company_info['cik']
            }
        
        return None
    
    def _parse_money(self, money_text: str) -> Optional[float]:
        """
        Parse monetary value to float (in base currency units).
        
        Args:
            money_text: Money string like "$1.5M" or "€500K"
            
        Returns:
            Parsed value in base units, or None if parsing fails
        """
        try:
            # Remove currency symbol
            text = re.sub(r'[\$€£¥,]', '', money_text).strip()
            
            # Check for multipliers
            multiplier = 1.0
            text_lower = text.lower()
            
            if 'trillion' in text_lower or text_lower.endswith('t'):
                multiplier = 1_000_000_000_000
                text = re.sub(r'(?:trillion|t)$', '', text_lower).strip()
            elif 'billion' in text_lower or text_lower.endswith('b'):
                multiplier = 1_000_000_000
                text = re.sub(r'(?:billion|b)$', '', text_lower).strip()
            elif 'million' in text_lower or text_lower.endswith('m'):
                multiplier = 1_000_000
                text = re.sub(r'(?:million|m)$', '', text_lower).strip()
            elif 'thousand' in text_lower or text_lower.endswith('k'):
                multiplier = 1_000
                text = re.sub(r'(?:thousand|k)$', '', text_lower).strip()
            
            # Parse base number
            value = float(text)
            return value * multiplier
        
        except (ValueError, AttributeError):
            return None
    
    def _parse_percent(self, percent_text: str) -> Optional[float]:
        """
        Parse percentage to float.
        
        Args:
            percent_text: Percentage string like "25.5%"
            
        Returns:
            Percentage as float (e.g., 25.5), or None if parsing fails
        """
        try:
            # Remove % and parse
            text = percent_text.replace('%', '').strip()
            return float(text)
        except ValueError:
            return None
    
    def _extract_custom_patterns(
        self,
        text: str,
        doc: Doc,
        existing_entities: List[Entity]
    ) -> List[Entity]:
        """
        Extract entities using custom regex patterns.
        
        Args:
            text: Original text
            doc: spaCy Doc object
            existing_entities: Already extracted entities (to avoid duplicates)
            
        Returns:
            List of additional entities
        """
        custom_entities = []
        existing_spans = [(e.start_char, e.end_char) for e in existing_entities]
        
        # Find money patterns not caught by spaCy
        for match in self.money_pattern.finditer(text):
            start, end = match.span()
            
            # Skip if overlaps with existing entity
            if any(start >= es and end <= ee for es, ee in existing_spans):
                continue
            
            money_text = match.group(0)
            parsed_value = self._parse_money(money_text)
            
            entity = Entity(
                text=money_text,
                label=EntityType.MONEY,
                start_char=start,
                end_char=end,
                confidence=0.95,  # Slightly lower confidence for regex
                metadata={'value': parsed_value} if parsed_value else {}
            )
            custom_entities.append(entity)
        
        # Find percentage patterns not caught by spaCy
        for match in self.percent_pattern.finditer(text):
            start, end = match.span()
            
            # Skip if overlaps with existing entity
            if any(start >= es and end <= ee for es, ee in existing_spans):
                continue
            
            percent_text = match.group(0)
            parsed_value = self._parse_percent(percent_text)
            
            entity = Entity(
                text=percent_text,
                label=EntityType.PERCENT,
                start_char=start,
                end_char=end,
                confidence=0.95,
                metadata={'value': parsed_value} if parsed_value is not None else {}
            )
            custom_entities.append(entity)
        
        return custom_entities
    
    def get_entity_counts(self, entities: List[Entity]) -> Dict[str, int]:
        """
        Count entities by type.
        
        Args:
            entities: List of entities
            
        Returns:
            Dictionary mapping entity type to count
        """
        counts = {}
        for entity in entities:
            label = entity.label.value
            counts[label] = counts.get(label, 0) + 1
        return counts
    
    def filter_by_type(
        self,
        entities: List[Entity],
        entity_type: EntityType
    ) -> List[Entity]:
        """
        Filter entities by type.
        
        Args:
            entities: List of entities
            entity_type: Entity type to filter by
            
        Returns:
            Filtered list of entities
        """
        return [e for e in entities if e.label == entity_type]
    
    def filter_by_confidence(
        self,
        entities: List[Entity],
        min_confidence: float = 0.5
    ) -> List[Entity]:
        """
        Filter entities by minimum confidence.
        
        Args:
            entities: List of entities
            min_confidence: Minimum confidence threshold
            
        Returns:
            Filtered list of entities
        """
        return [e for e in entities if e.confidence >= min_confidence]
