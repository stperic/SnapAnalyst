"""
Prompt Management Commands

Handlers for /prompt command to manage custom LLM prompts.
"""

import logging

import chainlit as cl

from src.database.prompt_manager import (
    get_user_prompt,
    has_custom_prompt,
    reset_user_prompt,
    set_user_prompt,
)
from ui.responses import send_error, send_message

logger = logging.getLogger(__name__)


def _get_prompt_preview(text: str, max_length: int = 500) -> tuple[str, bool]:
    """Get preview of prompt text with truncation indicator."""
    if len(text) <= max_length:
        return text, False
    return text[:200] + "...", True


def _clean_prompt_text(prompt_text: str, prompt_type: str) -> str:
    """Clean and sanitize prompt text input."""
    prompt_text = prompt_text.strip()

    # Remove surrounding quotes
    if (prompt_text.startswith('"') and prompt_text.endswith('"')) or \
       (prompt_text.startswith("'") and prompt_text.endswith("'")):
        prompt_text = prompt_text[1:-1]

    # Remove command prefix if accidentally included
    command_prefixes = [
        f"/prompt {prompt_type} set ",
        f"/prompt {prompt_type} set"
    ]
    for prefix in command_prefixes:
        if prompt_text.startswith(prefix):
            prompt_text = prompt_text[len(prefix):].strip()
            break

    return prompt_text


async def handle_prompt_command(args: str | None = None):
    """
    Manage LLM prompts.

    Usage:
      /prompt sql              Show current SQL prompt
      /prompt kb               Show current KB prompt
      /prompt sql set <text>   Set SQL prompt with inline text
      /prompt sql set          Set SQL prompt from attached file
      /prompt sql reset        Reset SQL prompt to default
      /prompt kb set <text>    Set KB prompt with inline text
      /prompt kb set           Set KB prompt from attached file
      /prompt kb reset         Reset KB prompt to default
    """
    if not args:
        await send_error(
            "**Usage:** `/prompt <sql|kb> [set <text>|reset]`\n\n"
            "**Examples:**\n"
            "- `/prompt sql` - Show current SQL prompt\n"
            "- `/prompt sql set Your prompt here...` - Set SQL prompt\n"
            "- `/prompt sql reset` - Reset to default\n\n"
            "**Attach a .txt file** to set prompt from file."
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

    if action == "reset":
        await handle_prompt_reset(prompt_type)
        return

    if action == "set":
        message_files = cl.user_session.get("message_files") or []

        if message_files:
            await handle_prompt_upload_from_file(prompt_type, message_files)
        elif len(parts) == 3:
            prompt_text = parts[2]
            await handle_prompt_upload_from_text(prompt_type, prompt_text)
        else:
            await send_error(
                "**Missing prompt text**\n\n"
                "Usage: `/prompt sql set Your prompt text here...`\n"
                "OR attach a .txt file with `/prompt sql set`"
            )
        return

    await send_error(
        f"Unknown action: `{action}`\n\n"
        "Use **set** (to update) or **reset** (to restore default)"
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

    content = f"""### Current {prompt_name} Prompt ({status})

**Stats:** {char_count:,} characters, {line_count} lines

```
{prompt_text}
```

**To modify:**
- Inline: `/prompt {prompt_type} set Your new prompt...`
- File: Attach .txt file + `/prompt {prompt_type} set`

**To reset:**
- `/prompt {prompt_type} reset` (restore system default)
"""

    await send_message(content)


async def handle_prompt_upload_from_text(prompt_type: str, prompt_text: str):
    """Handle inline text prompt upload with confirmation."""
    user = cl.user_session.get("user")
    if not user:
        await send_error("User session not found")
        return

    # Clean up prompt text
    prompt_text = _clean_prompt_text(prompt_text, prompt_type)

    # Validate length
    char_count = len(prompt_text)
    if char_count < 20:
        await send_error(f"Prompt too short ({char_count} chars). Minimum 20 characters.")
        return

    if char_count > 5000:
        await send_error(f"Prompt too long ({char_count} chars). Maximum 5000 characters.")
        return

    cl.user_session.set("pending_prompt_update", {
        "type": prompt_type,
        "text": prompt_text,
        "source": "inline"
    })

    prompt_name = "SQL Generation" if prompt_type == "sql" else "KB Insight"
    preview, truncated = _get_prompt_preview(prompt_text)

    content = f"""### Confirm New {prompt_name} Prompt

**Preview** ({char_count} characters{'...' if truncated else ''}):

```
{preview}
```

Replace your current prompt with this text?"""

    actions = [
        cl.Action(name="confirm_prompt_update", payload={"confirm": "yes"}, label="✅ Yes, Update Prompt"),
        cl.Action(name="cancel_prompt_update", payload={"confirm": "no"}, label="❌ Cancel"),
    ]

    await send_message(content, actions=actions)


async def handle_prompt_upload_from_file(prompt_type: str, files):
    """Handle file-based prompt upload with confirmation."""
    user = cl.user_session.get("user")
    if not user:
        await send_error("User session not found")
        return

    if len(files) > 1:
        await send_error("Please attach only one .txt file at a time.")
        return

    file = files[0]
    filename = file.name if hasattr(file, 'name') else str(file)

    if not filename.endswith('.txt'):
        await send_error(f"Invalid file type: `{filename}`\n\nOnly .txt files are allowed.")
        return

    try:
        with open(file.path, encoding='utf-8') as f:
            prompt_text = f.read()
    except Exception as e:
        await send_error(f"Error reading file: {str(e)}")
        return

    # Validate length
    char_count = len(prompt_text)
    if char_count < 20:
        await send_error(f"Prompt too short ({char_count} chars). Minimum 20 characters.")
        return

    if char_count > 5000:
        await send_error(f"Prompt too long ({char_count} chars). Maximum 5000 characters.")
        return

    cl.user_session.set("pending_prompt_update", {
        "type": prompt_type,
        "text": prompt_text,
        "source": "file",
        "filename": filename
    })

    prompt_name = "SQL Generation" if prompt_type == "sql" else "KB Insight"
    preview, truncated = _get_prompt_preview(prompt_text)

    content = f"""### Confirm New {prompt_name} Prompt

**File:** {filename} ({char_count} characters)

**Preview:**

```
{preview}
```

Replace your current prompt with this file content?"""

    actions = [
        cl.Action(name="confirm_prompt_update", payload={"confirm": "yes"}, label="✅ Yes, Update Prompt"),
        cl.Action(name="cancel_prompt_update", payload={"confirm": "no"}, label="❌ Cancel"),
    ]

    await send_message(content, actions=actions)


async def handle_prompt_confirmation(user_input: str):
    """Handle yes/no confirmation for pending prompt update."""
    pending = cl.user_session.get("pending_prompt_update")
    if not pending:
        return False

    user = cl.user_session.get("user")
    if not user:
        await send_error("User session not found")
        cl.user_session.set("pending_prompt_update", None)
        return True

    response = user_input.strip().lower()
    if response not in ['yes', 'no']:
        return False

    if response == 'no':
        await send_message("Prompt update cancelled.")
        cl.user_session.set("pending_prompt_update", None)
        return True

    prompt_type = pending["type"]
    prompt_text = pending["text"]
    user_id = user.identifier
    try:
        success = set_user_prompt(user_id, prompt_type, prompt_text)

        if success:
            prompt_name = "SQL generation" if prompt_type == "sql" else "KB insight"
            source = "file" if pending["source"] == "file" else "inline text"

            await send_message(
                f"✅ **{prompt_name} prompt updated successfully!**\n\n"
                f"Source: {source}\n"
                f"Length: {len(prompt_text):,} characters\n\n"
                f"Use `/prompt {prompt_type}` to view your custom prompt."
            )
        else:
            await send_error("Failed to save prompt. Please try again.")

    except ValueError as e:
        await send_error(f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error saving prompt: {e}")
        await send_error(f"Error saving prompt: {str(e)}")

    cl.user_session.set("pending_prompt_update", None)
    return True


async def handle_prompt_reset(prompt_type: str):
    """Reset user's prompt to system default."""
    user = cl.user_session.get("user")
    if not user:
        await send_error("User session not found")
        return

    user_id = user.identifier

    if not has_custom_prompt(user_id, prompt_type):
        prompt_name = "SQL" if prompt_type == "sql" else "KB"
        await send_message(
            f"**{prompt_name} prompt is already at default.**\n\n"
            "No custom prompt to reset."
        )
        return

    success = reset_user_prompt(user_id, prompt_type)

    if success:
        prompt_name = "SQL generation" if prompt_type == "sql" else "KB insight"
        await send_message(
            f"✅ **{prompt_name} prompt reset to default.**\n\n"
            f"Use `/prompt {prompt_type}` to view the default prompt."
        )
    else:
        await send_error("Failed to reset prompt. Please try again.")
