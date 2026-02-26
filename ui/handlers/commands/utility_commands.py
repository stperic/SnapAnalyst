"""
Utility Commands Module

Handles utility commands:
- /clear: Clear chat history
- Filter sidebar panel (via Settings)
"""

import chainlit as cl

from src.clients.api_client import call_api
from src.core.logging import get_logger

from ...responses import send_error, send_message

logger = get_logger(__name__)


async def handle_filter(args: str | None = None):
    """Handle /filter command - open filter sidebar panel."""
    try:
        filter_options = await call_api("/filter/options")
        current_filter = await call_api("/filter/")

        states = ["All States"] + filter_options.get("states", [])
        years = ["All Years"] + [str(y) for y in filter_options.get("fiscal_years", [])]

        current_state = current_filter.get("filter", {}).get("state") or "All States"
        current_year = str(current_filter.get("filter", {}).get("fiscal_year") or "") or "All Years"

        from src.clients.api_client import get_api_external_url, get_api_prefix

        api_url = get_api_external_url() + get_api_prefix()

        element = cl.CustomElement(
            name="FilterPanel",
            props={
                "apiUrl": api_url,
                "states": states,
                "years": years,
                "currentState": current_state,
                "currentYear": current_year,
            },
            display="side",
        )
        await cl.ElementSidebar.set_title("Data Filters")
        await cl.ElementSidebar.set_elements([element], key="filter")

    except Exception as e:
        await send_error(f"Error opening filter panel: {str(e)}")


async def handle_clear():
    """Handle /clear command - clear chat history."""
    from ...services.thread_context import get_thread_context

    cl.user_session.set("chat_history", [])
    cl.user_session.set("query_count", 0)

    # Also clear thread context
    thread_ctx = get_thread_context()
    thread_ctx.clear()

    await send_message("Chat history and thread context cleared!")
