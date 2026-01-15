"""
SnapAnalyst Database Engine and Session Management

Supports multi-dataset architecture with optional PostgreSQL schema isolation.
Each dataset can have its own schema (namespace) in PostgreSQL.

Usage:
    # Default engine (uses active dataset schema)
    from src.database.engine import engine, get_db
    
    # Get engine for specific dataset
    from src.database.engine import get_engine_for_dataset
    engine = get_engine_for_dataset("snap")
"""
from contextlib import contextmanager
from typing import Generator, Optional, Dict

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# Base class for all models
Base = declarative_base()

# Cache for dataset-specific engines
_dataset_engines: Dict[str, Engine] = {}


def _create_engine(schema_name: Optional[str] = None) -> Engine:
    """
    Create a SQLAlchemy engine, optionally configured for a specific schema.
    
    Args:
        schema_name: PostgreSQL schema to use (None for default/public)
        
    Returns:
        Configured SQLAlchemy Engine
    """
    connect_args: Dict[str, str] = {}
    
    # If schema isolation is enabled and schema specified, set search path
    if settings.dataset_schema_isolation and schema_name and schema_name != "public":
        connect_args["options"] = f"-c search_path={schema_name},public"
    
    # Build engine kwargs - only include connect_args if non-empty
    engine_kwargs = {
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_timeout": settings.database_pool_timeout,
        "pool_recycle": settings.database_pool_recycle,
        "echo": settings.debug,  # Log SQL queries in debug mode
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


def drop_all_tables() -> None:
    """Drop all tables - USE WITH CAUTION"""
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped")
