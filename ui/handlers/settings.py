"""
Settings Handler

Handles settings updates (filters).
LLM settings are managed via the LLM sidebar panel and callAction callbacks.
"""

import chainlit as cl

# Import from src/ for business logic
from src.clients.api_client import call_api
from src.core.logging import get_logger

# Import from ui/ for UI-specific config and responses
from ..responses import (
    filter_applied_message,
    send_message,
)

logger = get_logger(__name__)


async def handle_settings_update(settings: dict):
    """
    Handle settings updates from the ChatSettings panel.

    Now only handles filter changes — LLM settings are managed via sidebar panel.

    Args:
        settings: Dictionary of updated settings
    """
    try:
        state_filter = settings.get("state_filter", "All States")
        year_filter = settings.get("year_filter", "All Years")

        # Get previous values
        prev_state = cl.user_session.get("current_state_filter", "All States")
        prev_year = cl.user_session.get("current_year_filter", "All Years")

        # Handle filter changes
        if state_filter != prev_state or year_filter != prev_year:
            await _handle_filter_change(state_filter, year_filter)

    except Exception as e:
        await send_message(f'<div class="warning-box">Error updating settings: {str(e)}</div>')


async def _handle_filter_change(state_filter: str, year_filter: str):
    """
    Handle filter value changes.

    Args:
        state_filter: New state filter value
        year_filter: New year filter value
    """
    # Update session
    cl.user_session.set("current_state_filter", state_filter)
    cl.user_session.set("current_year_filter", year_filter)

    # Apply to backend API
    state_val = None if state_filter == "All States" else state_filter
    year_val = None if year_filter == "All Years" else int(year_filter)

    # Update filter via API
    await call_api("/filter/set", method="POST", data={"state": state_val, "fiscal_year": year_val})

    # Show confirmation message
    await filter_applied_message(state_val, year_val)
