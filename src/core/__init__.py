"""
Core Package

Application configuration, logging, and core utilities.

Modules:
- config: Settings management (Pydantic)
- logging: Structured logging setup
- prompts: LLM prompts and templates
- filter_manager: Data filtering logic
- exceptions: Custom exception classes
"""

from src.core.config import get_settings, settings
from src.core.logging import create_rotating_file_handler, get_llm_logger, get_logger, setup_logging

__all__ = [
    "get_settings",
    "settings",
    "create_rotating_file_handler",
    "get_llm_logger",
    "get_logger",
    "setup_logging",
]
