"""Pydantic models for API requests and responses."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Request model for POST /v1/ask."""
    
    query: str = Field(
        ...,
        description="User's question about financial documents",
        min_length=1,
        max_length=500,
        examples=["What was Apple's revenue in Q3 2023?"]
    )
    
    tenant_id: str = Field(
        default="demo",
        description="Tenant identifier for multi-tenancy",
        max_length=100,
        examples=["demo", "acme-corp", "tenant-123"]
    )
    
    stream: bool = Field(
        default=True,
        description="Whether to stream the response using SSE"
    )
    
    trace_id: Optional[str] = Field(
        default=None,
        description="Optional trace ID for distributed tracing",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )


class Citation(BaseModel):
    """Citation model for response."""
    
    source_uri: str = Field(
        ...,
        description="S3 URI or path to source document",
        examples=["s3://vesper-docs/10-Q/aapl-2023-q3.html"]
    )
    
    page: Optional[int] = Field(
        None,
        description="Page number in source document (for PDFs)",
        ge=0  # Allow 0 for documents without pages
    )
    
    span: dict = Field(
        ...,
        description="Exact span in source (start_char, end_char, text)",
        examples=[{"start_char": 1234, "end_char": 1567, "text": "Revenue was $81.8B"}]
    )
    
    sha256: str = Field(
        ...,
        description="SHA-256 hash of the source content for verification",
        min_length=1,  # Allow shorter hashes (may be truncated IDs)
        max_length=64
    )


class StreamEvent(BaseModel):
    """Server-Sent Event model."""
    
    type: str = Field(
        ...,
        description="Event type: 'token', 'citation', 'done', 'error'",
        examples=["token", "citation", "done", "error"]
    )
    
    content: Optional[str] = Field(
        None,
        description="Token content (for type='token')"
    )
    
    citations: Optional[List[Citation]] = Field(
        None,
        description="Citations (for type='citation')"
    )
    
    latency_ms: Optional[float] = Field(
        None,
        description="Total latency in milliseconds (for type='done')"
    )
    
    cost_usd: Optional[float] = Field(
        None,
        description="Estimated cost in USD (for type='done')"
    )
    
    error: Optional[str] = Field(
        None,
        description="Error message (for type='error')"
    )


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(
        ...,
        description="Overall health status: 'healthy', 'degraded', 'unhealthy'",
        examples=["healthy", "degraded", "unhealthy"]
    )
    
    checks: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Individual health checks for each dependency",
        examples=[{
            "database": {"status": "healthy", "latency_ms": 5.2},
            "redis": {"status": "healthy", "latency_ms": 1.1},
            "agents": {"status": "healthy", "latency_ms": 12.3}
        }]
    )
    
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp of health check"
    )
