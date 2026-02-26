"""
SnapAnalyst FastAPI Application

Main FastAPI application entry point.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

# Configure ONNX Runtime before any imports that might trigger ChromaDB/Vanna initialization
# CRITICAL: Explicitly set thread count to prevent CPU affinity errors in LXC containers
# When thread count is explicit, ONNX Runtime skips automatic CPU affinity (which fails in LXC)
# See: https://github.com/chroma-core/chroma/issues/1420
if not os.environ.get("OMP_NUM_THREADS") or os.environ.get("OMP_NUM_THREADS") == "0":
    os.environ["OMP_NUM_THREADS"] = "4"

# Suppress noisy library warnings before imports
import warnings

warnings.filterwarnings("ignore", message="urllib3.*doesn't match a supported version")

import logging as _logging  # noqa: E402

# Suppress config warnings until proper logging is set up
_logging.getLogger("src.core.config").setLevel(_logging.ERROR)

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.core.logging import get_logger, setup_logging  # noqa: E402

# Initialize logging (restores src.core.config to inherited level)
setup_logging()
_logging.getLogger("src.core.config").setLevel(_logging.WARNING)
logger = get_logger(__name__)

from src.database.engine import init_db  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan context manager for FastAPI application.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version} ({settings.environment})")

    # Initialize database (create tables if they don't exist)
    if settings.is_development:
        logger.debug("Development mode: Initializing database tables...")
        init_db()

    # Initialize LLM service (chatbot) - training always happens
    try:
        from src.services.llm_service import initialize_llm_service

        initialize_llm_service()
    except Exception as e:
        logger.warning(f"LLM service initialization failed: {e} (will retry on first use)")

    yield

    # Shutdown with timeout to prevent hanging on Ctrl+C / docker stop
    logger.info("Shutting down SnapAnalyst...")
    try:
        from src.database.engine import dispose_engines

        await asyncio.wait_for(asyncio.to_thread(dispose_engines), timeout=5.0)
    except TimeoutError:
        logger.warning("Engine disposal timed out after 5s, forcing exit")
    except Exception as e:
        logger.warning(f"Error during shutdown: {e}")

    # Close Vanna's psycopg2 connection pool (moved from atexit to avoid
    # blocking indefinitely when connections are checked out at SIGTERM)
    try:
        from src.services.llm_providers import shutdown_db_pool

        await asyncio.wait_for(asyncio.to_thread(shutdown_db_pool), timeout=3.0)
    except TimeoutError:
        logger.warning("DB pool shutdown timed out after 3s, forcing exit")
    except Exception as e:
        logger.warning(f"Error shutting down DB pool: {e}")


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


# Add user context middleware for multi-user safety
@app.middleware("http")
async def add_user_context_middleware(request: Request, call_next):
    """
    Middleware to extract and set user context for each request.

    THREAD-SAFE: Uses ContextVar to store user_id per-request.
    This ensures FilterManager and other services can identify the current user
    without mixing data between concurrent requests.

    User identification sources (in order of priority):
    1. X-User-ID header (for API clients with authentication)
    2. Authorization header parsing (for JWT/Bearer tokens)
    3. "default" fallback (for unauthenticated requests)

    Args:
        request: FastAPI Request object
        call_next: Next middleware/handler in chain

    Returns:
        Response from downstream handlers
    """
    from src.api.dependencies import set_request_user

    # Extract user ID from headers
    user_id = request.headers.get("X-User-ID")

    if not user_id:
        # Try to extract from Authorization header (JWT/Bearer token)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # TODO: Implement JWT token parsing to extract user_id
            # For now, use a placeholder
            token = auth_header.replace("Bearer ", "")
            user_id = f"token_{token[:8]}"  # Placeholder

    # Fallback to default if no user identification
    if not user_id:
        user_id = "default"

    # Set user context for this request
    set_request_user(user_id)
    logger.debug(f"Request user context set: {user_id}")

    # Process request with cleanup guarantee
    try:
        response = await call_next(request)
        return response
    finally:
        # Clean up context after request completes
        set_request_user(None)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - returns basic application information"""
    return {"name": settings.app_name, "version": settings.app_version, "status": "running"}


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint for monitoring"""
    from datetime import UTC, datetime

    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


@app.get("/about", tags=["Info"])
async def about():
    """Detailed application information and service status"""
    from datetime import UTC, datetime

    # Check database health
    db_status = "healthy"
    try:
        from sqlalchemy import text

        from src.database.engine import SessionLocal

        session = SessionLocal()
        try:
            session.execute(text("SELECT 1"))
        finally:
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
            "environment": settings.environment,
        },
        "services": {
            "api": {
                "status": "healthy",
                "version": settings.app_version,
                "host": settings.api_host,
                "port": settings.api_port,
            },
            "database": {
                "status": db_status,
                "type": "PostgreSQL",
                "url": str(settings.database_url).split("@")[1] if "@" in str(settings.database_url) else "configured",
            },
            "llm": {"status": llm_status, "provider": llm_provider, "model": llm_model},
        },
        "features": {
            "natural_language_queries": True,
            "sql_execution": True,
            "knowledge_base": True,
            "data_export": True,
            "filtering": True,
        },
        "docs": {
            "api_docs": "/docs" if settings.is_development else None,
            "redoc": "/redoc" if settings.is_development else None,
        },
        "timestamp": datetime.now(UTC).isoformat(),
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
