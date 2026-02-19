"""
Prompt Management Commands

Handlers for /prompt command to view LLM prompts.
Prompt updates and resets are now done via /mem and /memsql sidebar panels.
"""

import logging

import chainlit as cl

from src.database.prompt_manager import (
    get_user_prompt,
    has_custom_prompt,
)
from ui.responses import send_error, send_message

logger = logging.getLogger(__name__)


async def handle_prompt_command(args: str | None = None):
    """
    View LLM prompts.

    Usage:
      /prompt sql   Show current SQL prompt
      /prompt kb    Show current KB prompt

    To update or reset prompts, use the /memsql or /mem sidebar panels.
    """
    if not args:
        await send_error(
            "**Usage:** `/prompt <sql|kb>`\n\n"
            "**Examples:**\n"
            "- `/prompt sql` - Show current SQL generation prompt\n"
            "- `/prompt kb` - Show current KB insight prompt\n\n"
            "**To update or reset prompts:**\n"
            "- Use `/memsql` panel for SQL prompts\n"
            "- Use `/mem` panel for KB prompts"
        )
        return

    parts = args.split(maxsplit=2)
    prompt_type = parts[0].lower()

    if prompt_type not in ["sql", "kb"]:
        await send_error(
            f"Invalid prompt type: `{prompt_type}`\n\n"
            "Use **sql** (for SQL generation) or **kb** (for insights)"
        )
        return

    if len(parts) == 1:
        await show_current_prompt(prompt_type)
        return

    action = parts[1].lower()

    if action in ("set", "reset"):
        panel = "/memsql" if prompt_type == "sql" else "/mem"
        await send_message(
            f"Prompt updates are now managed via the **{panel}** sidebar panel.\n\n"
            f"Type `{panel}` to open it, then use the **System Prompt** section."
        )
        return

    await send_error(
        f"Unknown action: `{action}`\n\n"
        "Use `/prompt sql` or `/prompt kb` to view prompts.\n"
        "Use `/memsql` or `/mem` panels to update or reset."
    )


async def show_current_prompt(prompt_type: str):
    """Show user's current prompt (custom or default)."""
    user = cl.user_session.get("user")
    if not user:
        await send_error("User session not found")
        return

    user_id = user.identifier
    prompt_text = get_user_prompt(user_id, prompt_type)
    is_custom = has_custom_prompt(user_id, prompt_type)

    prompt_name = "SQL Generation" if prompt_type == "sql" else "KB Insight"
    status = "custom" if is_custom else "default"
    char_count = len(prompt_text)
    line_count = prompt_text.count('\n') + 1
    panel = "/memsql" if prompt_type == "sql" else "/mem"

    content = f"""### Current {prompt_name} Prompt ({status})

**Stats:** {char_count:,} characters, {line_count} lines

`````
{prompt_text}
`````

**To modify:** Use the `{panel}` panel (System Prompt section)
"""

    await send_message(content)
