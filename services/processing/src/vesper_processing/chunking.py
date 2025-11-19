"""
Semantic Chunking Module

This module provides intelligent document chunking that respects semantic boundaries
(headings, paragraphs, tables) while maintaining 200-400 token chunks suitable for
embedding models.

Features:
- Heading-aware chunking (respects H1, H2, H3 hierarchy)
- Table-aware chunking (keeps tables intact with context)
- Configurable chunk size and overlap
- Token counting using tiktoken
- Comprehensive metadata for each chunk

Example:
    >>> from vesper_processing.chunking import SemanticChunker
    >>> chunker = SemanticChunker(target_tokens=300, overlap_tokens=50)
    >>> chunks = chunker.chunk_document(text, metadata={'doc_id': '123'})
    >>> for chunk in chunks:
    ...     print(f"Chunk {chunk.chunk_id}: {chunk.token_count} tokens")
"""

import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import tiktoken
from bs4 import BeautifulSoup


class ChunkType(str, Enum):
    """Type of content chunk"""
    TEXT = "text"
    HEADING = "heading"
    TABLE = "table"
    LIST = "list"
    PARAGRAPH = "paragraph"


@dataclass
class Chunk:
    """
    Represents a semantic chunk of document content with provenance.
    
    Attributes:
        chunk_id: Unique identifier for the chunk
        doc_id: Parent document identifier
        content: The actual text content
        chunk_type: Type of content (text, heading, table, etc.)
        token_count: Number of tokens in the chunk
        position: Position in the document (0-based)
        start_char: Starting character position in original document
        end_char: Ending character position in original document
        section: Section name (e.g., "Item 1A", "MD&A")
        heading: Associated heading text
        content_hash: SHA-256 hash of chunk content (optional)
        document_hash: SHA-256 hash of source document (optional)
        metadata: Additional metadata
    """
    chunk_id: str
    doc_id: str
    content: str
    chunk_type: ChunkType
    token_count: int
    position: int
    start_char: int
    end_char: int
    section: Optional[str] = None
    heading: Optional[str] = None
    content_hash: Optional[str] = None
    document_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary"""
        return {
            'chunk_id': self.chunk_id,
            'doc_id': self.doc_id,
            'content': self.content,
            'chunk_type': self.chunk_type.value,
            'token_count': self.token_count,
            'position': self.position,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'section': self.section,
            'heading': self.heading,
            'content_hash': self.content_hash,
            'document_hash': self.document_hash,
            'metadata': self.metadata
        }


class SemanticChunker:
    """
    Intelligent document chunker that respects semantic boundaries.
    
    This chunker:
    - Maintains target chunk size of 200-400 tokens
    - Respects heading hierarchy (doesn't split mid-section)
    - Keeps tables intact with their captions
    - Provides configurable overlap between chunks
    - Includes comprehensive metadata
    
    Args:
        target_tokens: Target number of tokens per chunk (default: 300)
        min_tokens: Minimum tokens per chunk (default: 200)
        max_tokens: Maximum tokens per chunk (default: 400)
        overlap_tokens: Number of overlapping tokens between chunks (default: 50)
        encoding_name: Tiktoken encoding to use (default: "cl100k_base" for GPT-4)
    
    Example:
        >>> chunker = SemanticChunker(target_tokens=300, overlap_tokens=50)
        >>> chunks = chunker.chunk_document(document_text)
        >>> print(f"Created {len(chunks)} chunks")
    """
    
    def __init__(
        self,
        target_tokens: int = 300,
        min_tokens: int = 200,
        max_tokens: int = 400,
        overlap_tokens: int = 50,
        encoding_name: str = "cl100k_base"
    ):
        self.target_tokens = target_tokens
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        
        # Initialize tiktoken encoder
        try:
            self.encoder = tiktoken.get_encoding(encoding_name)
        except Exception:
            # Fallback to basic encoding
            self.encoder = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        if not text:
            return 0
        return len(self.encoder.encode(text))
    
    def _generate_chunk_id(self, doc_id: str, position: int, content: str) -> str:
        """
        Generate unique chunk ID.
        
        Args:
            doc_id: Document identifier
            position: Chunk position
            content: Chunk content
            
        Returns:
            Unique chunk identifier
        """
        # Create hash of content for uniqueness
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{doc_id}_chunk_{position}_{content_hash}"
    
    def _detect_headings(self, text: str) -> List[Tuple[int, str, int]]:
        """
        Detect headings in text (Markdown-style and numbered).
        
        Args:
            text: Text to analyze
            
        Returns:
            List of (position, heading_text, level) tuples
        """
        headings = []
        
        # Markdown-style headings (# Heading)
        for match in re.finditer(r'^(#{1,3})\s+(.+)$', text, re.MULTILINE):
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            position = match.start()
            headings.append((position, heading_text, level))
        
        # Numbered headings (1. Heading, 1.1 Subheading)
        for match in re.finditer(r'^(\d+(?:\.\d+)*)\s+([A-Z][^\.]+)$', text, re.MULTILINE):
            numbering = match.group(1)
            heading_text = match.group(2).strip()
            position = match.start()
            level = numbering.count('.') + 1
            headings.append((position, f"{numbering} {heading_text}", level))
        
        # SEC-specific sections (ITEM 1A, Part I, PART II)
        for match in re.finditer(r'^((?:ITEM|PART)\s+(?:\d+[A-Z]?|[IVX]+)[\.\:]?\s+[A-Z][^\.]+)$', text, re.MULTILINE | re.IGNORECASE):
            heading_text = match.group(1).strip()
            position = match.start()
            headings.append((position, heading_text, 1))
        
        # Sort by position
        headings.sort(key=lambda x: x[0])
        return headings
    
    def _detect_tables(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Detect table regions in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of (start_pos, end_pos, table_text) tuples
        """
        tables = []
        
        # Detect HTML tables
        soup = BeautifulSoup(text, 'html.parser')
        for table in soup.find_all('table'):
            table_text = str(table)
            # Find position in original text
            start_pos = text.find(table_text)
            if start_pos != -1:
                end_pos = start_pos + len(table_text)
                tables.append((start_pos, end_pos, table_text))
        
        # Detect ASCII tables (rows with | separators)
        table_pattern = r'(?:(?:\|[^\n]+\|[\n\r]+){3,})'
        for match in re.finditer(table_pattern, text):
            start_pos = match.start()
            end_pos = match.end()
            table_text = match.group(0)
            tables.append((start_pos, end_pos, table_text))
        
        return tables
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences
        """
        # Simple sentence splitter (can be enhanced)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def chunk_document(
        self,
        text: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk document into semantic chunks.
        
        Args:
            text: Document text to chunk
            doc_id: Document identifier (generated if not provided)
            metadata: Additional metadata to include in chunks
            
        Returns:
            List of Chunk objects
        """
        if not text:
            return []
        
        if doc_id is None:
            doc_id = hashlib.md5(text.encode()).hexdigest()[:16]
        
        if metadata is None:
            metadata = {}
        
        chunks = []
        current_pos = 0
        chunk_position = 0
        
        # Detect structure
        headings = self._detect_headings(text)
        tables = self._detect_tables(text)
        
        # Create sections based on headings
        sections = []
        for i, (pos, heading_text, level) in enumerate(headings):
            next_pos = headings[i + 1][0] if i + 1 < len(headings) else len(text)
            sections.append({
                'start': pos,
                'end': next_pos,
                'heading': heading_text,
                'level': level,
                'text': text[pos:next_pos]
            })
        
        # If no headings, treat entire document as one section
        if not sections:
            sections.append({
                'start': 0,
                'end': len(text),
                'heading': None,
                'level': 0,
                'text': text
            })
        
        # Process each section
        for section in sections:
            section_text = section['text']
            section_heading = section['heading']
            section_start = section['start']
            
            # Check if section contains tables
            section_tables = [
                (start - section_start, end - section_start, table_text)
                for start, end, table_text in tables
                if start >= section_start and end <= section['end']
            ]
            
            # If section is small enough, create single chunk
            section_tokens = self.count_tokens(section_text)
            if section_tokens <= self.max_tokens:
                chunk_type = ChunkType.TABLE if section_tables else ChunkType.TEXT
                chunk = Chunk(
                    chunk_id=self._generate_chunk_id(doc_id, chunk_position, section_text),
                    doc_id=doc_id,
                    content=section_text,
                    chunk_type=chunk_type,
                    token_count=section_tokens,
                    position=chunk_position,
                    start_char=section_start,
                    end_char=section['end'],
                    section=section_heading,
                    heading=section_heading,
                    metadata=metadata.copy()
                )
                chunks.append(chunk)
                chunk_position += 1
                continue
            
            # Section too large - split into smaller chunks
            sentences = self._split_into_sentences(section_text)
            current_chunk_sentences = []
            current_chunk_tokens = 0
            chunk_start_char = section_start
            
            for sentence in sentences:
                sentence_tokens = self.count_tokens(sentence)
                
                # If single sentence exceeds max, split it
                if sentence_tokens > self.max_tokens:
                    # Save current chunk if exists
                    if current_chunk_sentences:
                        chunk_text = ' '.join(current_chunk_sentences)
                        chunk = Chunk(
                            chunk_id=self._generate_chunk_id(doc_id, chunk_position, chunk_text),
                            doc_id=doc_id,
                            content=chunk_text,
                            chunk_type=ChunkType.TEXT,
                            token_count=current_chunk_tokens,
                            position=chunk_position,
                            start_char=chunk_start_char,
                            end_char=chunk_start_char + len(chunk_text),
                            section=section_heading,
                            heading=section_heading,
                            metadata=metadata.copy()
                        )
                        chunks.append(chunk)
                        chunk_position += 1
                        current_chunk_sentences = []
                        current_chunk_tokens = 0
                        chunk_start_char += len(chunk_text)
                    
                    # Split long sentence by words
                    words = sentence.split()
                    current_words = []
                    current_word_tokens = 0
                    
                    for word in words:
                        word_tokens = self.count_tokens(word)
                        if current_word_tokens + word_tokens > self.max_tokens:
                            # Save current word chunk
                            chunk_text = ' '.join(current_words)
                            chunk = Chunk(
                                chunk_id=self._generate_chunk_id(doc_id, chunk_position, chunk_text),
                                doc_id=doc_id,
                                content=chunk_text,
                                chunk_type=ChunkType.TEXT,
                                token_count=current_word_tokens,
                                position=chunk_position,
                                start_char=chunk_start_char,
                                end_char=chunk_start_char + len(chunk_text),
                                section=section_heading,
                                heading=section_heading,
                                metadata=metadata.copy()
                            )
                            chunks.append(chunk)
                            chunk_position += 1
                            current_words = [word]
                            current_word_tokens = word_tokens
                            chunk_start_char += len(chunk_text)
                        else:
                            current_words.append(word)
                            current_word_tokens += word_tokens
                    
                    # Save remaining words
                    if current_words:
                        chunk_text = ' '.join(current_words)
                        chunk = Chunk(
                            chunk_id=self._generate_chunk_id(doc_id, chunk_position, chunk_text),
                            doc_id=doc_id,
                            content=chunk_text,
                            chunk_type=ChunkType.TEXT,
                            token_count=current_word_tokens,
                            position=chunk_position,
                            start_char=chunk_start_char,
                            end_char=chunk_start_char + len(chunk_text),
                            section=section_heading,
                            heading=section_heading,
                            metadata=metadata.copy()
                        )
                        chunks.append(chunk)
                        chunk_position += 1
                        chunk_start_char += len(chunk_text)
                    
                    continue
                
                # Check if adding sentence exceeds target
                if current_chunk_tokens + sentence_tokens > self.target_tokens:
                    # Save current chunk
                    chunk_text = ' '.join(current_chunk_sentences)
                    chunk = Chunk(
                        chunk_id=self._generate_chunk_id(doc_id, chunk_position, chunk_text),
                        doc_id=doc_id,
                        content=chunk_text,
                        chunk_type=ChunkType.TEXT,
                        token_count=current_chunk_tokens,
                        position=chunk_position,
                        start_char=chunk_start_char,
                        end_char=chunk_start_char + len(chunk_text),
                        section=section_heading,
                        heading=section_heading,
                        metadata=metadata.copy()
                    )
                    chunks.append(chunk)
                    chunk_position += 1
                    
                    # Add overlap
                    if self.overlap_tokens > 0 and current_chunk_sentences:
                        # Keep last few sentences for overlap
                        overlap_sentences = []
                        overlap_tokens = 0
                        for sent in reversed(current_chunk_sentences):
                            sent_tokens = self.count_tokens(sent)
                            if overlap_tokens + sent_tokens <= self.overlap_tokens:
                                overlap_sentences.insert(0, sent)
                                overlap_tokens += sent_tokens
                            else:
                                break
                        current_chunk_sentences = overlap_sentences
                        current_chunk_tokens = overlap_tokens
                    else:
                        current_chunk_sentences = []
                        current_chunk_tokens = 0
                    
                    chunk_start_char += len(chunk_text)
                
                # Add sentence to current chunk
                current_chunk_sentences.append(sentence)
                current_chunk_tokens += sentence_tokens
            
            # Save final chunk in section
            if current_chunk_sentences:
                chunk_text = ' '.join(current_chunk_sentences)
                chunk = Chunk(
                    chunk_id=self._generate_chunk_id(doc_id, chunk_position, chunk_text),
                    doc_id=doc_id,
                    content=chunk_text,
                    chunk_type=ChunkType.TEXT,
                    token_count=current_chunk_tokens,
                    position=chunk_position,
                    start_char=chunk_start_char,
                    end_char=chunk_start_char + len(chunk_text),
                    section=section_heading,
                    heading=section_heading,
                    metadata=metadata.copy()
                )
                chunks.append(chunk)
                chunk_position += 1
        
        return chunks
    
    def chunk_documents(
        self,
        documents: List[Dict[str, Any]],
        text_field: str = 'text',
        id_field: str = 'id'
    ) -> Dict[str, List[Chunk]]:
        """
        Chunk multiple documents.
        
        Args:
            documents: List of document dictionaries
            text_field: Field name containing text
            id_field: Field name containing document ID
            
        Returns:
            Dictionary mapping doc_id to list of chunks
        """
        results = {}
        for doc in documents:
            text = doc.get(text_field, '')
            doc_id = doc.get(id_field)
            metadata = {k: v for k, v in doc.items() if k not in [text_field, id_field]}
            
            chunks = self.chunk_document(text, doc_id=doc_id, metadata=metadata)
            if doc_id:
                results[doc_id] = chunks
        
        return results
