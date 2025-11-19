"""
VESPER Document Processing Service Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class S3Config(BaseSettings):
    """S3/MinIO configuration"""
    
    model_config = SettingsConfigDict(
        env_prefix="S3_",
        env_file=".env",
        case_sensitive=False,
    )
    
    endpoint_url: str = Field(
        default="http://localhost:9000",
        description="S3/MinIO endpoint URL"
    )
    access_key: str = Field(
        default="minioadmin",
        description="S3 access key"
    )
    secret_key: str = Field(
        default="minioadmin",
        description="S3 secret key"
    )
    bronze_bucket: str = Field(
        default="vesper-bronze",
        description="Bronze layer bucket (raw data)"
    )
    silver_bucket: str = Field(
        default="vesper-silver",
        description="Silver layer bucket (processed data)"
    )
    region: str = Field(
        default="us-east-1",
        description="AWS region"
    )


class PostgresConfig(BaseSettings):
    """PostgreSQL configuration"""
    
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=".env",
        case_sensitive=False,
    )
    
    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5434, description="PostgreSQL port")
    user: str = Field(default="vesper", description="PostgreSQL user")
    password: str = Field(default="vesper", description="PostgreSQL password")
    db: str = Field(default="vesper", description="PostgreSQL database")
    
    @property
    def connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class ProcessingConfig(BaseSettings):
    """Document processing configuration"""
    
    model_config = SettingsConfigDict(
        env_prefix="PROCESSING_",
        env_file=".env",
        case_sensitive=False,
    )
    
    max_chunk_size: int = Field(
        default=1000,
        description="Maximum chunk size in tokens"
    )
    chunk_overlap: int = Field(
        default=200,
        description="Overlap between chunks in tokens"
    )
    min_section_length: int = Field(
        default=50,
        description="Minimum section length in characters"
    )
    remove_tables: bool = Field(
        default=False,
        description="Remove tables from text extraction"
    )
    extract_tables: bool = Field(
        default=True,
        description="Extract tables separately"
    )


class Config(BaseSettings):
    """Main configuration"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )
    
    s3: S3Config = Field(default_factory=S3Config)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )


def get_config() -> Config:
    """Get configuration instance"""
    return Config()
