"""
Configuration Management

Loads configuration from environment variables and provides settings objects.
"""
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    """Storage configuration"""
    
    # S3/MinIO settings
    s3_bucket_name: str = Field(default="vesper-bronze", alias="VESPER_S3_BUCKET")
    s3_endpoint_url: Optional[str] = Field(default=None, alias="VESPER_S3_ENDPOINT")
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class SECEdgarConfig(BaseSettings):
    """SEC EDGAR API configuration"""
    
    # User agent (required by SEC)
    user_agent: str = Field(
        default="VESPER Research vesper@research.com",
        alias="SEC_USER_AGENT"
    )
    
    # Rate limiting (max requests per second)
    rate_limit: float = Field(default=10.0, alias="SEC_RATE_LIMIT")
    
    # Request timeout
    timeout: int = Field(default=30, alias="SEC_TIMEOUT")
    
    # Retry configuration
    max_retries: int = Field(default=3, alias="SEC_MAX_RETRIES")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class DatabaseConfig(BaseSettings):
    """Database configuration"""
    
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5434, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="vesper", alias="POSTGRES_DB")
    postgres_user: str = Field(default="vesper", alias="POSTGRES_USER")
    postgres_password: str = Field(default="vesper_password", alias="POSTGRES_PASSWORD")
    
    @property
    def connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class IngestionConfig(BaseSettings):
    """Main ingestion service configuration"""
    
    # Service settings
    service_name: str = Field(default="vesper-ingestion", alias="SERVICE_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Component configs
    storage: StorageConfig = Field(default_factory=StorageConfig)
    sec_edgar: SECEdgarConfig = Field(default_factory=SECEdgarConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env
    
    @classmethod
    def from_env(cls) -> "IngestionConfig":
        """Load configuration from environment"""
        return cls(
            storage=StorageConfig(),
            sec_edgar=SECEdgarConfig(),
            database=DatabaseConfig()
        )


# Global config instance
_config: Optional[IngestionConfig] = None


def get_config() -> IngestionConfig:
    """
    Get or create global configuration instance
    
    Returns:
        IngestionConfig instance
    """
    global _config
    if _config is None:
        _config = IngestionConfig.from_env()
    return _config


def reload_config() -> IngestionConfig:
    """
    Force reload configuration from environment
    
    Returns:
        New IngestionConfig instance
    """
    global _config
    _config = IngestionConfig.from_env()
    return _config
