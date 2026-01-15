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

from src.core.config import settings, get_settings
from src.core.logging import get_logger, setup_logging, create_rotating_file_handler, get_llm_logger
