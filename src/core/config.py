"""
SnapAnalyst Configuration Management
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, PostgresDsn, field_validator
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
    environment: str = Field(default="development", pattern="^(development|staging|production|test)$")
    debug: bool = False
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

    # CORS — set CORS_ORIGINS env var as comma-separated URLs
    # Default to localhost only; set to "*" explicitly in .env if you need wildcard
    cors_origins: list[str] = ["http://localhost:8001", "http://localhost:8000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 3600  # per hour

    # Monitoring & Logging
    sentry_dsn: str | None = None
    log_to_file: bool = True
    log_file_path: str = "./logs/snapanalyst.log"
    log_max_bytes: int = Field(default=10_000_000, description="Max log file size in bytes (default 10MB)")
    log_backup_count: int = Field(default=5, description="Number of backup log files to keep")

    # LLM Configuration
    llm_provider: str = Field(default="ollama", pattern="^(openai|anthropic|ollama|azure_openai)$")

    # Legacy/shared settings (used as defaults if specific settings not provided)
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2000, ge=100, le=8000)

    # SQL Generation settings (LLM_SQL_*)
    llm_sql_model: str | None = None  # Model for SQL generation
    llm_sql_max_tokens: int | None = Field(
        default=None, ge=100, le=8000, description="Max tokens for SQL generation (defaults to llm_max_tokens)"
    )
    llm_sql_temperature: float | None = Field(
        default=None, ge=0.0, le=2.0, description="Temperature for SQL generation (defaults to llm_temperature)"
    )

    # Knowledge Base / Insight settings (LLM_KB_*)
    llm_kb_model: str | None = None  # Model for KB/insight generation
    llm_kb_max_tokens: int = Field(default=1000, ge=50, le=8000, description="Max response tokens for insights")
    llm_kb_max_data_size: int = Field(
        default=50000, ge=1000, le=500000, description="Max chars for previous query data in insights"
    )
    llm_kb_max_prompt_size: int = Field(
        default=100000, ge=1000, le=500000, description="Total max prompt size (chars) for KB insights"
    )
    llm_kb_temperature: float | None = Field(
        default=0.3, ge=0.0, le=2.0, description="Temperature for KB insights (higher for more natural summaries)"
    )

    # SQL Result AI Summary settings
    llm_sql_summary_enabled: bool = Field(
        default=True, description="Enable AI-powered summaries for SQL query results"
    )
    llm_sql_summary_max_rows: int = Field(
        default=50, ge=1, le=500, description="Max result rows sent to LLM for AI summary"
    )

    # Vanna RAG retrieval counts
    vanna_n_results_sql: int = Field(
        default=10, ge=1, le=50, description="Number of SQL example pairs retrieved from ChromaDB"
    )
    vanna_n_results_docs: int = Field(
        default=10, ge=1, le=50, description="Number of documentation chunks retrieved from ChromaDB"
    )

    # Query Result Settings
    max_result_columns: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of columns to return in query results (for SELECT * queries)",
    )

    # API Keys (Optional - required based on provider)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Azure OpenAI Configuration (optional - only if using Azure OpenAI-compatible endpoint)
    azure_openai_endpoint: str | None = None  # e.g., "https://your-resource.cognitiveservices.azure.com/openai/v1/"
    azure_openai_api_key: str | None = None

    # Vanna Configuration
    #
    # 1. INITIAL TRAINING (Always enabled - required for Vanna to work)
    #    - Trains on: DDL, schemas, reference data, business context
    #    - When: Automatically during data initialization
    #    - No configuration needed (happens automatically)
    #
    # 2. ONGOING TRAINING (Optional - continuous learning from user queries)
    #    - Trains on: User questions + generated SQL pairs
    #    - When: After EVERY successful query (if enabled)
    #    - How: Stores (question, sql) pair in ChromaDB via vanna.train()
    #    - Benefit: Future similar questions use past queries as examples
    #    - Risk: All user questions stored (privacy concern)
    #    - Controlled by: VANNA_STORE_USER_QUERIES flag below

    vanna_store_user_queries: bool = True  # Feedback-driven training: thumbs up/down trains Vanna

    # SQL training data folder — all .md/.txt loaded as documentation, all .json as question/SQL pairs
    sql_training_data_path: str = "./datasets/snap/training"
    vanna_chromadb_path: str = "./chromadb"  # ChromaDB vector store location

    # System prompts folder — sql_system_prompt.txt, kb_system_prompt.txt
    system_prompts_path: str = "./datasets/snap/prompts"

    # Multi-Dataset Configuration
    # Supports multiple datasets with different schemas (e.g., public SNAP + state private data)
    active_dataset: str = "snap"  # Default dataset (backward compatible)
    dataset_schema_isolation: bool = False  # If True, use PostgreSQL schemas for isolation

    @property
    def resolved_data_path(self) -> str:
        """Resolve data path from active dataset, falling back to snapdata_path."""
        if self.snapdata_path != "./datasets/snap/data":
            return self.snapdata_path  # User override
        try:
            from datasets import get_active_dataset

            ds = get_active_dataset()
            if ds:
                return str(ds.base_path / "data")
        except Exception:
            pass
        return self.snapdata_path

    @property
    def resolved_training_path(self) -> str:
        """Resolve training data path from active dataset, falling back to sql_training_data_path."""
        if self.sql_training_data_path != "./datasets/snap/training":
            return self.sql_training_data_path  # User override
        try:
            from datasets import get_active_dataset

            ds = get_active_dataset()
            if ds:
                return str(ds.base_path / "training")
        except Exception:
            pass
        return self.sql_training_data_path

    @property
    def resolved_prompts_path(self) -> str:
        """Resolve prompts path from active dataset, falling back to system_prompts_path."""
        if self.system_prompts_path != "./datasets/snap/prompts":
            return self.system_prompts_path  # User override
        try:
            from datasets import get_active_dataset

            ds = get_active_dataset()
            if ds:
                return str(ds.base_path / "prompts")
        except Exception:
            pass
        return self.system_prompts_path

    @property
    def data_path(self) -> str:
        """Alias for resolved_data_path (backward compatible)."""
        return self.resolved_data_path

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == "production"

    @property
    def sql_model(self) -> str:
        """Get model for SQL generation"""
        if self.llm_sql_model:
            return self.llm_sql_model
        defaults = {
            "openai": "gpt-4.1",
            "azure_openai": "gpt-4.1",
            "anthropic": "claude-sonnet-4-20250514",
            "ollama": "llama3.1:8b",
        }
        return defaults.get(self.llm_provider, "gpt-4.1")

    @property
    def kb_model(self) -> str:
        """Get model for KB/insight generation"""
        if self.llm_kb_model:
            return self.llm_kb_model
        defaults = {
            "openai": "gpt-4.1-mini",
            "azure_openai": "gpt-4.1-mini",
            "anthropic": "claude-haiku-4-5-20251001",
            "ollama": "llama3.1:8b",
        }
        return defaults.get(self.llm_provider, "gpt-4.1-mini")

    @property
    def effective_sql_max_tokens(self) -> int:
        """Get effective max tokens for SQL generation"""
        return self.llm_sql_max_tokens if self.llm_sql_max_tokens is not None else self.llm_max_tokens

    @property
    def effective_sql_temperature(self) -> float:
        """Get effective temperature for SQL generation"""
        return self.llm_sql_temperature if self.llm_sql_temperature is not None else self.llm_temperature

    @property
    def effective_kb_temperature(self) -> float:
        """Get effective temperature for KB/insight generation"""
        return self.llm_kb_temperature if self.llm_kb_temperature is not None else self.llm_temperature


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses LRU cache to ensure settings are loaded once and reused.
    """
    import logging

    _settings = Settings()

    # Warn about wildcard CORS in production
    if _settings.is_production and "*" in _settings.cors_origins:
        logging.getLogger(__name__).warning(
            "CORS is set to wildcard ('*') in production. Set CORS_ORIGINS to specific origins for better security."
        )

    # Warn about default SECRET_KEY
    if _settings.secret_key in ("change-this-to-a-secure-random-string", "change-this-in-production"):
        logging.getLogger(__name__).warning(
            "SECRET_KEY is set to a default placeholder value. Generate a secure random key for production use."
        )

    return _settings


# Global settings instance
settings = get_settings()
