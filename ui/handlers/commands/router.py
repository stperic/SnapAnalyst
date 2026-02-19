"""
Command Router

Routes slash commands to appropriate handler modules.
Replaces the monolithic commands.py file with modular organization.
"""


from ...responses import send_message

# Import command handlers from modules
from .data_commands import (
    handle_files,
    handle_load,
    handle_reset,
    handle_upload,
)
from .info_commands import (
    handle_database,
    handle_help,
    handle_history,
    handle_llm,
    handle_schema,
    handle_status,
)
from .memory_commands import (
    handle_mem_command,
)
from .memsql_commands import (
    handle_memsql_command,
)
from .prompt_commands import (
    handle_prompt_command,
)
from .utility_commands import (
    handle_clear,
    handle_export,
    handle_filter,
)


async def handle_command(command: str, args: str | None = None):
    """
    Route slash commands to appropriate handlers.

    Args:
        command: The command (e.g., "/help")
        args: Optional arguments after the command
    """
    # Map commands to their handlers
    handlers = {
        # Info commands
        "/help": lambda: handle_help(),
        "/status": lambda: handle_status(),
        "/database": lambda: handle_database(),
        "/stats": lambda: handle_database(),  # Alias for /database
        "/schema": lambda: handle_schema(),
        "/llm": lambda: handle_llm(),
        "/history": lambda: handle_history(),

        # Data commands
        "/load": lambda: handle_load(args),
        "/files": lambda: handle_files(),
        "/upload": lambda: handle_upload(),
        "/reset": lambda: handle_reset(),

        # Utility commands
        "/export": lambda: handle_export(args),
        "/filter": lambda: handle_filter(args),
        "/clear": lambda: handle_clear(),

        # Memory commands
        "/mem": lambda: handle_mem_command(args),

        # Vanna SQL training commands
        "/memsql": lambda: handle_memsql_command(args),

        # Prompt commands
        "/prompt": lambda: handle_prompt_command(args),
    }

    handler = handlers.get(command)
    if handler:
        await handler()
    else:
        await send_message(f"❌ Unknown command: `{command}`. Type `/help` for available commands.")
