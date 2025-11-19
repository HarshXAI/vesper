"""
Content Hashing & Provenance Tracking Module

This module provides SHA-256 content hashing and provenance tracking for documents
and chunks. It enables citation verification, content integrity checks, and full
lineage tracking from source documents through transformations.

Features:
- Document and chunk-level SHA-256 hashing
- Span offset tracking (character and line positions)
- Provenance chain tracking (source → document → chunk)
- Hash verification with detailed error reporting
- Transformation metadata tracking

Example:
    >>> from vesper_processing.provenance import ProvenanceTracker, hash_content
    >>> 
    >>> # Hash content
    >>> content_hash = hash_content("Sample text")
    >>> 
    >>> # Track provenance
    >>> tracker = ProvenanceTracker()
    >>> doc_prov = tracker.track_document(
    ...     content="Full document text",
    ...     source_url="https://sec.gov/filing.html",
    ...     metadata={'ticker': 'AAPL', 'form_type': '10-Q'}
    ... )
    >>> 
    >>> # Track chunk with span offsets
    >>> chunk_prov = tracker.track_chunk(
    ...     content="Chunk text",
    ...     document_hash=doc_prov.content_hash,
    ...     start_char=100,
    ...     end_char=200,
    ...     start_line=5,
    ...     end_line=8
    ... )
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class TransformationType(str, Enum):
    """Types of content transformations"""
    INGESTION = "ingestion"
    CLEANING = "cleaning"
    CHUNKING = "chunking"
    EXTRACTION = "extraction"
    ENRICHMENT = "enrichment"
    AGGREGATION = "aggregation"


@dataclass
class SpanOffset:
    """
    Represents the position of content within a source document.
    
    Attributes:
        start_char: Starting character position (0-based)
        end_char: Ending character position (exclusive)
        start_line: Starting line number (1-based)
        end_line: Ending line number (1-based, inclusive)
    """
    start_char: int
    end_char: int
    start_line: int
    end_line: int
    
    def __post_init__(self):
        """Validate span offsets"""
        if self.start_char < 0:
            raise ValueError(f"start_char must be >= 0, got {self.start_char}")
        if self.end_char <= self.start_char:
            raise ValueError(f"end_char ({self.end_char}) must be > start_char ({self.start_char})")
        if self.start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {self.start_line}")
        if self.end_line < self.start_line:
            raise ValueError(f"end_line ({self.end_line}) must be >= start_line ({self.start_line})")
    
    @property
    def char_length(self) -> int:
        """Character length of the span"""
        return self.end_char - self.start_char
    
    @property
    def line_count(self) -> int:
        """Number of lines in the span"""
        return self.end_line - self.start_line + 1
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary"""
        return {
            'start_char': self.start_char,
            'end_char': self.end_char,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'char_length': self.char_length,
            'line_count': self.line_count
        }


@dataclass
class TransformationStep:
    """
    Represents a single transformation in the provenance chain.
    
    Attributes:
        transform_type: Type of transformation applied
        timestamp: When the transformation occurred
        input_hash: Hash of input content
        output_hash: Hash of output content
        parameters: Transformation parameters
        metadata: Additional metadata
    """
    transform_type: TransformationType
    timestamp: datetime
    input_hash: str
    output_hash: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'transform_type': self.transform_type.value,
            'timestamp': self.timestamp.isoformat(),
            'input_hash': self.input_hash,
            'output_hash': self.output_hash,
            'parameters': self.parameters,
            'metadata': self.metadata
        }


@dataclass
class DocumentProvenance:
    """
    Complete provenance information for a document.
    
    Attributes:
        content_hash: SHA-256 hash of document content
        source_url: Original source URL or identifier
        ingestion_timestamp: When document was ingested
        content_length: Length of content in characters
        line_count: Number of lines in document
        metadata: Additional metadata (ticker, form_type, etc.)
        transformations: Chain of transformations applied
    """
    content_hash: str
    source_url: str
    ingestion_timestamp: datetime
    content_length: int
    line_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    transformations: List[TransformationStep] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'content_hash': self.content_hash,
            'source_url': self.source_url,
            'ingestion_timestamp': self.ingestion_timestamp.isoformat(),
            'content_length': self.content_length,
            'line_count': self.line_count,
            'metadata': self.metadata,
            'transformations': [t.to_dict() for t in self.transformations]
        }


@dataclass
class ChunkProvenance:
    """
    Complete provenance information for a content chunk.
    
    Attributes:
        content_hash: SHA-256 hash of chunk content
        document_hash: Hash of source document
        span: Position within source document
        chunk_timestamp: When chunk was created
        content_length: Length of chunk in characters
        metadata: Additional metadata
        transformations: Chain of transformations applied
    """
    content_hash: str
    document_hash: str
    span: SpanOffset
    chunk_timestamp: datetime
    content_length: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    transformations: List[TransformationStep] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'content_hash': self.content_hash,
            'document_hash': self.document_hash,
            'span': self.span.to_dict(),
            'chunk_timestamp': self.chunk_timestamp.isoformat(),
            'content_length': self.content_length,
            'metadata': self.metadata,
            'transformations': [t.to_dict() for t in self.transformations]
        }
    
    @property
    def provenance_chain(self) -> str:
        """Get human-readable provenance chain"""
        return f"{self.document_hash} → {self.content_hash}"


def hash_content(content: str, algorithm: str = "sha256") -> str:
    """
    Generate cryptographic hash of content.
    
    Args:
        content: Text content to hash
        algorithm: Hash algorithm (default: sha256)
        
    Returns:
        Hexadecimal hash string
        
    Example:
        >>> hash_content("Hello, world!")
        '315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3'
    """
    if not content:
        raise ValueError("Content cannot be empty")
    
    if algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha1":
        hasher = hashlib.sha1()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    hasher.update(content.encode('utf-8'))
    return hasher.hexdigest()


def calculate_span_offsets(
    full_text: str,
    chunk_text: str,
    start_pos: Optional[int] = None
) -> SpanOffset:
    """
    Calculate span offsets for a chunk within a document.
    
    Args:
        full_text: Full document text
        chunk_text: Chunk text to locate
        start_pos: Optional starting position hint
        
    Returns:
        SpanOffset with character and line positions
        
    Raises:
        ValueError: If chunk_text not found in full_text
    """
    # Find chunk position
    if start_pos is not None:
        start_char = start_pos
    else:
        start_char = full_text.find(chunk_text)
    
    if start_char == -1:
        raise ValueError("Chunk text not found in document")
    
    end_char = start_char + len(chunk_text)
    
    # Calculate line numbers
    lines_before = full_text[:start_char].count('\n')
    lines_in_chunk = chunk_text.count('\n')
    
    start_line = lines_before + 1  # 1-based
    end_line = start_line + lines_in_chunk
    
    return SpanOffset(
        start_char=start_char,
        end_char=end_char,
        start_line=start_line,
        end_line=end_line
    )


class ProvenanceTracker:
    """
    Tracks provenance and content hashing for documents and chunks.
    
    This class maintains a registry of document and chunk provenance,
    enabling citation verification and content integrity checks.
    
    Example:
        >>> tracker = ProvenanceTracker()
        >>> 
        >>> # Track document
        >>> doc_prov = tracker.track_document(
        ...     content="Document content...",
        ...     source_url="https://example.com/doc.html",
        ...     metadata={'ticker': 'AAPL'}
        ... )
        >>> 
        >>> # Track chunk
        >>> chunk_prov = tracker.track_chunk(
        ...     content="Chunk content...",
        ...     document_hash=doc_prov.content_hash,
        ...     start_char=0,
        ...     end_char=100,
        ...     start_line=1,
        ...     end_line=5
        ... )
        >>> 
        >>> # Verify hash
        >>> is_valid = tracker.verify_content(
        ...     content="Document content...",
        ...     expected_hash=doc_prov.content_hash
        ... )
    """
    
    def __init__(self):
        self.documents: Dict[str, DocumentProvenance] = {}
        self.chunks: Dict[str, ChunkProvenance] = {}
    
    def track_document(
        self,
        content: str,
        source_url: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> DocumentProvenance:
        """
        Track provenance for a document.
        
        Args:
            content: Document content
            source_url: Source URL or identifier
            metadata: Additional metadata
            timestamp: Ingestion timestamp (default: now)
            
        Returns:
            DocumentProvenance object
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        if metadata is None:
            metadata = {}
        
        content_hash = hash_content(content)
        content_length = len(content)
        line_count = content.count('\n') + 1
        
        provenance = DocumentProvenance(
            content_hash=content_hash,
            source_url=source_url,
            ingestion_timestamp=timestamp,
            content_length=content_length,
            line_count=line_count,
            metadata=metadata
        )
        
        self.documents[content_hash] = provenance
        return provenance
    
    def track_chunk(
        self,
        content: str,
        document_hash: str,
        start_char: int,
        end_char: int,
        start_line: int,
        end_line: int,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> ChunkProvenance:
        """
        Track provenance for a chunk.
        
        Args:
            content: Chunk content
            document_hash: Hash of source document
            start_char: Starting character position
            end_char: Ending character position
            start_line: Starting line number
            end_line: Ending line number
            metadata: Additional metadata
            timestamp: Chunk creation timestamp (default: now)
            
        Returns:
            ChunkProvenance object
            
        Raises:
            ValueError: If document_hash not found in registry
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        if metadata is None:
            metadata = {}
        
        # Verify document exists
        if document_hash not in self.documents:
            raise ValueError(f"Document hash not found: {document_hash}")
        
        content_hash = hash_content(content)
        content_length = len(content)
        
        span = SpanOffset(
            start_char=start_char,
            end_char=end_char,
            start_line=start_line,
            end_line=end_line
        )
        
        provenance = ChunkProvenance(
            content_hash=content_hash,
            document_hash=document_hash,
            span=span,
            chunk_timestamp=timestamp,
            content_length=content_length,
            metadata=metadata
        )
        
        self.chunks[content_hash] = provenance
        return provenance
    
    def add_transformation(
        self,
        content_hash: str,
        transform_type: TransformationType,
        input_hash: str,
        parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Add a transformation step to provenance chain.
        
        Args:
            content_hash: Hash of output content
            transform_type: Type of transformation
            input_hash: Hash of input content
            parameters: Transformation parameters
            metadata: Additional metadata
            timestamp: Transformation timestamp (default: now)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        if parameters is None:
            parameters = {}
        
        if metadata is None:
            metadata = {}
        
        transformation = TransformationStep(
            transform_type=transform_type,
            timestamp=timestamp,
            input_hash=input_hash,
            output_hash=content_hash,
            parameters=parameters,
            metadata=metadata
        )
        
        # Add to document or chunk
        if content_hash in self.documents:
            self.documents[content_hash].transformations.append(transformation)
        elif content_hash in self.chunks:
            self.chunks[content_hash].transformations.append(transformation)
        else:
            raise ValueError(f"Content hash not found: {content_hash}")
    
    def verify_content(
        self,
        content: str,
        expected_hash: str,
        algorithm: str = "sha256"
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify content matches expected hash.
        
        Args:
            content: Content to verify
            expected_hash: Expected hash value
            algorithm: Hash algorithm (default: sha256)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            actual_hash = hash_content(content, algorithm)
            
            if actual_hash == expected_hash:
                return (True, None)
            else:
                error = f"Hash mismatch: expected {expected_hash}, got {actual_hash}"
                return (False, error)
        
        except Exception as e:
            return (False, f"Verification error: {str(e)}")
    
    def get_document_provenance(self, content_hash: str) -> Optional[DocumentProvenance]:
        """Get document provenance by hash"""
        return self.documents.get(content_hash)
    
    def get_chunk_provenance(self, content_hash: str) -> Optional[ChunkProvenance]:
        """Get chunk provenance by hash"""
        return self.chunks.get(content_hash)
    
    def get_provenance_chain(self, chunk_hash: str) -> Optional[List[str]]:
        """
        Get full provenance chain for a chunk.
        
        Args:
            chunk_hash: Hash of the chunk
            
        Returns:
            List of hashes in provenance chain: [source_url, doc_hash, chunk_hash]
        """
        chunk_prov = self.chunks.get(chunk_hash)
        if not chunk_prov:
            return None
        
        doc_prov = self.documents.get(chunk_prov.document_hash)
        if not doc_prov:
            return [chunk_prov.document_hash, chunk_hash]
        
        return [doc_prov.source_url, chunk_prov.document_hash, chunk_hash]
    
    def export_provenance(self) -> Dict[str, Any]:
        """
        Export all provenance data.
        
        Returns:
            Dictionary with documents and chunks provenance
        """
        return {
            'documents': {h: p.to_dict() for h, p in self.documents.items()},
            'chunks': {h: p.to_dict() for h, p in self.chunks.items()}
        }
