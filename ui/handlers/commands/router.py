"""
Command Router

Routes slash commands to appropriate handler modules.
Only /clear remains as a slash command.
User-facing settings are accessed via the Settings toolbar button.
"""

from ...responses import send_message
from .utility_commands import (
    handle_clear,
)


async def handle_command(command: str, args: str | None = None):
    """
    Route slash commands to appropriate handlers.

    Args:
        command: The command (e.g., "/clear")
        args: Optional arguments after the command
    """
    handlers = {
        "/clear": lambda: handle_clear(),
    }

    handler = handlers.get(command)
    if handler:
        await handler()
    else:
        await send_message(
            f"Unknown command: `{command}`. Use the **Settings** button to access filters, LLM, knowledge, and database options."
        )
