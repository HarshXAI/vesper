"""
Healthcare Domain Transformer

Transforms healthcare documents through the medallion architecture (Bronze → Silver → Gold).
Toggle via ENV: DOMAIN=healthcare

Adjusts NER entity filters for healthcare-specific extraction.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Domain toggle
DOMAIN = os.getenv("DOMAIN", "finance")


# Healthcare-specific NER patterns
HEALTHCARE_NER_PATTERNS = {
    # Clinical entities
    "DIAGNOSIS": r"\b(?:diagnosis|diagnosed with|condition|disease|disorder|syndrome)\b",
    "PROCEDURE": r"\b(?:surgery|procedure|treatment|therapy|intervention)\b",
    "MEDICATION": r"\b(?:medication|drug|prescription|dosage|pharmaceutical)\b",
    
    # Operational entities
    "DEPARTMENT": r"\b(?:Emergency|ER|ICU|NICU|PICU|CCU|OR|PACU|L&D|Med-Surg|Oncology|Cardiology|Orthopedics|Pediatrics|Radiology|Pharmacy|Lab)\b",
    "STAFF_ROLE": r"\b(?:physician|nurse|RN|LPN|NP|PA|technician|therapist|aide|administrator)\b",
    "FACILITY_TYPE": r"\b(?:hospital|clinic|medical center|health system|urgent care|ambulatory|outpatient|inpatient)\b",
    
    # Quality metrics
    "QUALITY_METRIC": r"\b(?:readmission rate|mortality rate|infection rate|patient satisfaction|HCAHPS|Core Measures|quality score)\b",
    "COMPLIANCE_STANDARD": r"\b(?:HIPAA|CMS|Joint Commission|OSHA|FDA|state regulations|accreditation|certification)\b",
    
    # Numeric patterns
    "RATE_VALUE": r"\b\d+(?:\.\d+)?%\b",
    "TIME_VALUE": r"\b\d+(?:\.\d+)?\s*(?:minutes?|hours?|days?|weeks?|months?)\b",
    "COUNT_VALUE": r"\b\d{1,3}(?:,\d{3})*\s*(?:patients?|visits?|admissions?|discharges?|beds?)\b",
}

# Finance-specific NER patterns (for comparison)
FINANCE_NER_PATTERNS = {
    "COMPANY": r"\b(?:Inc\.|Corp\.|Corporation|LLC|Ltd\.|Company)\b",
    "TICKER": r"\b[A-Z]{1,5}\b",
    "CURRENCY": r"\$\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:million|billion|M|B))?\b",
    "PERCENTAGE": r"\b\d+(?:\.\d+)?%\b",
    "FISCAL_PERIOD": r"\b(?:Q[1-4]|FY|fiscal year|quarter)\s*\d{2,4}\b",
    "FILING_TYPE": r"\b(?:10-K|10-Q|8-K|S-1|DEF 14A)\b",
}


@dataclass
class TransformedChunk:
    """A transformed document chunk with extracted entities."""
    
    chunk_id: str
    text: str
    section: str
    entities: dict[str, list[str]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransformResult:
    """Result of document transformation."""
    
    document_id: str
    source_type: str
    chunks: list[TransformedChunk]
    summary: dict[str, Any]
    domain: str


class HealthcareTransformer:
    """Transformer for healthcare domain documents."""
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.domain = "healthcare"
        self.ner_patterns = HEALTHCARE_NER_PATTERNS
    
    def transform_to_silver(
        self,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Transform bronze data to silver layer.
        
        Applies:
        - Text normalization
        - Section extraction
        - Entity recognition
        - Data validation
        """
        content = document.get("content", "")
        sections = document.get("sections", [])
        
        # Normalize text
        normalized_content = self._normalize_text(content)
        
        # Extract entities from full document
        entities = self._extract_entities(normalized_content)
        
        # Process sections
        processed_sections = []
        for section in sections:
            section_entities = self._extract_entities(section.get("content", ""))
            processed_sections.append({
                "title": section.get("title", ""),
                "content": self._normalize_text(section.get("content", "")),
                "entities": section_entities,
                "word_count": len(section.get("content", "").split()),
            })
        
        return {
            "document_id": document.get("document_id"),
            "facility_id": document.get("facility_id"),
            "facility_name": document.get("facility_name"),
            "document_type": document.get("document_type"),
            "report_date": document.get("report_date"),
            "content": normalized_content,
            "sections": processed_sections,
            "entities": entities,
            "metrics": document.get("metrics", {}),
            "layer": "silver",
            "transformed_at": datetime.now().isoformat(),
        }
    
    def transform_to_gold(
        self,
        silver_document: dict[str, Any],
    ) -> TransformResult:
        """
        Transform silver data to gold layer.
        
        Applies:
        - Chunking for embedding
        - Entity consolidation
        - Quality scoring
        - Metadata enrichment
        """
        chunks = []
        all_entities: dict[str, set[str]] = {}
        
        for section in silver_document.get("sections", []):
            section_chunks = self._chunk_section(
                section.get("content", ""),
                section.get("title", ""),
                silver_document.get("document_id", ""),
            )
            chunks.extend(section_chunks)
            
            # Consolidate entities
            for entity_type, values in section.get("entities", {}).items():
                if entity_type not in all_entities:
                    all_entities[entity_type] = set()
                all_entities[entity_type].update(values)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(silver_document)
        
        return TransformResult(
            document_id=silver_document.get("document_id", ""),
            source_type=silver_document.get("document_type", ""),
            chunks=chunks,
            summary={
                "facility_name": silver_document.get("facility_name"),
                "report_date": silver_document.get("report_date"),
                "section_count": len(silver_document.get("sections", [])),
                "chunk_count": len(chunks),
                "entity_count": sum(len(v) for v in all_entities.values()),
                "entities": {k: list(v) for k, v in all_entities.items()},
                "quality_score": quality_score,
                "key_metrics": silver_document.get("metrics", {}),
            },
            domain=self.domain,
        )
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text content."""
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Normalize line breaks
        text = re.sub(r"\n\s*\n", "\n\n", text)
        # Strip leading/trailing whitespace
        text = text.strip()
        return text
    
    def _extract_entities(self, text: str) -> dict[str, list[str]]:
        """Extract healthcare-specific entities from text."""
        entities = {}
        
        for entity_type, pattern in self.ner_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Deduplicate and normalize
                unique_matches = list(set(m.strip() for m in matches))
                entities[entity_type] = unique_matches
        
        return entities
    
    def _chunk_section(
        self,
        content: str,
        section_title: str,
        document_id: str,
        chunk_size: int = 500,
        overlap: int = 100,
    ) -> list[TransformedChunk]:
        """Chunk section content for embedding."""
        chunks = []
        words = content.split()
        
        if not words:
            return chunks
        
        start = 0
        chunk_index = 0
        
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)
            
            # Extract entities for this chunk
            chunk_entities = self._extract_entities(chunk_text)
            
            chunk_id = f"{document_id}_{section_title[:10]}_{chunk_index}"
            
            chunks.append(TransformedChunk(
                chunk_id=chunk_id,
                text=chunk_text,
                section=section_title,
                entities=chunk_entities,
                metadata={
                    "word_count": len(chunk_words),
                    "char_count": len(chunk_text),
                    "chunk_index": chunk_index,
                },
            ))
            
            # Move to next chunk with overlap
            start = end - overlap if end < len(words) else end
            chunk_index += 1
        
        return chunks
    
    def _calculate_quality_score(self, document: dict[str, Any]) -> float:
        """Calculate a quality score for the document."""
        score = 0.0
        max_score = 100.0
        
        # Has required sections (25 points)
        sections = document.get("sections", [])
        if sections:
            score += min(25, len(sections) * 5)
        
        # Has entities extracted (25 points)
        entities = document.get("entities", {})
        if entities:
            score += min(25, len(entities) * 5)
        
        # Has metrics (25 points)
        metrics = document.get("metrics", {})
        if metrics:
            score += min(25, len(metrics) * 3)
        
        # Content length appropriate (25 points)
        content = document.get("content", "")
        word_count = len(content.split())
        if 100 <= word_count <= 5000:
            score += 25
        elif word_count > 50:
            score += 15
        
        return round(score / max_score, 2)


class DomainTransformer:
    """Factory for domain-specific transformers."""
    
    def __init__(self):
        self.domain = os.getenv("DOMAIN", "finance").lower()
    
    def get_transformer(self):
        """Get the appropriate transformer for the current domain."""
        if self.domain == "healthcare":
            return HealthcareTransformer()
        else:
            # Return finance transformer (default)
            from .silver_transform import SilverTransformer
            return SilverTransformer()
    
    def get_ner_patterns(self) -> dict[str, str]:
        """Get NER patterns for the current domain."""
        if self.domain == "healthcare":
            return HEALTHCARE_NER_PATTERNS
        else:
            return FINANCE_NER_PATTERNS


def get_entity_filter(domain: str | None = None) -> dict[str, str]:
    """
    Get entity filter patterns for the specified domain.
    
    Usage:
        patterns = get_entity_filter("healthcare")
        patterns = get_entity_filter()  # Uses DOMAIN env var
    """
    domain = domain or os.getenv("DOMAIN", "finance").lower()
    
    if domain == "healthcare":
        return HEALTHCARE_NER_PATTERNS
    else:
        return FINANCE_NER_PATTERNS


# Demo usage
if __name__ == "__main__":
    from .healthcare_connector import HealthcareConnector
    
    print("Healthcare Domain Transformer Demo")
    print("=" * 50)
    print(f"Current domain: {DOMAIN}")
    
    # Get connector and transformer
    connector = HealthcareConnector()
    transformer = HealthcareTransformer()
    
    # Generate sample document
    doc = connector.generate_quality_report("METRO_GENERAL")
    
    # Transform to silver
    silver = transformer.transform_to_silver({
        "document_id": doc.document_id,
        "facility_id": doc.facility_id,
        "facility_name": doc.facility_name,
        "document_type": doc.document_type.value,
        "report_date": doc.report_date,
        "content": doc.content,
        "sections": doc.sections,
        "metrics": doc.metrics,
    })
    
    print(f"\nSilver Layer:")
    print(f"  Entities: {list(silver['entities'].keys())}")
    print(f"  Sections: {len(silver['sections'])}")
    
    # Transform to gold
    gold = transformer.transform_to_gold(silver)
    
    print(f"\nGold Layer:")
    print(f"  Chunks: {len(gold.chunks)}")
    print(f"  Quality Score: {gold.summary['quality_score']}")
