"""
Settings Handler

Handles settings updates (filters, training toggle).
"""

import logging
import shutil
from pathlib import Path

import chainlit as cl

# Import from src/ for business logic
from src.clients.api_client import call_api

# Import from ui/ for UI-specific config and responses
from ..responses import (
    filter_applied_message,
    send_message,
    training_disabled_message,
    training_enabled_message,
)

logger = logging.getLogger(__name__)


async def handle_settings_update(settings: dict):
    """
    Handle settings updates from the ChatSettings panel.

    Handles:
    - State filter changes
    - Fiscal year filter changes
    - Training toggle

    Args:
        settings: Dictionary of updated settings
    """
    try:
        state_filter = settings.get("state_filter", "All States")
        year_filter = settings.get("year_filter", "All Years")
        training_enabled = settings.get("training_enabled", False)

        # Get previous values
        prev_state = cl.user_session.get("current_state_filter", "All States")
        prev_year = cl.user_session.get("current_year_filter", "All Years")
        prev_training = cl.user_session.get("training_enabled", False)

        # Handle training toggle
        if training_enabled != prev_training:
            await _handle_training_toggle(training_enabled)

        # Handle filter changes
        if state_filter != prev_state or year_filter != prev_year:
            await _handle_filter_change(state_filter, year_filter)

    except Exception as e:
        await send_message(
            f'<div class="warning-box">❌ Error updating settings: {str(e)}</div>'
        )


async def _handle_training_toggle(enabled: bool):
    """
    Handle training enabled/disabled toggle.

    Args:
        enabled: Whether training is now enabled
    """
    cl.user_session.set("training_enabled", enabled)

    if enabled:
        await training_enabled_message()

        try:
            await call_api("/llm/training/enable", method="POST")
        except Exception as e:
            logger.warning(f"Could not enable training via API: {e}")
    else:
        # Training disabled - clean ChromaDB
        await send_message("🧠 **AI Training Disabled**\n\nCleaning vector database...")

        try:
            chromadb_path = Path("./chromadb")
            if chromadb_path.exists():
                shutil.rmtree(chromadb_path)
                await training_disabled_message(cleaned=True)
            else:
                await training_disabled_message(cleaned=False)

            try:
                await call_api("/llm/training/disable", method="POST")
            except Exception as e:
                logger.warning(f"Could not disable training via API: {e}")

        except Exception as e:
            await training_disabled_message(error=str(e))


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
    await call_api(
        "/filter/set",
        method="POST",
        data={"state": state_val, "fiscal_year": year_val}
    )

    # Show confirmation message
    await filter_applied_message(state_val, year_val)
