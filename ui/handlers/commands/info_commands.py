"""
Info Commands Module

Handles system information and status commands:
- /help: Show all available commands
- /status: System health check
- /database: Database statistics
- /schema: Database schema
- /llm: LLM provider info
- /history: Chat history
"""

import logging

import chainlit as cl

# Import from src/ for business logic
from src.clients.api_client import call_api, get_api_base_url

# Import centralized prompts
from src.core.prompts import (
    MSG_DATABASE_STATS_HEADER,
    MSG_HELP,
    MSG_LOADING_IN_PROGRESS,
)

# Import from ui/ for UI-specific config and message helpers
from ...responses import send_error, send_message

logger = logging.getLogger(__name__)


async def handle_help():
    """Display help message with all available commands."""
    await send_message(MSG_HELP)


async def handle_status():
    """Display system health status for all services."""
    try:
        # Get detailed status from /about endpoint (root level, not /api/v1)
        import httpx

        from src.clients.api_client import get_api_base_url

        api_base_url = get_api_base_url()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{api_base_url}/about")
            response.raise_for_status()
            about_info = response.json()

        services = about_info.get('services', {})

        # Extract service status
        api_service = services.get('api', {})
        db_service = services.get('database', {})
        llm_service = services.get('llm', {})

        api_status = api_service.get('status', 'unknown')
        api_version = api_service.get('version', 'unknown')

        db_status = db_service.get('status', 'unknown')
        db_type = db_service.get('type', 'PostgreSQL')

        llm_status = llm_service.get('status', 'unknown')
        llm_provider = llm_service.get('provider', 'unknown')
        llm_model = llm_service.get('model', 'unknown')

        # Build status message
        content = f"""### System Status

✅ **API Service** ({api_version})
{'✅' if db_status == 'healthy' else '❌'} **{db_type} Database**
{'✅' if llm_status == 'healthy' else '❌'} **LLM Inference Service** ({llm_provider} - {llm_model})

---

{'🟢 **All systems operational**' if all([api_status == 'healthy', db_status == 'healthy', llm_status == 'healthy']) else '🟡 **Some services unavailable** - Check logs for details'}
"""

        await send_message(content)

    except Exception as e:
        await send_error(f"Error fetching system status: {str(e)}")


async def handle_database():
    """Handle /database command - show database statistics."""
    try:
        import httpx

        api_base_url = get_api_base_url()

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{api_base_url}/api/v1/data/health")
            health = response.json()

        db_info = health.get("database", {})

        connection_status = '🟢 Connected' if db_info.get('connected', False) else '🔴 Disconnected'
        content = MSG_DATABASE_STATS_HEADER.format(
            connection_status=connection_status,
            db_name=db_info.get('name', 'snapanalyst_db')
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                stats_response = await client.get(f"{api_base_url}/api/v1/data/stats")
                stats = stats_response.json()

            summary = stats.get('summary', {})

            # FNS SNAP Data section
            content += "**FNS SNAP Data**\n"
            if summary.get('fiscal_years'):
                content += f"- Fiscal Years: {', '.join(map(str, summary['fiscal_years']))}\n"
            content += f"- Households: {summary.get('total_households', 0):,}\n"
            content += f"- Household Members: {summary.get('total_members', 0):,}\n"
            content += f"- QC Errors: {summary.get('total_qc_errors', 0):,}\n"
            content += f"- Data Loads: {len(stats.get('by_fiscal_year', []))}\n\n"

            # SNAP Tables section
            ref_count = summary.get('reference_tables', 0)
            views_count = summary.get('views', 0)
            content += "**SNAP Tables**\n"
            content += "- Core: households, household_members, qc_errors\n"
            content += f"- Reference Tables: {ref_count}\n"
            if views_count:
                content += f"- Views: {views_count}\n"
            content += "\n"

            # Custom Tables section
            custom_count = summary.get('custom_tables', 0)
            custom_names = summary.get('custom_table_names', [])
            if custom_count:
                content += f"**Custom Tables** ({custom_count})\n"
                for name in custom_names:
                    content += f"- {name}\n"
                content += "\n"

            if stats.get('last_load'):
                content += f"**Last Load:** {stats['last_load']}\n"
        except Exception as e:
            content += f"*Unable to fetch detailed statistics: {str(e)}*\n\n"

        # Check for active loading jobs
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                jobs_response = await client.get(f"{api_base_url}/api/v1/data/load/jobs?active_only=true")
                jobs_data = jobs_response.json()
                active_jobs = jobs_data.get("jobs", [])

            if active_jobs:
                job_status = active_jobs[0]
                active_job_id = job_status.get("job_id")
                status_value = job_status.get("status")

                if status_value in ["in_progress", "processing", "accepted"]:
                    progress = job_status.get("progress", {})
                    content += MSG_LOADING_IN_PROGRESS.format(
                        job_id=active_job_id,
                        percent=progress.get("percent_complete", 0),
                        rows_processed=progress.get('rows_processed', 0),
                        total_rows=progress.get('total_rows', 0)
                    )
        except Exception as e:
            logger.debug(f"Error fetching active jobs: {e}")

        # Add refresh button
        refresh_action = cl.Action(
            name="refresh_database",
            payload={"action": "refresh"},
            label="🔄 Refresh",
            tooltip="Refresh database statistics"
        )

        await send_message(content, actions=[refresh_action])

    except Exception as e:
        import traceback
        logger.error(f"Database command error: {e}\n{traceback.format_exc()}")
        await send_error(f"Error fetching database info: {str(e)}")


async def handle_schema():
    """Handle /schema command - show database schema."""
    try:
        schema = await call_api("/query/schema")

        content = "### Database Schema\n\n"

        db_info = schema.get("database", {})
        if db_info:
            content += f"**Database:** {db_info.get('name', 'SnapAnalyst')}\n"
            content += f"*{db_info.get('description', '')}*\n\n"
            if db_info.get('fiscal_years_available'):
                content += f"**Available Years:** {', '.join(map(str, db_info['fiscal_years_available']))}\n\n"

        tables = schema.get("tables", {})

        for table_name, table_info in tables.items():
            content += f"#### Table: `{table_name}`\n"
            content += f"*{table_info.get('description', 'No description')}*\n\n"

            content += "| Column | Type | Nullable | Description |\n"
            content += "|--------|------|----------|-------------|\n"

            columns = table_info.get("columns", {})
            for col_name, col_info in columns.items():
                col_type = col_info.get('type', 'UNKNOWN')
                nullable = "✓" if col_info.get("nullable", True) else "✗"
                description = col_info.get('description', '-')
                content += f"| `{col_name}` | {col_type} | {nullable} | {description} |\n"

            content += "\n"

        relationships = schema.get("relationships", {})
        if relationships:
            content += "### Relationships\n\n"
            for rel_name, rel_info in relationships.items():
                rel_type = rel_info.get('type', 'UNKNOWN')
                description = rel_info.get('description', '')
                join_condition = rel_info.get('join', '')
                content += f"**{rel_name}** ({rel_type})\n"
                content += f"- {description}\n"
                content += f"- Join: `{join_condition}`\n\n"

        await send_message(content)

    except Exception as e:
        import traceback
        logger.error(f"Schema command error: {e}\n{traceback.format_exc()}")
        await send_error(f"Error fetching schema: {str(e)}")


async def handle_llm():
    """Handle /llm command - show LLM provider info and configuration."""
    try:
        provider_info = await call_api("/llm/provider")

        # New simplified response structure
        provider = provider_info.get('provider', 'Unknown').upper()
        model = provider_info.get('model', 'Unknown')
        vanna_version = provider_info.get('vanna_version', 'Unknown')
        initialized = provider_info.get('initialized', False)
        datasets = ', '.join(provider_info.get('datasets_loaded', [])) or 'None'

        content = f"""### LLM Provider Information

**Provider:** {provider}
**Model:** {model}
**Vanna Version:** {vanna_version}
**Status:** {'✅ Initialized' if initialized else '⚠️ Not Initialized'}
**Datasets Loaded:** {datasets}

Use `/help` for available commands.
"""

        await send_message(content)

    except Exception as e:
        await send_error(f"Error fetching provider info: {str(e)}")


async def handle_history():
    """Handle /history command - show chat history."""
    history = cl.user_session.get("chat_history")
    query_count = cl.user_session.get("query_count")

    if not history:
        await send_message("No chat history yet. Start asking questions!")
        return

    content = f"### Your Chat History ({len(history)} messages, {query_count} queries)\n\n"

    for i, entry in enumerate(history[-10:], 1):
        role = "👤" if entry["role"] == "user" else "🤖"
        timestamp = entry["timestamp"].split("T")[1][:8]
        content += f"{i}. [{timestamp}] {role} {entry['content'][:100]}...\n\n"

    await send_message(content)
