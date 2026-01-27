"""
UI Package for SnapAnalyst Chainlit Application

This package contains ONLY UI-related code for the Chainlit interface.
Business logic and services are in the src/ package.

Structure:
- config.py: UI-specific constants (persona, display settings)
- formatters.py: HTML/display formatting utilities
- responses.py: Message templates with persona
- handlers/: Chainlit event routing and UI logic

For business logic, see:
- src/clients/: API client
- src/services/: Business services (AI summary, code enrichment)
- src/utils/: Utilities (SQL validation)
"""

from .config import APP_PERSONA, MAX_DISPLAY_ROWS

__all__ = [
    "APP_PERSONA",
    "MAX_DISPLAY_ROWS",
]
