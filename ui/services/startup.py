"""
Startup Service

Handles session initialization and system health checks.
This is UI-specific because it deals with Chainlit session management.
"""

import asyncio

import chainlit as cl

# Import from src/ for API client
from src.clients.api_client import API_BASE_URL, call_api
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


def _get_default_llm_settings() -> dict:
    """Get default LLM settings from config for all three modes."""
    return {
        "sql": {
            "model": settings.sql_model,
            "temperature": settings.effective_sql_temperature,
            "max_tokens": settings.effective_sql_max_tokens,
            "top_p": 1.0,
            "context_window": None,
            "summary_enabled": settings.llm_sql_summary_enabled,
            "summary_max_rows": settings.llm_sql_summary_max_rows,
        },
        "insights": {
            "model": settings.kb_model,
            "temperature": settings.effective_kb_temperature,
            "max_tokens": settings.llm_kb_max_tokens,
            "top_p": 1.0,
            "context_window": None,
        },
        "knowledge": {
            "model": settings.kb_model,
            "temperature": settings.effective_kb_temperature,
            "max_tokens": settings.llm_kb_max_tokens,
            "top_p": 1.0,
            "context_window": None,
        },
        "summary": {
            "model": settings.kb_model,
            "temperature": settings.effective_kb_temperature,
            "max_tokens": settings.llm_kb_max_tokens,
            "top_p": 1.0,
            "context_window": None,
            "summary_enabled": settings.llm_sql_summary_enabled,
            "summary_max_rows": settings.llm_sql_summary_max_rows,
        },
    }


def _prefill_context_windows(defaults: dict) -> dict:
    """Try to fill context window values from the model registry."""
    try:
        from src.services.model_registry import get_context_window

        for mode in ("sql", "insights", "knowledge", "summary"):
            model = defaults[mode]["model"]
            ctx = get_context_window(model)
            if ctx:
                defaults[mode]["context_window"] = ctx
    except Exception as e:
        logger.debug(f"Could not prefill context windows: {e}")
    return defaults


async def initialize_session():
    """
    Initialize a new chat session with default values.
    Sets up session variables for chat history, query count, filters, and LLM settings.
    """
    # Get authenticated user and set user_id
    user = cl.user_session.get("user")
    if user and hasattr(user, "identifier"):
        user_id = user.identifier
        cl.user_session.set("user_id", user_id)
        logger.debug(f"Session initialized for user: {user_id}")
    else:
        # Derive default anonymous email from active dataset
        try:
            from datasets import get_active_dataset

            ds = get_active_dataset()
            app_name = ds.get_personas().get("app", "snapanalyst").lower().replace(" ", "") if ds else "snapanalyst"
        except Exception:
            app_name = "snapanalyst"
        cl.user_session.set("user_id", f"anonymous@{app_name}.com")
        logger.warning("No authenticated user found, using anonymous")

    cl.user_session.set("chat_history", [])
    cl.user_session.set("query_count", 0)
    cl.user_session.set("current_state_filter", "All States")
    cl.user_session.set("current_year_filter", "All Years")

    # Initialize per-mode LLM settings with defaults
    defaults = _prefill_context_windows(_get_default_llm_settings())
    cl.user_session.set("llm_sql_settings", defaults["sql"])
    cl.user_session.set("llm_insights_settings", defaults["insights"])
    cl.user_session.set("llm_knowledge_settings", defaults["knowledge"])
    cl.user_session.set("llm_summary_settings", defaults["summary"])


async def setup_filter_settings():
    """
    Load saved filter from database and apply to session.
    No longer creates ChatSettings widgets — filters are managed via the Settings button.
    """
    try:
        # Get available filter options from API
        filter_options = await call_api("/filter/options")
        years = ["All Years"] + [str(y) for y in filter_options.get("fiscal_years", [])]

        # Store years in session for refresh detection
        cl.user_session.set("available_years", years)

        # Load saved filter from database
        try:
            current_filter = await call_api("/filter/")
            saved_state = current_filter.get("filter", {}).get("state")
            saved_year = current_filter.get("filter", {}).get("fiscal_year")

            if saved_state:
                cl.user_session.set("current_state_filter", saved_state)
            if saved_year:
                cl.user_session.set("current_year_filter", str(saved_year))
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error setting up filters: {e}")


async def refresh_filter_settings():
    """
    Refresh the available filter options from API.
    Call this after data load completes to update fiscal year options.

    Returns:
        True if years have changed, False otherwise
    """
    try:
        old_years = cl.user_session.get("available_years", [])

        filter_options = await call_api("/filter/options")
        new_years = ["All Years"] + [str(y) for y in filter_options.get("fiscal_years", [])]

        if set(new_years) != set(old_years):
            logger.info(f"Filter years changed: {old_years} -> {new_years}")
            cl.user_session.set("available_years", new_years)
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
                    response = await client.get(f"{API_BASE_URL}/api/v1/data/load/jobs/{job_id}")
                    if response.status_code == 200:
                        job_data = response.json()
                        status = job_data.get("status")

                        if status == "completed":
                            logger.info(f"Load job {job_id} completed, refreshing filters")
                            updated = await refresh_filter_settings()
                            if updated:
                                from ..responses import send_message

                                await send_message(
                                    "**Filters updated** - New fiscal year is now available. Use the **Settings** button to update your filters."
                                )
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
