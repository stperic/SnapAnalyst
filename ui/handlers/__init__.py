"""
Handlers Package

Contains Chainlit event handlers and UI routing logic.
Business logic is delegated to src/ services.

- commands.py: Slash command handlers (/help, /load, /schema, etc.)
- queries.py: Natural language query processing
- actions.py: Action button callbacks (CSV, reset, load file)
- settings.py: Settings update handlers
"""

from .commands import handle_command
from .queries import handle_chat_query
from .actions import (
    handle_csv_download,
    handle_execute,
    handle_cancel,
    handle_followup,
    handle_reset_confirm,
    handle_reset_cancel,
    handle_file_load,
)
from .settings import handle_settings_update
