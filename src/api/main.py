"""
SnapAnalyst FastAPI Application

Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

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
    
    # Initialize LLM service (chatbot) if training is enabled
    if settings.vanna_training_enabled:
        logger.info(f"Initializing LLM service with {settings.llm_provider}...")
        try:
            from src.services.llm_service import initialize_llm_service
            initialize_llm_service()
            logger.info("✅ LLM service initialized and trained successfully")
        except Exception as e:
            logger.warning(f"⚠️  LLM service initialization failed: {e}")
            logger.warning("Chatbot will initialize on first use")
    else:
        logger.info("LLM training disabled. Chatbot will use pre-trained model.")
    
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


# Health check endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - returns application information"""
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "environment": settings.environment,
        "docs_url": "/docs" if settings.is_development else "disabled",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "application": settings.app_name,
        "version": settings.app_version,
    }


# Import and include routers
from src.api.routers import data_loading, management, files, query, chatbot, schema, schema_exports, data_export, filter as filter_router, llm

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
