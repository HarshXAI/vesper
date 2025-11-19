"""
Section extractor for SEC filings
"""
import re
from typing import List, Dict, Tuple, Optional
import structlog
from vesper_processing.models import ProcessedSection, SectionType

logger = structlog.get_logger()


class SectionExtractor:
    """
    Extract sections from SEC filings
    
    Identifies and extracts key sections like:
    - Item 1: Business
    - Item 1A: Risk Factors
    - Item 7: MD&A
    - Item 8: Financial Statements
    etc.
    """
    
    # Section patterns for 10-K and 10-Q
    SECTION_PATTERNS = {
        SectionType.ITEM_1: [
            r'item\s+1\s*[.\-:]\s*business',
            r'item\s+1\s*$',
        ],
        SectionType.ITEM_1A: [
            r'item\s+1a\s*[.\-:]\s*risk\s+factors',
            r'item\s+1a\s*$',
        ],
        SectionType.ITEM_1B: [
            r'item\s+1b\s*[.\-:]\s*unresolved\s+staff',
            r'item\s+1b\s*$',
        ],
        SectionType.ITEM_2: [
            r'item\s+2\s*[.\-:]\s*properties',
            r'item\s+2\s*$',
        ],
        SectionType.ITEM_3: [
            r'item\s+3\s*[.\-:]\s*legal\s+proceedings',
            r'item\s+3\s*$',
        ],
        SectionType.ITEM_7: [
            r'item\s+7\s*[.\-:]\s*management[\'\u2019s\s]+discussion',  # Handle both ' and '
            r'item\s+7\s*[.\-:]\s*md\s*&\s*a',
            r'item\s+7\s*$',
        ],
        SectionType.ITEM_7A: [
            r'item\s+7a\s*[.\-:]\s*quantitative\s+and\s+qualitative',
            r'item\s+7a\s*$',
        ],
        SectionType.ITEM_8: [
            r'item\s+8\s*[.\-:]\s*financial\s+statements',
            r'item\s+8\s*$',
        ],
        SectionType.ITEM_9: [
            r'item\s+9\s*[.\-:]\s*changes\s+in\s+and\s+disagreements',
            r'item\s+9\s*$',
        ],
        SectionType.ITEM_9A: [
            r'item\s+9a\s*[.\-:]\s*controls\s+and\s+procedures',
            r'item\s+9a\s*$',
        ],
    }
    
    def __init__(self, min_section_length: int = 50):
        """
        Initialize section extractor
        
        Args:
            min_section_length: Minimum section length in characters
        """
        self.min_section_length = min_section_length
        
        # Compile patterns
        self.compiled_patterns: Dict[SectionType, List[re.Pattern]] = {}
        for section_type, patterns in self.SECTION_PATTERNS.items():
            self.compiled_patterns[section_type] = [
                re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                for pattern in patterns
            ]
    
    def extract(self, text: str) -> List[ProcessedSection]:
        """
        Extract sections from document text
        
        Args:
            text: Clean document text
            
        Returns:
            List of extracted sections
        """
        if not text:
            logger.warning("empty_text_for_section_extraction")
            return []
        
        try:
            # Find all section boundaries
            boundaries = self._find_section_boundaries(text)
            
            if not boundaries:
                logger.warning("no_sections_found")
                return []
            
            # Extract section content
            sections = self._extract_section_content(text, boundaries)
            
            # Filter by minimum length
            sections = [
                s for s in sections 
                if len(s.content) >= self.min_section_length
            ]
            
            logger.info(
                "extracted_sections",
                section_count=len(sections),
                section_types=[s.section_type for s in sections]
            )
            
            return sections
            
        except Exception as e:
            logger.error("section_extraction_failed", error=str(e))
            raise
    
    def _find_section_boundaries(self, text: str) -> List[Tuple[SectionType, str, int]]:
        """
        Find section boundaries in text
        
        Returns:
            List of (section_type, title, position) tuples
        """
        boundaries = []
        
        for section_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    # Extract the full line containing the match
                    line_start = text.rfind('\n', 0, match.start()) + 1
                    line_end = text.find('\n', match.end())
                    if line_end == -1:
                        line_end = len(text)
                    
                    title = text[line_start:line_end].strip()
                    
                    # Skip table of contents entries (they have just a page number after)
                    # Look at next few lines to see if it's mostly just a number
                    next_line_start = line_end + 1
                    next_line_end = text.find('\n', next_line_start)
                    if next_line_end == -1:
                        next_line_end = len(text)
                    
                    next_line = text[next_line_start:next_line_end].strip()
                    
                    # If next line is just a number (page number), skip this as ToC entry
                    if next_line and next_line.isdigit():
                        logger.debug(
                            "skipping_toc_entry",
                            section_type=section_type,
                            title=title,
                            next_line=next_line
                        )
                        continue
                    
                    boundaries.append((section_type, title, match.start()))
        
        # Sort by position
        boundaries.sort(key=lambda x: x[2])
        
        # Remove duplicates (keep first occurrence)
        seen_types = set()
        unique_boundaries = []
        for section_type, title, pos in boundaries:
            if section_type not in seen_types:
                unique_boundaries.append((section_type, title, pos))
                seen_types.add(section_type)
        
        return unique_boundaries
    
    def _extract_section_content(
        self,
        text: str,
        boundaries: List[Tuple[SectionType, str, int]]
    ) -> List[ProcessedSection]:
        """
        Extract content for each section based on boundaries
        
        Args:
            text: Full document text
            boundaries: List of (section_type, title, position) tuples
            
        Returns:
            List of ProcessedSection objects
        """
        sections = []
        
        for i, (section_type, title, start_pos) in enumerate(boundaries):
            # Determine end position (next section or end of document)
            if i < len(boundaries) - 1:
                end_pos = boundaries[i + 1][2]
            else:
                end_pos = len(text)
            
            # Extract content (skip the title line)
            title_end = text.find('\n', start_pos)
            if title_end == -1:
                title_end = start_pos
            else:
                title_end += 1
            
            content = text[title_end:end_pos].strip()
            
            section = ProcessedSection(
                section_type=section_type,
                title=title,
                content=content,
                start_pos=start_pos,
                end_pos=end_pos,
                metadata={
                    'length': len(content),
                    'word_count': len(content.split())
                }
            )
            
            sections.append(section)
            
            logger.debug(
                "extracted_section_content",
                section_type=section_type,
                title=title,
                length=len(content)
            )
        
        return sections
    
    def get_section(
        self,
        sections: List[ProcessedSection],
        section_type: SectionType
    ) -> Optional[ProcessedSection]:
        """
        Get a specific section by type
        
        Args:
            sections: List of sections
            section_type: Type of section to retrieve
            
        Returns:
            ProcessedSection or None
        """
        for section in sections:
            if section.section_type == section_type:
                return section
        return None
