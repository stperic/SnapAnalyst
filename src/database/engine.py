"""
SnapAnalyst Database Engine and Session Management

Schema Organization:
- public: SNAP QC domain data (households, members, errors, reference tables)
- app: Application data (user prompts, load history)
- Custom schemas: User-created datasets (e.g., state_ca, custom_data)

Default search_path: public, app
This allows queries without schema qualification for SNAP QC data.

Usage:
    from src.database.engine import engine, get_db

    # Queries automatically search: public → app
    result = session.execute(text("SELECT * FROM households"))
"""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# Base class for all models
Base = declarative_base()

# Cache for dataset-specific engines
_dataset_engines: dict[str, Engine] = {}


def _create_engine(schema_name: str | None = None) -> Engine:
    """
    Create a SQLAlchemy engine with proper schema search_path.

    Sets search_path to: public, app
    SNAP QC data in public schema (default, no qualification needed)
    System data in app schema (user prompts, load history)
    Custom datasets in user-created schemas (optional)

    Args:
        schema_name: Optional schema override (kept for backward compatibility)

    Returns:
        Configured SQLAlchemy Engine with schema search_path
    """
    connect_args: dict[str, str] = {}

    # Set search_path: public (SNAP QC), app (system data)
    # This allows unqualified table names for SNAP QC tables
    connect_args["options"] = "-c search_path=public,app"

    # Build engine kwargs with performance optimizations
    engine_kwargs = {
        # Connection pooling - optimized for bulk operations
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_timeout": settings.database_pool_timeout,
        "pool_recycle": settings.database_pool_recycle,

        # Performance optimizations
        "pool_pre_ping": True,  # Verify connections on checkout (handles DB restarts)
        "echo": False,  # Never echo SQL to stdout; use sqlalchemy.engine logger instead

        # PostgreSQL-specific optimizations for bulk inserts
        "executemany_mode": "values_plus_batch",  # Use fast batch mode for executemany
    }

    if connect_args:
        engine_kwargs["connect_args"] = connect_args

    return create_engine(str(settings.database_url), **engine_kwargs)


# Create default engine (backward compatible - uses public schema)
engine = _create_engine()

# Create session factory (bound to default engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_engine_for_dataset(dataset_name: str) -> Engine:
    """
    Get or create an engine configured for a specific dataset's schema.

    This enables schema isolation when dataset_schema_isolation is enabled.
    Each dataset can have tables in its own PostgreSQL schema.

    Args:
        dataset_name: Name of the dataset (e.g., 'snap', 'state_private')

    Returns:
        SQLAlchemy Engine configured for the dataset's schema

    Example:
        engine = get_engine_for_dataset('snap')
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM households LIMIT 1"))
    """
    global _dataset_engines

    # Return cached engine if available
    if dataset_name in _dataset_engines:
        return _dataset_engines[dataset_name]

    # Get schema name from dataset config
    schema_name = "public"  # Default

    try:
        from datasets import get_dataset
        dataset_config = get_dataset(dataset_name)
        if dataset_config:
            schema_name = dataset_config.schema_name
    except ImportError:
        logger.debug("datasets module not available, using public schema")

    # Create and cache engine
    dataset_engine = _create_engine(schema_name)
    _dataset_engines[dataset_name] = dataset_engine

    return dataset_engine


def get_active_engine() -> Engine:
    """
    Get the engine for the currently active dataset.

    Uses the active_dataset setting from configuration.

    Returns:
        SQLAlchemy Engine for active dataset
    """
    return get_engine_for_dataset(settings.active_dataset)


def get_session_for_dataset(dataset_name: str) -> sessionmaker:
    """
    Get a session factory for a specific dataset.

    Args:
        dataset_name: Name of the dataset

    Returns:
        sessionmaker bound to the dataset's engine
    """
    dataset_engine = get_engine_for_dataset(dataset_name)
    return sessionmaker(autocommit=False, autoflush=False, bind=dataset_engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database session.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database session.

    Usage:
        with get_db_context() as db:
            # use db session

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()


def init_db() -> None:
    """Initialize database - create all tables"""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def dispose_engines() -> None:
    """Dispose all SQLAlchemy engines and release connection pools."""
    global _dataset_engines
    engine.dispose()
    for ds_engine in _dataset_engines.values():
        ds_engine.dispose()
    _dataset_engines.clear()
    logger.info("All database engines disposed")


def drop_all_tables() -> None:
    """Drop all tables - USE WITH CAUTION"""
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped")
