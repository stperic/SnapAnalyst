"""
SnapAnalyst FastAPI Application

Main FastAPI application entry point.
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

# Configure ONNX Runtime before any imports that might trigger ChromaDB/Vanna initialization
# CRITICAL: Explicitly set thread count to prevent CPU affinity errors in LXC containers
# When thread count is explicit, ONNX Runtime skips automatic CPU affinity (which fails in LXC)
# See: https://github.com/chroma-core/chroma/issues/1420
if not os.environ.get('OMP_NUM_THREADS') or os.environ.get('OMP_NUM_THREADS') == '0':
    os.environ['OMP_NUM_THREADS'] = '4'

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.logging import get_logger, setup_logging
from src.database.engine import init_db

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan context manager for FastAPI application.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    # Initialize database (create tables if they don't exist)
    if settings.is_development:
        logger.info("Development mode: Initializing database tables...")
        init_db()

    # Initialize LLM service (chatbot) - training always happens
    logger.info(f"Initializing LLM service with {settings.llm_provider}...")
    try:
        from src.services.llm_service import initialize_llm_service
        initialize_llm_service()
        logger.info("LLM service initialized and trained successfully")
    except Exception as e:
        logger.warning(f"LLM service initialization failed: {e}")
        logger.warning("Chatbot will initialize on first use")

    yield

    # Shutdown
    logger.info("Shutting down SnapAnalyst...")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="SNAP Quality Control data analysis platform with natural language query interface",
    version=settings.app_version,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - returns basic application information"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint for monitoring"""
    from datetime import datetime
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.get("/about", tags=["Info"])
async def about():
    """Detailed application information and service status"""
    from datetime import datetime

    # Check database health
    db_status = "healthy"
    try:
        from sqlalchemy import text

        from src.database.engine import SessionLocal
        session = SessionLocal()
        session.execute(text("SELECT 1"))
        session.close()
    except Exception:
        db_status = "unhealthy"

    # Check LLM health
    llm_status = "healthy"
    llm_provider = "unknown"
    llm_model = "unknown"
    try:
        from src.services.llm_service import get_llm_service
        llm_service = get_llm_service()
        health = llm_service.check_health()
        llm_status = "healthy" if health.get("healthy") else "unhealthy"
        llm_provider = health.get("provider", "unknown")
        llm_model = health.get("model", "unknown")
    except Exception:
        llm_status = "unhealthy"

    return {
        "application": {
            "name": settings.app_name,
            "description": "SNAP Quality Control data analysis platform with natural language query interface",
            "version": settings.app_version,
            "environment": settings.environment
        },
        "services": {
            "api": {
                "status": "healthy",
                "version": settings.app_version,
                "host": settings.api_host,
                "port": settings.api_port
            },
            "database": {
                "status": db_status,
                "type": "PostgreSQL",
                "url": str(settings.database_url).split('@')[1] if '@' in str(settings.database_url) else "configured"
            },
            "llm": {
                "status": llm_status,
                "provider": llm_provider,
                "model": llm_model
            }
        },
        "features": {
            "natural_language_queries": True,
            "sql_execution": True,
            "knowledge_base": True,
            "data_export": True,
            "filtering": True
        },
        "docs": {
            "api_docs": "/docs" if settings.is_development else None,
            "redoc": "/redoc" if settings.is_development else None
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


# Import and include routers (after app creation to avoid circular imports)
from src.api.routers import (  # noqa: E402
    chatbot,
    data_export,
    data_loading,
    files,
    llm,
    management,
    query,
    schema,
    schema_exports,
)
from src.api.routers import filter as filter_router  # noqa: E402

app.include_router(data_loading.router, prefix="/api/v1/data", tags=["Data Loading"])
app.include_router(management.router, prefix="/api/v1/data", tags=["Management"])
app.include_router(files.router, prefix="/api/v1/data", tags=["Files"])
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
app.include_router(chatbot.router, prefix="/api/v1/chat", tags=["Chatbot 🤖"])
app.include_router(schema.router, prefix="/api/v1/schema", tags=["Schema 📋"])
app.include_router(schema_exports.router, prefix="/api/v1/schema/export", tags=["Schema Export 📤"])
app.include_router(data_export.router, prefix="/api/v1/data", tags=["Data Export 📥"])
app.include_router(filter_router.router, prefix="/api/v1/filter", tags=["Filter 🔍"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["LLM Training 🧠"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        workers=settings.api_workers,
        log_level=settings.log_level.lower(),
    )
