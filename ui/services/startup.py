"""
Startup Service

Handles session initialization and system health checks.
This is UI-specific because it deals with Chainlit session management.
"""

import asyncio
import logging

import chainlit as cl

# Import from src/ for API client
from src.clients.api_client import call_api, check_api_health, check_database_health, check_llm_health

# Import from ui/ for responses
from ..responses import system_status_message, welcome_message

logger = logging.getLogger(__name__)

# Store the current settings widget for refresh
_current_settings = None


async def initialize_session():
    """
    Initialize a new chat session with default values.
    Sets up session variables for chat history, query count, and filters.
    """
    # Get authenticated user and set user_id
    user = cl.user_session.get("user")
    if user and hasattr(user, 'identifier'):
        user_id = user.identifier
        cl.user_session.set("user_id", user_id)
        logger.info(f"Session initialized for user: {user_id}")
    else:
        cl.user_session.set("user_id", "anonymous@snapanalyst.com")
        logger.warning("No authenticated user found, using anonymous")

    cl.user_session.set("chat_history", [])
    cl.user_session.set("query_count", 0)
    cl.user_session.set("current_state_filter", "All States")
    cl.user_session.set("current_year_filter", "All Years")
    cl.user_session.set("training_enabled", False)


async def setup_filter_settings():
    """
    Set up the filter settings UI.
    Fetches available filter options from API and creates the settings panel.
    Loads saved filter from database if it exists.

    Returns:
        The ChatSettings object, or None if setup failed
    """
    global _current_settings
    try:
        # Get available filter options from API
        filter_options = await call_api("/filter/options")
        states = ["All States"] + filter_options.get("states", [])
        years = ["All Years"] + [str(y) for y in filter_options.get("fiscal_years", [])]

        # Store years in session for refresh detection
        cl.user_session.set("available_years", years)

        # Load saved filter from database
        try:
            current_filter = await call_api("/filter/")
            saved_state = current_filter.get("filter", {}).get("state")
            saved_year = current_filter.get("filter", {}).get("fiscal_year")

            initial_state = saved_state if saved_state else "All States"
            initial_year = str(saved_year) if saved_year else "All Years"
        except Exception:
            initial_state = "All States"
            initial_year = "All Years"

        # Create filter selection UI
        settings = await cl.ChatSettings(
            [
                cl.input_widget.Select(
                    id="state_filter",
                    label="State Filter",
                    values=states,
                    initial_value=initial_state,
                    description="Filter all queries and exports by state",
                ),
                cl.input_widget.Select(
                    id="year_filter",
                    label="Fiscal Year Filter",
                    values=years,
                    initial_value=initial_year,
                    description="Filter all queries and exports by fiscal year",
                ),
                cl.input_widget.Switch(
                    id="training_enabled",
                    label="AI Training",
                    initial=False,
                    description="Enable persistent training (stores embeddings in ChromaDB). When disabled, clears vector database.",
                ),
            ]
        ).send()

        _current_settings = settings
        return settings

    except Exception as e:
        logger.error(f"Error setting up filters: {e}")
        return None


async def refresh_filter_settings():
    """
    Refresh the filter settings with updated options from API.
    Call this after data load completes to update fiscal year options.

    Returns:
        True if filters were updated, False otherwise
    """
    try:
        # Get current available years from session
        old_years = cl.user_session.get("available_years", [])

        # Fetch fresh filter options
        filter_options = await call_api("/filter/options")
        new_years = ["All Years"] + [str(y) for y in filter_options.get("fiscal_years", [])]

        # Check if years have changed
        if set(new_years) != set(old_years):
            logger.info(f"Filter years changed: {old_years} -> {new_years}")
            cl.user_session.set("available_years", new_years)

            # Re-create the settings panel with new options
            states = ["All States"] + filter_options.get("states", [])

            await cl.ChatSettings(
                [
                    cl.input_widget.Select(
                        id="state_filter",
                        label="🗺️ State Filter",
                        values=states,
                        initial_value=cl.user_session.get("current_state_filter", "All States"),
                        description="Filter all queries and exports by state",
                    ),
                    cl.input_widget.Select(
                        id="year_filter",
                        label="📅 Fiscal Year Filter",
                        values=new_years,
                        initial_value=cl.user_session.get("current_year_filter", "All Years"),
                        description="Filter all queries and exports by fiscal year",
                    ),
                    cl.input_widget.Switch(
                        id="training_enabled",
                        label="🧠 AI Training",
                        initial=cl.user_session.get("training_enabled", False),
                        description="Enable persistent training (stores embeddings in ChromaDB). When disabled, clears vector database.",
                    ),
                ]
            ).send()

            return True

        return False

    except Exception as e:
        logger.error(f"Error refreshing filters: {e}")
        return False


async def wait_for_load_and_refresh(job_id: str, max_wait_seconds: int = 300):
    """
    Poll for load job completion and refresh filters when done.

    Args:
        job_id: The job ID to monitor
        max_wait_seconds: Maximum time to wait for completion
    """
    import httpx

    poll_interval = 5  # seconds
    elapsed = 0

    try:
        while elapsed < max_wait_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            try:
                # Check job status
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"http://localhost:8000/api/v1/data/load/jobs/{job_id}"
                    )
                    if response.status_code == 200:
                        job_data = response.json()
                        status = job_data.get("status")

                        if status == "completed":
                            logger.info(f"Load job {job_id} completed, refreshing filters")
                            updated = await refresh_filter_settings()
                            if updated:
                                from ..responses import send_message
                                await send_message("✅ **Filters updated** - New fiscal year is now available in the Settings panel.")
                            return
                        elif status == "failed":
                            logger.warning(f"Load job {job_id} failed")
                            return
                        # else: still in progress, keep polling

            except Exception as e:
                logger.debug(f"Error checking job status: {e}")
                # Continue polling on error

    except asyncio.CancelledError:
        logger.debug(f"Load monitoring task cancelled for job {job_id}")
    except Exception as e:
        logger.error(f"Error in load monitoring: {e}")


async def check_system_health():
    """
    Check all system components and display status.
    Checks API, database, and LLM services.
    """
    # Check all services
    api_ok, api_version = await check_api_health()
    db_ok, db_name = await check_database_health()
    llm_ok, llm_provider = await check_llm_health()

    # Send status message
    await system_status_message(
        api_ok=api_ok,
        api_version=api_version,
        db_ok=db_ok,
        db_name=db_name,
        llm_ok=llm_ok,
        llm_provider=llm_provider
    )

    # Send welcome message
    await welcome_message()

    return api_ok and db_ok and llm_ok
