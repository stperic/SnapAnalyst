"""
Chainlit Web UI for SnapAnalyst AI Chatbot

This is the THIN UI LAYER - all business logic is in the ui/ package.
This file only contains Chainlit decorators and routing.

Structure:
- ui/config.py: Constants, persona settings
- ui/api_client.py: API communication
- ui/formatters.py: HTML formatting
- ui/responses.py: Message templates with persona
- ui/handlers/: Business logic handlers
- ui/services/: Data processing services
"""

# Suppress noisy libraries BEFORE importing chainlit
# This must happen first to catch loggers before they're configured
import logging
logging.getLogger("websockets").setLevel(logging.ERROR)
logging.getLogger("websockets.protocol").setLevel(logging.ERROR)
logging.getLogger("websockets.server").setLevel(logging.ERROR)
logging.getLogger("websockets.client").setLevel(logging.ERROR)
logging.getLogger("engineio").setLevel(logging.ERROR)
logging.getLogger("socketio").setLevel(logging.ERROR)

import chainlit as cl
from datetime import datetime
from typing import Dict

# Initialize centralized logging (suppresses additional noisy libraries)
from src.core.logging import setup_logging
setup_logging()

# Import handlers from ui package
from ui.handlers.commands import handle_command
from ui.handlers.queries import handle_chat_query
from ui.handlers.settings import handle_settings_update
from ui.handlers.actions import (
    handle_csv_download,
    handle_execute,
    handle_cancel,
    handle_followup,
    handle_reset_confirm,
    handle_reset_cancel,
    handle_file_load,
    handle_refresh_database,
    handle_feedback_positive,
    handle_feedback_negative,
)
from ui.services.startup import initialize_session, setup_filter_settings, check_system_health


# =============================================================================
# CHAINLIT EVENT HANDLERS
# =============================================================================

@cl.on_chat_start
async def start():
    """Initialize chat session."""
    # Initialize session variables
    await initialize_session()
    
    # Set up filter settings UI
    await setup_filter_settings()
    
    # Check system health and show status
    await check_system_health()


@cl.on_settings_update
async def on_settings_update(settings: Dict):
    """Handle filter settings updates."""
    await handle_settings_update(settings)


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages."""
    user_input = message.content.strip()
    
    # Update chat history
    history = cl.user_session.get("chat_history")
    history.append({
        "timestamp": datetime.now().isoformat(),
        "role": "user",
        "content": user_input
    })
    
    # Handle special commands
    if user_input.startswith("/"):
        parts = user_input.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else None
        await handle_command(command, args)
        return
    
    # Normal chat query - send to LLM
    await handle_chat_query(user_input)


# =============================================================================
# ACTION CALLBACKS
# =============================================================================

@cl.action_callback("download_csv")
async def on_download_csv(action: cl.Action):
    """Handle CSV download action."""
    await handle_csv_download()


@cl.action_callback("execute")
async def on_execute(action: cl.Action):
    """Execute the pending SQL query."""
    await handle_execute()


@cl.action_callback("cancel")
async def on_cancel(action: cl.Action):
    """Cancel the pending query."""
    await handle_cancel()


@cl.action_callback("followup_*")
async def on_followup(action: cl.Action):
    """Handle follow-up question click."""
    await handle_followup(action.value)


@cl.action_callback("confirm_reset")
async def on_confirm_reset(action: cl.Action):
    """Handle database reset confirmation."""
    await handle_reset_confirm()


@cl.action_callback("cancel_reset")
async def on_cancel_reset(action: cl.Action):
    """Cancel database reset."""
    await handle_reset_cancel()


@cl.action_callback("load_*")
async def on_load_file(action: cl.Action):
    """Handle file loading."""
    await handle_file_load(action.value)


@cl.action_callback("refresh_database")
async def on_refresh_database(action: cl.Action):
    """Refresh database statistics."""
    await handle_refresh_database()


@cl.action_callback("feedback_positive")
async def on_feedback_positive(action: cl.Action):
    """Handle positive feedback (thumbs up)."""
    await handle_feedback_positive(action.value)


@cl.action_callback("feedback_negative")
async def on_feedback_negative(action: cl.Action):
    """Handle negative feedback (thumbs down)."""
    await handle_feedback_negative(action.value)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # This is handled by chainlit CLI
    pass
