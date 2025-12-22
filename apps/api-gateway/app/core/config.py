"""
Core configuration for VESPER API Gateway.

Provides centralized configuration management with support for:
- Environment variables (loaded from SSM at runtime)
- Per-tenant budget configuration
- Model routing configuration
- Cost governor settings
- Secret validation on startup
"""

import os
import sys
from typing import Optional, Dict, List
from pydantic import Field, ConfigDict, field_validator
from pydantic_settings import BaseSettings


def _check_required_secret(name: str, value: Optional[str]) -> str:
    """Validate required secrets are present at startup."""
    if not value or value.strip() == "":
        print(f"❌ FATAL: Required secret '{name}' is missing or empty", file=sys.stderr)
        print(f"   Set via environment variable or SSM Parameter Store", file=sys.stderr)
        # In production, fail fast if secrets are missing
        if os.getenv("ENVIRONMENT", "dev") in ("staging", "prod"):
            sys.exit(1)
        return ""
    return value


class TenantBudgetConfig(BaseSettings):
    """Per-tenant budget configuration."""
    
    # Monthly budget in USD
    monthly_budget_usd: float = 100.0
    
    # Warning thresholds
    warning_threshold: float = 0.8  # 80% - trigger cost governor soft mode
    critical_threshold: float = 0.9  # 90% - trigger cost governor hard mode
    
    # Model restrictions when budget is tight
    allowed_models_normal: List[str] = Field(
        default=["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "claude-3-sonnet", "claude-3-haiku"]
    )
    allowed_models_warning: List[str] = Field(
        default=["gpt-4o-mini", "gpt-3.5-turbo", "claude-3-haiku"]
    )
    allowed_models_critical: List[str] = Field(
        default=["gpt-3.5-turbo", "claude-3-haiku"]
    )
    
    model_config = ConfigDict(
        env_prefix="VESPER_BUDGET_",
        protected_namespaces=()
    )


class CostGovernorConfig(BaseSettings):
    """Cost governor configuration."""
    
    # Enable cost governor
    enabled: bool = True
    
    # Default budget per tenant (USD/month)
    default_budget_usd: float = 100.0
    
    # Model costs (USD per 1K tokens)
    model_costs: Dict[str, Dict[str, float]] = Field(default={
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    })
    
    # Embedding costs (USD per 1K tokens)
    embedding_costs: Dict[str, float] = Field(default={
        "text-embedding-3-small": 0.00002,
        "text-embedding-3-large": 0.00013,
        "text-embedding-ada-002": 0.0001,
    })
    
    # Rerank costs (USD per 1K documents)
    rerank_costs: Dict[str, float] = Field(default={
        "cohere-rerank-v3": 0.002,
        "bge-reranker": 0.0,  # Self-hosted
    })
    
    model_config = ConfigDict(
        env_prefix="VESPER_COST_",
        protected_namespaces=()
    )


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
    otel_exporter_endpoint: Optional[str] = None  # e.g., "http://localhost:4317" for OTLP
    otel_service_name: str = "vesper-api-gateway"
    
    # Cost Governor
    cost_governor: CostGovernorConfig = Field(default_factory=CostGovernorConfig)
    
    # Default Tenant Budget
    default_tenant_budget: TenantBudgetConfig = Field(default_factory=TenantBudgetConfig)
    
    # Evaluation
    eval_queries_path: str = "data/eval/queries.jsonl"
    eval_results_bucket: str = "vesper-artifacts-dev"
    
    # Slack Notifications
    slack_webhook_url: Optional[str] = None
    slack_channel: str = "#vesper-alerts"
    
    # MLflow
    mlflow_tracking_uri: str = "http://mlflow:5000"
    mlflow_experiment_name: str = "vesper-nightly-eval"
    
    # Prometheus
    prometheus_url: str = "http://prometheus:9090"
    
    # Airflow
    airflow_url: str = "http://airflow-webserver:8080"
    
    # Authentication (loaded from SSM in prod)
    auth_enabled: bool = True
    cognito_user_pool_id: str = ""
    cognito_region: str = "us-east-1"
    cognito_analyst_client_id: str = ""
    cognito_ops_client_id: str = ""
    cognito_api_client_id: str = ""
    
    # JWKS URL (constructed or loaded from SSM)
    jwks_url: Optional[str] = None
    
    # Secrets (loaded from SSM Parameter Store in prod)
    # These should NEVER have default values in production
    slack_webhook_url: Optional[str] = None
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        protected_namespaces=()
    )
    
    @field_validator("cognito_user_pool_id", mode="after")
    @classmethod
    def validate_cognito_pool(cls, v: str) -> str:
        """Validate Cognito user pool ID in production."""
        env = os.getenv("ENVIRONMENT", "dev")
        if env in ("staging", "prod") and (not v or v.strip() == ""):
            return _check_required_secret("COGNITO_USER_POOL_ID", v)
        return v
    
    @field_validator("database_url", mode="after")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL doesn't contain plaintext secrets in prod."""
        env = os.getenv("ENVIRONMENT", "dev")
        if env in ("staging", "prod"):
            if "localhost" in v or "vesper:vesper" in v:
                print("⚠️  WARNING: Using default database URL in production!", file=sys.stderr)
        return v
    
    @property
    def computed_jwks_url(self) -> str:
        """Compute JWKS URL from Cognito settings."""
        if self.jwks_url:
            return self.jwks_url
        if self.cognito_user_pool_id and self.cognito_region:
            return (
                f"https://cognito-idp.{self.cognito_region}.amazonaws.com/"
                f"{self.cognito_user_pool_id}/.well-known/jwks.json"
            )
        return ""
    
    @property
    def jwt_issuer(self) -> str:
        """Compute JWT issuer from Cognito settings."""
        if self.cognito_user_pool_id and self.cognito_region:
            return (
                f"https://cognito-idp.{self.cognito_region}.amazonaws.com/"
                f"{self.cognito_user_pool_id}"
            )
        return ""


def validate_secrets_on_startup() -> bool:
    """
    Validate all required secrets are present.
    Called during application startup.
    
    Returns:
        True if all secrets valid, False otherwise
    """
    errors = []
    env = os.getenv("ENVIRONMENT", "dev")
    
    if env not in ("staging", "prod"):
        return True  # Skip validation in dev
    
    required_secrets = [
        ("COGNITO_USER_POOL_ID", os.getenv("COGNITO_USER_POOL_ID")),
        ("COGNITO_ANALYST_CLIENT_ID", os.getenv("COGNITO_ANALYST_CLIENT_ID")),
        ("DATABASE_URL", os.getenv("DATABASE_URL")),
    ]
    
    for name, value in required_secrets:
        if not value or value.strip() == "":
            errors.append(name)
    
    if errors:
        print(f"❌ FATAL: Missing required secrets: {', '.join(errors)}", file=sys.stderr)
        return False
    
    print("✅ All required secrets validated")
    return True


# Global settings instance
settings = Settings()
