"""
SnapAnalyst Logging Configuration
"""
import logging
import sys
from pathlib import Path
from typing import Optional

from src.core.config import settings


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Configure application logging.
    
    Args:
        log_level: Override log level from settings
    """
    level = log_level or settings.log_level
    
    # Create logs directory if logging to file
    if settings.log_to_file:
        log_path = Path(settings.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    # Add file handler if configured
    if settings.log_to_file:
        file_handler = logging.FileHandler(settings.log_file_path)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(file_handler)
    
    # Set specific log levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logging.info(f"SnapAnalyst logging initialized at {level} level")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Module name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
