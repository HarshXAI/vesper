"""Core configuration for API Gateway."""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    api_title: str = "Vesper API Gateway"
    api_description: str = "Production API for financial document Q&A with citations"
    api_version: str = "v1"
    api_port: int = 8000
    api_workers: int = 4
    
    # Database
    database_url: str = "postgresql://vesper:vesper@localhost:5432/vesper"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Agents Worker
    agents_worker_url: str = "http://localhost:8001"
    
    # Streaming
    stream_chunk_size: int = 1024
    stream_timeout_sec: int = 120
    
    # Limits
    max_query_length: int = 500
    max_tenant_id_length: int = 100
    
    # Health Check
    health_check_timeout_sec: int = 5
    
    # Logging
    log_level: str = "INFO"
    
    # Guardrails
    guardrails_enabled: bool = True
    
    # OpenTelemetry
    otel_exporter_endpoint: Optional[str] = None  # e.g., "http://localhost:4317" for OTLP, None for console
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
