"""
SnapAnalyst Logging Configuration

Provides centralized logging with:
- Console output
- Rotating file logs (prevents logs from growing too large)
- Configurable size limits and backup counts
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.core.config import settings

# Default log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def create_rotating_file_handler(
    log_path: str,
    max_bytes: int = None,
    backup_count: int = None,
    level: int = logging.DEBUG
) -> RotatingFileHandler:
    """
    Create a rotating file handler with size limits.

    Args:
        log_path: Path to the log file
        max_bytes: Maximum size per log file (default from settings)
        backup_count: Number of backup files to keep (default from settings)
        level: Logging level for this handler

    Returns:
        Configured RotatingFileHandler
    """
    # Use settings defaults if not specified
    max_bytes = max_bytes or settings.log_max_bytes
    backup_count = backup_count or settings.log_backup_count

    # Ensure directory exists
    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.setLevel(level)

    return handler


def setup_logging(log_level: str | None = None) -> None:
    """
    Configure application logging with rotation.

    Args:
        log_level: Override log level from settings
    """
    level = log_level or settings.log_level

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level),
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )

    # Add rotating file handler if configured
    if settings.log_to_file:
        file_handler = create_rotating_file_handler(
            settings.log_file_path,
            level=getattr(logging, level)
        )
        logging.getLogger().addHandler(file_handler)

    # Set specific log levels for noisy libraries
    # Suppress verbose HTTP/database logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Suppress WebSocket/Socket.io noise (ping/pong, connection headers)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("websockets.protocol").setLevel(logging.WARNING)
    logging.getLogger("websockets.server").setLevel(logging.WARNING)
    logging.getLogger("engineio").setLevel(logging.WARNING)
    logging.getLogger("engineio.server").setLevel(logging.WARNING)
    logging.getLogger("socketio").setLevel(logging.WARNING)
    logging.getLogger("socketio.server").setLevel(logging.WARNING)

    # Suppress Chainlit internal noise
    logging.getLogger("chainlit").setLevel(logging.INFO)
    logging.getLogger("chainlit.socket").setLevel(logging.WARNING)
    logging.getLogger("chainlit.data.sql_alchemy").setLevel(logging.ERROR)  # Suppress blob storage warnings

    # Suppress ML/Vector DB noise
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("chromadb.telemetry").setLevel(logging.ERROR)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("ollama").setLevel(logging.WARNING)

    # Suppress Vanna verbose prompt/response logging
    logging.getLogger("vanna").setLevel(logging.ERROR)
    logging.getLogger("vanna.openai").setLevel(logging.ERROR)
    logging.getLogger("vanna.anthropic").setLevel(logging.ERROR)
    logging.getLogger("vanna.chromadb").setLevel(logging.ERROR)
    logging.getLogger("vanna.base").setLevel(logging.ERROR)
    logging.getLogger("vanna.legacy").setLevel(logging.ERROR)

    # Suppress other noisy libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.info(
        f"SnapAnalyst logging initialized at {level} level "
        f"(rotation: {settings.log_max_bytes / 1_000_000:.1f}MB, "
        f"keeping {settings.log_backup_count} backups)"
    )


def setup_api_logging(log_path: str = "./logs/api.log") -> logging.Logger:
    """
    Set up a dedicated logger for API requests with rotation.

    Args:
        log_path: Path to the API log file

    Returns:
        Configured logger for API
    """
    logger = logging.getLogger("api")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        handler = create_rotating_file_handler(log_path)
        logger.addHandler(handler)

    return logger


def setup_llm_logging(log_path: str = "./logs/llm.log") -> logging.Logger:
    """
    Set up a dedicated logger for LLM interactions with rotation.

    Logs all LLM calls including:
    - SQL generation requests and responses
    - Summary generation requests and responses
    - Errors and timing information

    Args:
        log_path: Path to the LLM log file

    Returns:
        Configured logger for LLM
    """
    logger = logging.getLogger("llm")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        handler = create_rotating_file_handler(log_path, level=logging.INFO)
        logger.addHandler(handler)

    return logger


def get_llm_logger() -> logging.Logger:
    """
    Get the LLM logger instance, initializing if needed.

    Returns:
        Logger instance for LLM logging
    """
    logger = logging.getLogger("llm")

    # Initialize if no handlers configured
    if not logger.handlers:
        setup_llm_logging()

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
