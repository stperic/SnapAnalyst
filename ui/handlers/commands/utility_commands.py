"""
Utility Commands Module

Handles utility commands:
- /export: Export data to Excel
- /filter: Show/manage filter status
- /clear: Clear chat history
"""

import logging
import os
import tempfile
from datetime import datetime

import chainlit as cl
import httpx

from src.clients.api_client import call_api, get_api_base_url, get_api_prefix
from src.core.prompts import MSG_FILTER_STATUS

from ...config import SUPPORTED_FISCAL_YEARS
from ...responses import send_error, send_message, send_warning

logger = logging.getLogger(__name__)


async def handle_export(args: str | None = None):
    """
    Handle /export command - download data to Excel.

    Usage:
        /export                              # Default: 3 core tables
        /export 2023                         # FY2023 only
        /export tables=snap_my_table         # Custom tables
        /export 2023 tables=households,snap_my_table
    """
    try:
        await send_message("Preparing your data export... This may take up to 3 minutes in some cases.")

        api_base_url = get_api_base_url()
        api_prefix = get_api_prefix()

        # Parse arguments
        fiscal_year = None
        tables = None

        if args:
            parts = args.split()
            for part in parts:
                if part.isdigit():
                    # Fiscal year argument
                    try:
                        fy = int(part)
                        if fy in SUPPORTED_FISCAL_YEARS:
                            fiscal_year = fy
                        else:
                            await send_warning(f"Invalid fiscal year: {fy}. Using all years.")
                    except ValueError:
                        pass
                elif part.startswith("tables="):
                    # Tables argument (comma-separated)
                    tables = part.split("=", 1)[1]

        # Build API URL with parameters
        params = []
        if fiscal_year:
            params.append(f"fiscal_year={fiscal_year}")
        if tables:
            params.append(f"tables={tables}")

        param_str = "?" + "&".join(params) if params else ""
        api_url = f"{api_base_url}{api_prefix}/data/export/excel{param_str}"

        # Increased timeout for large exports (can take 2-3 minutes for full dataset)
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.get(api_url)
            response.raise_for_status()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snapanalyst_export_{timestamp}.xlsx"
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, filename)

            with open(temp_path, 'wb') as f:
                f.write(response.content)

        file_element = cl.File(
            name=filename,
            path=temp_path,
            display="inline"
        )

        try:
            filter_data = await call_api("/filter/")
            filter_description = filter_data.get("description", "No filter (All data)")
        except Exception:
            filter_description = "No filter (All data)"

        # Build dynamic "What's included" section
        if tables:
            # Custom tables specified
            table_list = [t.strip() for t in tables.split(",")]
            sheets_info = "\n".join([f"- **{t.replace('_', ' ').title()}** - {t}" for t in table_list])
        else:
            # Default tables (backward compatible)
            sheets_info = """- **Households** - Household case data
- **Members** - Household member data
- **QC_Errors** - Quality control errors"""

        content = f"""### ✅ Your Excel export is ready!

**What's included:**
- **README** - Complete documentation (opens first)
{sheets_info}

**Filter:** {filter_description}

Click the file below to download:"""

        await send_message(content, elements=[file_element])

    except httpx.HTTPError as e:
        await send_error(f"Error fetching export from API: {str(e)}")
    except Exception as e:
        await send_error(f"Error generating download: {str(e)}")


async def handle_filter(args: str | None = None):
    """Handle /filter command - show or manage filter status."""
    try:
        filter_data = await call_api("/filter/")
        current_filter = filter_data.get("filter", {})
        description = filter_data.get("description", "No filter")
        is_active = filter_data.get("is_active", False)

        content = MSG_FILTER_STATUS.format(
            status='✅ Active' if is_active else '⚠️ No Filter (All Data)',
            state=current_filter.get('state') or 'All States',
            fiscal_year=current_filter.get('fiscal_year') or 'All Years',
            description=description
        )

        await send_message(content)

    except Exception as e:
        await send_error(f"Error fetching filter status: {str(e)}")


async def handle_clear():
    """Handle /clear command - clear chat history."""
    from ...services.thread_context import get_thread_context

    cl.user_session.set("chat_history", [])
    cl.user_session.set("query_count", 0)

    # Also clear thread context
    thread_ctx = get_thread_context()
    thread_ctx.clear()

    await send_message("✅ Chat history and thread context cleared!")


