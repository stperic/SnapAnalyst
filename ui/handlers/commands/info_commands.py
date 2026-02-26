"""
Info Commands Module

Handles system information and settings panel commands:
- Readme panel: App documentation in the sidebar
- Settings panel: Navigation hub for all settings
- Database panel: Database stats and export
- LLM panel: LLM provider settings
"""

import pathlib

import chainlit as cl
import markdown

from src.core.logging import get_logger

from ...responses import send_error

logger = get_logger(__name__)

# Read and render chainlit.md once at import time
_README_HTML = ""
_readme_path = pathlib.Path(__file__).resolve().parents[3] / "chainlit.md"
if _readme_path.exists():
    _README_HTML = markdown.markdown(
        _readme_path.read_text(),
        extensions=["tables", "fenced_code"],
    )


async def handle_readme_panel():
    """Open the Readme panel in the sidebar."""
    element = cl.CustomElement(
        name="ReadmePanel",
        props={"markdown": _README_HTML},
        display="side",
    )
    await cl.ElementSidebar.set_title("Readme")
    await cl.ElementSidebar.set_elements([element], key="readme")


async def handle_settings_panel():
    """Open the Settings navigation panel in the sidebar."""
    element = cl.CustomElement(
        name="SettingsPanel",
        props={},
        display="side",
    )
    await cl.ElementSidebar.set_title("Settings")
    await cl.ElementSidebar.set_elements([element], key="settings")


async def handle_database_panel():
    """Open the Database panel in the sidebar with stats and export."""
    try:
        from src.clients.api_client import get_api_external_url, get_api_prefix

        api_url = get_api_external_url() + get_api_prefix()

        # Get available years from session or API
        available_years = cl.user_session.get("available_years") or []
        # Strip "All Years" from the list for the panel
        year_values = [y for y in available_years if y != "All Years"]

        current_year = cl.user_session.get("current_year_filter") or ""
        if current_year == "All Years":
            current_year = ""

        element = cl.CustomElement(
            name="DatabasePanel",
            props={
                "apiUrl": api_url,
                "currentYear": current_year,
                "availableYears": year_values,
            },
            display="side",
        )
        await cl.ElementSidebar.set_title("Database")
        await cl.ElementSidebar.set_elements([element], key="database")

    except Exception as e:
        await send_error(f"Error opening database panel: {str(e)}")


async def handle_llm(args: str | None = None):
    """Open LLM settings sidebar panel."""
    # Default: open sidebar panel
    try:
        sql_settings = cl.user_session.get("llm_sql_settings") or {}
        insights_settings = cl.user_session.get("llm_insights_settings") or {}
        knowledge_settings = cl.user_session.get("llm_knowledge_settings") or {}
        summary_settings = cl.user_session.get("llm_summary_settings") or {}
        user_id = cl.user_session.get("user_id") or "default"

        from src.clients.api_client import get_api_external_url, get_api_prefix
        from src.core.config import settings
        from ui.services.startup import _get_default_llm_settings, _prefill_context_windows

        api_url = get_api_external_url() + get_api_prefix()

        defaults = _prefill_context_windows(_get_default_llm_settings())

        element = cl.CustomElement(
            name="LlmPanel",
            props={
                "apiUrl": api_url,
                "provider": settings.llm_provider.replace("_", " ").title(),
                "userId": user_id,
                "settings": {
                    "sql": sql_settings,
                    "insights": insights_settings,
                    "knowledge": knowledge_settings,
                    "summary": summary_settings,
                },
                "defaults": defaults,
            },
            display="side",
        )
        await cl.ElementSidebar.set_title("LLM Params")
        await cl.ElementSidebar.set_elements([element], key="llm")

    except Exception as e:
        await send_error(f"Error opening LLM settings panel: {str(e)}")
