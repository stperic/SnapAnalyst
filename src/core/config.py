"""
SnapAnalyst Configuration Management
"""
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
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

    # Redis Configuration
    redis_url: RedisDsn
    redis_password: Optional[str] = None

    # Celery Configuration
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    @field_validator("celery_broker_url", "celery_result_backend", mode="before")
    @classmethod
    def default_to_redis(cls, v: Optional[str], info) -> str:
        """Default Celery URLs to Redis URL if not provided"""
        if v is None and info.data.get("redis_url"):
            return str(info.data["redis_url"])
        return v or ""

    # Data Configuration
    snapdata_path: str = "./snapdata"
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

    # LLM Configuration
    llm_provider: str = Field(default="ollama", pattern="^(openai|anthropic|ollama)$")
    llm_model: Optional[str] = None  # Auto-selected based on provider if not set
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2000, ge=100, le=8000)
    
    # API Keys (Optional - required based on provider)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    
    # Vanna Configuration
    vanna_training_enabled: bool = False  # DISABLED: Was causing 10+ second API startup hangs
    vanna_training_data_path: str = "./query_examples.json"
    vanna_schema_path: str = "./data_mapping.json"

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
        """Get default model based on provider"""
        defaults = {
            "openai": "gpt-4-turbo-preview",
            "anthropic": "claude-3-5-sonnet-20241022",
            "ollama": "llama3.1:8b"
        }
        return self.llm_model or defaults.get(self.llm_provider, "llama3.1:8b")


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses LRU cache to ensure settings are loaded once and reused.
    """
    return Settings()


# Global settings instance
settings = get_settings()
