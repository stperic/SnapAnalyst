"""
Handlers Package

Contains Chainlit event handlers and UI routing logic.
Business logic is delegated to src/ services.

- commands/: Slash command handlers organized by category
- queries.py: Natural language query processing
- actions.py: Action button callbacks (CSV, reset, load file)
- settings.py: Settings update handlers
"""

from .actions import (
    handle_cancel,
    handle_csv_download,
    handle_execute,
    handle_file_load,
    handle_followup,
    handle_reset_cancel,
    handle_reset_confirm,
)
from .commands import handle_command
from .queries import handle_chat_query, handle_insight_request
from .settings import handle_settings_update

__all__ = [
    "handle_cancel",
    "handle_csv_download",
    "handle_execute",
    "handle_file_load",
    "handle_followup",
    "handle_reset_cancel",
    "handle_reset_confirm",
    "handle_command",
    "handle_chat_query",
    "handle_insight_request",
    "handle_settings_update",
]
