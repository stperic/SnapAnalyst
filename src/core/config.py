"""
SnapAnalyst Configuration Management
"""
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "SnapAnalyst"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = True
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False  # Disabled auto-reload to prevent performance issues
    api_workers: int = 1

    # Database Configuration
    database_url: PostgresDsn
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600

    # Data Configuration
    # Default data path (overridden by active dataset config)
    snapdata_path: str = "./datasets/snap/data"
    backup_path: str = "./backups"
    max_upload_size_mb: int = 500

    # ETL Configuration
    etl_batch_size: int = 1000
    etl_max_workers: int = 4
    etl_validation_strict: bool = True

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 3600  # per hour

    # Monitoring & Logging
    sentry_dsn: Optional[str] = None
    log_to_file: bool = True
    log_file_path: str = "./logs/snapanalyst.log"
    log_max_bytes: int = Field(default=10_000_000, description="Max log file size in bytes (default 10MB)")
    log_backup_count: int = Field(default=5, description="Number of backup log files to keep")

    # LLM Configuration
    llm_provider: str = Field(default="ollama", pattern="^(openai|anthropic|ollama)$")
    llm_model: Optional[str] = None  # Auto-selected based on provider if not set (legacy)
    
    # Legacy/shared settings (used as defaults if specific settings not provided)
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2000, ge=100, le=8000)
    
    # SQL Generation settings (LLM_SQL_*)
    llm_sql_model: Optional[str] = None  # Model for SQL generation
    llm_sql_max_tokens: Optional[int] = Field(default=None, ge=100, le=8000, description="Max tokens for SQL generation (defaults to llm_max_tokens)")
    llm_sql_temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Temperature for SQL generation (defaults to llm_temperature)")
    
    # Summary Generation settings (LLM_SUMMARY_*)
    llm_summary_model: Optional[str] = None  # Model for summary generation
    llm_summary_max_tokens: int = Field(default=200, ge=50, le=1000, description="Max tokens for summary generation")
    llm_summary_max_prompt_size: int = Field(default=8000, ge=1000, le=50000, description="Max prompt size (chars) for summary generation before fallback")
    llm_summary_temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Temperature for summary generation (defaults to llm_temperature)")
    
    # API Keys (Optional - required based on provider)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    
    # Vanna Configuration
    vanna_training_enabled: bool = False  # DISABLED: Was causing 10+ second API startup hangs
    # Paths are now dataset-relative (see datasets/snap/)
    vanna_training_data_path: str = "./datasets/snap/query_examples.json"
    vanna_schema_path: str = "./datasets/snap/data_mapping.json"
    vanna_chromadb_path: str = "./chromadb"  # ChromaDB vector store location
    
    # Multi-Dataset Configuration
    # Supports multiple datasets with different schemas (e.g., public SNAP + state private data)
    active_dataset: str = "snap"  # Default dataset (backward compatible)
    dataset_schema_isolation: bool = False  # If True, use PostgreSQL schemas for isolation

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == "production"
    
    @property
    def default_llm_model(self) -> str:
        """Get default model based on provider (legacy - use sql or summary specific)"""
        defaults = {
            "openai": "gpt-4-turbo-preview",
            "anthropic": "claude-3-5-sonnet-20241022",
            "ollama": "llama3.1:8b"
        }
        return self.llm_model or defaults.get(self.llm_provider, "llama3.1:8b")
    
    @property
    def sql_model(self) -> str:
        """Get model for SQL generation"""
        if self.llm_sql_model:
            return self.llm_sql_model
        # Default to more powerful models for SQL generation
        defaults = {
            "openai": "gpt-4-turbo-preview",
            "anthropic": "claude-3-5-sonnet-20241022",
            "ollama": "llama3.1:8b"
        }
        return defaults.get(self.llm_provider, "gpt-4-turbo-preview")
    
    @property
    def summary_model(self) -> str:
        """Get model for summary generation"""
        if self.llm_summary_model:
            return self.llm_summary_model
        # Default to faster/cheaper models for summaries
        defaults = {
            "openai": "gpt-3.5-turbo",
            "anthropic": "claude-3-5-haiku-20241022",
            "ollama": "llama3.1:8b"
        }
        return defaults.get(self.llm_provider, "gpt-3.5-turbo")
    
    @property
    def effective_sql_max_tokens(self) -> int:
        """Get effective max tokens for SQL generation"""
        return self.llm_sql_max_tokens if self.llm_sql_max_tokens is not None else self.llm_max_tokens
    
    @property
    def effective_sql_temperature(self) -> float:
        """Get effective temperature for SQL generation"""
        return self.llm_sql_temperature if self.llm_sql_temperature is not None else self.llm_temperature
    
    @property
    def effective_summary_temperature(self) -> float:
        """Get effective temperature for summary generation"""
        return self.llm_summary_temperature if self.llm_summary_temperature is not None else self.llm_temperature


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses LRU cache to ensure settings are loaded once and reused.
    """
    return Settings()


# Global settings instance
settings = get_settings()
