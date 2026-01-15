"""
Command Handlers

Handles all slash commands (/help, /load, /schema, /notes, etc.)
Uses centralized message templates from src/core/prompts.py.

All messages use APP_PERSONA (SnapAnalyst) - the app persona.
AI responses (query answers) use AI_PERSONA in queries.py.
"""

import chainlit as cl
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

# Import from src/ for business logic
from src.clients.api_client import (
    call_api, upload_file, get_api_base_url, get_api_prefix,
    check_api_health, check_database_health, check_llm_health
)

# Import from ui/ for UI-specific config and message helpers
from ..config import SUPPORTED_FISCAL_YEARS, DEFAULT_FISCAL_YEAR, APP_PERSONA
from ..responses import send_message, send_error, send_warning, system_status_message

# Import centralized prompts
from src.core.prompts import (
    MSG_HELP,
    MSG_DATA_LOADING_INITIATED,
    MSG_LOADING_IN_PROGRESS,
    MSG_FILE_UPLOAD_SUCCESS,
    MSG_DATABASE_STATS_HEADER,
    MSG_LLM_PROVIDER_INFO,
    MSG_LLM_TRAINING_NOTE,
    MSG_EXCEL_EXPORT_READY,
    MSG_FILTER_STATUS,
    MSG_SAMPLES_HEADER,
    MSG_SAMPLES_NOT_FOUND,
    MSG_EDIT_SAMPLES_PROMPT,
    MSG_SAMPLES_UPDATED,
    MSG_EDIT_CANCELLED,
)

# Import LLM logger for notes logging
from src.core.logging import get_llm_logger

logger = logging.getLogger(__name__)
llm_logger = get_llm_logger()


async def handle_command(command: str, args: Optional[str] = None):
    """
    Route slash commands to appropriate handlers.
    
    Args:
        command: The command (e.g., "/help")
        args: Optional arguments after the command
    """
    handlers = {
        "/help": lambda: handle_help(),
        "/status": lambda: handle_status(),
        "/load": lambda: handle_load(args),
        "/files": lambda: handle_files(),
        "/upload": lambda: handle_upload(),
        "/reset": lambda: handle_reset(),
        "/database": lambda: handle_database(),
        "/schema": lambda: handle_schema(),
        "/provider": lambda: handle_provider(),
        "/stats": lambda: handle_database(),  # Alias
        "/history": lambda: handle_history(),
        "/export": lambda: handle_export(args),
        "/filter": lambda: handle_filter(args),
        "/clear": lambda: handle_clear(),
        "/samples": lambda: handle_samples(),
        "/edit-samples": lambda: handle_edit_samples(),
        "/notes": lambda: handle_notes(args),
    }
    
    handler = handlers.get(command)
    if handler:
        await handler()
    else:
        await send_message(f"❌ Unknown command: `{command}`. Type `/help` for available commands.")


async def handle_help():
    """Display help message with all available commands."""
    await send_message(MSG_HELP)


async def handle_status():
    """Display system health status for all services."""
    await send_message("Checking system status...")
    
    # Check all services
    api_ok, api_version = await check_api_health()
    db_ok, db_name = await check_database_health()
    llm_ok, llm_provider = await check_llm_health()
    
    # Display status
    await system_status_message(
        api_ok=api_ok,
        api_version=api_version,
        db_ok=db_ok,
        db_name=db_name,
        llm_ok=llm_ok,
        llm_provider=llm_provider
    )


async def handle_load(filename: Optional[str] = None):
    """Handle /load command - load CSV file by name."""
    try:
        files_response = await call_api("/data/files")
        files = files_response.get("files", [])
        
        if not files:
            await send_warning("No CSV files found in snapdata directory")
            return
        
        if filename:
            # Remove .csv extension if user included it
            filename_to_match = filename.replace('.csv', '')
            
            # Find matching file (case-insensitive, partial match)
            matching_file = None
            for file_info in files:
                file_name_base = file_info['filename'].replace('.csv', '')
                if filename_to_match.lower() in file_name_base.lower():
                    matching_file = file_info['filename']
                    break
            
            if matching_file:
                await load_file_by_name(matching_file)
            else:
                await send_error(f'File not found: {filename}\n\nAvailable files: {", ".join([f["filename"] for f in files])}')
            return
        
        # No filename provided - show file selection
        actions = []
        for file_info in files:
            actions.append(
                cl.Action(
                    name=f"load_{file_info['filename']}",
                    value=file_info['filename'],
                    label=f"📁 {file_info['filename']} ({file_info['size_mb']:.2f} MB)"
                )
            )
        
        await send_message(
            f"### 📂 Available CSV Files ({len(files)} found)\n\nClick a file to load it into the database, or use `/load filename`:",
            actions=actions
        )
        
    except Exception as e:
        await send_error(f"Error listing files: {str(e)}")


async def load_file_by_name(filename: str):
    """Load a file by its name."""
    import asyncio
    from ..services.startup import wait_for_load_and_refresh
    
    await send_message(f"📥 Loading `{filename}`...")
    
    try:
        # Extract fiscal year from filename
        fy_match = re.search(r'fy(\d{4})', filename, re.IGNORECASE)
        if fy_match:
            fiscal_year = int(fy_match.group(1))
        else:
            year_match = re.search(r'20(\d{2})', filename)
            if year_match:
                fiscal_year = int('20' + year_match.group(1))
            else:
                fiscal_year = DEFAULT_FISCAL_YEAR
        
        result = await call_api(
            "/data/load",
            method="POST",
            data={"fiscal_year": fiscal_year, "filename": filename}
        )
        
        job_id = result.get('job_id')
        
        success_msg = MSG_DATA_LOADING_INITIATED.format(
            job_id=job_id or 'N/A',
            status=result.get('status', 'Unknown'),
            filename=filename,
            fiscal_year=fiscal_year
        )
        
        await send_message(success_msg)
        
        # Start background task to monitor job and refresh filters when done
        if job_id:
            asyncio.create_task(wait_for_load_and_refresh(job_id))
        
    except Exception as e:
        await send_error(f"Error loading file: {str(e)}")


async def handle_files():
    """Handle /files command - list all available CSV files."""
    try:
        files_response = await call_api("/data/files")
        files = files_response.get("files", [])
        
        if not files:
            await send_warning("No CSV files found in snapdata directory")
            return
        
        content = f"### 📂 Available CSV Files ({len(files)} found)\n\n"
        content += f"**Directory:** `{files_response.get('snapdata_path', 'snapdata')}`\n\n"
        
        content += "| File | Size | Fiscal Year | Status |\n"
        content += "|------|------|-------------|--------|\n"
        
        for file_info in files:
            filename = file_info['filename']
            size = f"{file_info['size_mb']:.2f} MB"
            fy = file_info.get('fiscal_year', 'N/A')
            status = "✅ Loaded" if file_info.get('loaded', False) else "⚪ Not loaded"
            content += f"| `{filename}` | {size} | {fy} | {status} |\n"
        
        content += f"\n**Total Size:** {sum(f['size_mb'] for f in files):.2f} MB\n"
        content += f"\n💡 *Use `/load <filename>` to load a file*"
        
        await send_message(content)
        
    except Exception as e:
        await send_error(f"Error listing files: {str(e)}")


async def handle_upload():
    """Handle /upload command - upload CSV file from browser."""
    try:
        files = await cl.AskFileMessage(
            content="📤 **Upload CSV File**\n\nPlease select a CSV file to upload to the database.\n\n**Accepted formats:**\n- CSV files (.csv)\n- Maximum size: 100 MB\n\n**File naming:**\n- Include fiscal year in filename (e.g., `qc_pub_fy2023.csv`)\n- File will be saved to the snapdata directory",
            accept=["text/csv", ".csv"],
            max_size_mb=100,
            max_files=1,
            timeout=180,
        ).send()
        
        if not files:
            await send_warning("No file uploaded.")
            return
        
        uploaded_file = files[0]
        
        await send_message(f"📤 Uploading `{uploaded_file.name}`...")
        
        # Upload file to API
        result = await upload_file(uploaded_file.path, uploaded_file.name)
        
        file_info = result.get("file", {})
        
        success_msg = MSG_FILE_UPLOAD_SUCCESS.format(
            filename=file_info.get('filename', uploaded_file.name),
            size_mb=file_info.get('size_mb', 0),
            fiscal_year=file_info.get('fiscal_year', 'N/A')
        )
        
        await send_message(success_msg)
        
        # Ask if they want to load it now
        actions = [
            cl.Action(
                name=f"load_{file_info.get('filename')}",
                value=file_info.get('filename'),
                label=f"📥 Load Now"
            )
        ]
        
        await send_message(
            "Would you like to load this file into the database now?",
            actions=actions
        )
        
    except Exception as e:
        import traceback
        logger.error(f"Upload error: {e}\n{traceback.format_exc()}")
        await send_error(f"Error uploading file: {str(e)}")


async def handle_reset():
    """Handle /reset command - reset the database."""
    actions = [
        cl.Action(name="confirm_reset", value="yes", label="⚠️ Yes, Reset Database"),
        cl.Action(name="cancel_reset", value="no", label="❌ Cancel")
    ]
    
    await send_message(
        """### ⚠️ Reset Database

**Warning:** This will delete ALL data from the database!

- All households
- All household members
- All QC errors
- All load history

**This action cannot be undone.**

Are you sure you want to continue?""",
        actions=actions
    )


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
            content += f"- **Households:** {summary.get('total_households', 0):,}\n"
            content += f"- **Household Members:** {summary.get('total_members', 0):,}\n"
            content += f"- **QC Errors:** {summary.get('total_qc_errors', 0):,}\n"
            content += f"- **Data Loads:** {len(stats.get('by_fiscal_year', [])):,}\n\n"
            
            if summary.get('fiscal_years'):
                content += f"**Fiscal Years:** {', '.join(map(str, summary['fiscal_years']))}\n\n"
            
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
            value="refresh",
            label="🔄 Refresh",
            description="Refresh database statistics"
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
        
        content = "### 🗄️ Database Schema\n\n"
        
        db_info = schema.get("database", {})
        if db_info:
            content += f"**Database:** {db_info.get('name', 'SnapAnalyst')}\n"
            content += f"*{db_info.get('description', '')}*\n\n"
            if db_info.get('fiscal_years_available'):
                content += f"**Available Years:** {', '.join(map(str, db_info['fiscal_years_available']))}\n\n"
        
        tables = schema.get("tables", {})
        
        for table_name, table_info in tables.items():
            content += f"#### 📋 Table: `{table_name}`\n"
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
            content += "### 🔗 Relationships\n\n"
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


async def handle_provider():
    """Handle /provider command - show LLM provider info."""
    try:
        provider_info = await call_api("/chat/provider")
        
        training_enabled = provider_info.get('training_enabled', False)
        status_note = "" if training_enabled else MSG_LLM_TRAINING_NOTE
        
        content = MSG_LLM_PROVIDER_INFO.format(
            provider=provider_info.get('provider', 'Unknown').upper(),
            sql_model=provider_info.get('sql_model', 'Unknown'),
            sql_max_tokens=provider_info.get('sql_max_tokens', 'N/A'),
            sql_temperature=provider_info.get('sql_temperature', 'N/A'),
            summary_model=provider_info.get('summary_model', 'Unknown'),
            summary_max_tokens=provider_info.get('summary_max_tokens', 'N/A'),
            summary_max_prompt_size=provider_info.get('summary_max_prompt_size', 8000),
            status=provider_info.get('status', 'Unknown'),
            training_status='✅ Enabled' if training_enabled else '⚠️ Disabled (Performance Mode)',
            status_note=status_note
        )
        
        await send_message(content)
        
    except Exception as e:
        await send_error(f"Error fetching provider info: {str(e)}")


async def handle_history():
    """Handle /history command - show chat history."""
    history = cl.user_session.get("chat_history")
    query_count = cl.user_session.get("query_count")
    
    if not history:
        await send_message("📝 No chat history yet. Start asking questions!")
        return
    
    content = f"### 📝 Your Chat History ({len(history)} messages, {query_count} queries)\n\n"
    
    for i, entry in enumerate(history[-10:], 1):
        role = "👤" if entry["role"] == "user" else "🤖"
        timestamp = entry["timestamp"].split("T")[1][:8]
        content += f"{i}. [{timestamp}] {role} {entry['content'][:100]}...\n\n"
    
    await send_message(content)


async def handle_export(fiscal_year: Optional[str] = None):
    """Handle /export command - download all data to Excel."""
    try:
        await send_message("📥 Preparing your data export...")
        
        api_base_url = get_api_base_url()
        api_prefix = get_api_prefix()
        
        fy_param = ""
        data_scope = f"All years ({min(SUPPORTED_FISCAL_YEARS)}-{max(SUPPORTED_FISCAL_YEARS)})"
        
        if fiscal_year:
            try:
                fy = int(fiscal_year)
                if fy in SUPPORTED_FISCAL_YEARS:
                    fy_param = f"?fiscal_year={fy}"
                    data_scope = f"FY {fiscal_year}"
                    await send_message(f"📊 Exporting data for Fiscal Year {fy}...")
                else:
                    await send_warning(f"Invalid fiscal year: {fiscal_year}. Using all years.")
            except ValueError:
                await send_warning("Invalid fiscal year format. Using all years.")
        else:
            await send_message(f"📊 Exporting all data ({data_scope})...")
        
        download_url = f"{api_base_url}{api_prefix}/data/export/excel{fy_param}"
        
        content = MSG_EXCEL_EXPORT_READY.format(
            data_scope=data_scope,
            download_url=download_url
        )
        
        elements = [
            cl.Text(
                name="Download Link",
                content=f"Download URL: {download_url}",
                display="inline"
            )
        ]
        
        await send_message(content, elements=elements)
        
        tips = """### 💡 Pro Tips:

1. **README First**: The README sheet opens automatically and explains everything
2. **Code Lookups**: Use the code tables in README to decode numeric codes
3. **Filtering**: Use Excel's built-in filters on each data sheet
4. **Pivot Tables**: Create pivot tables for quick analysis
5. **Formulas**: Reference the README sheet for column descriptions

**Example analysis:**
- Filter Households by `status=2` (overissuance errors)
- Create pivot table by `state_name` and `snap_benefit`"""
        
        await send_message(tips)
        
    except Exception as e:
        await send_error(f"Error generating download: {str(e)}")


async def handle_filter(args: Optional[str] = None):
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
    cl.user_session.set("chat_history", [])
    cl.user_session.set("query_count", 0)
    await send_message("✅ Chat history cleared!")


async def handle_samples():
    """Display sample questions from file."""
    try:
        samples_path = Path("./sample_questions.md")
        if samples_path.exists():
            with open(samples_path, 'r') as f:
                file_content = f.read()
            
            await send_message(MSG_SAMPLES_HEADER.format(content=file_content))
        else:
            await send_message(MSG_SAMPLES_NOT_FOUND)
    except Exception as e:
        await send_error(f"Error loading samples: {str(e)}")


async def handle_edit_samples():
    """Allow editing of sample questions."""
    try:
        samples_path = Path("./sample_questions.md")
        
        if samples_path.exists():
            with open(samples_path, 'r') as f:
                current_content = f.read()
        else:
            current_content = "# Sample Questions\n\nAdd your team's frequently used queries here!\n"
        
        res = await cl.AskUserMessage(
            content=MSG_EDIT_SAMPLES_PROMPT.format(
                char_count=len(current_content),
                preview=current_content[:500]
            ),
            timeout=300
        ).send()
        
        if res:
            new_content = res['output']
            
            with open(samples_path, 'w') as f:
                f.write(new_content)
            
            await send_message(MSG_SAMPLES_UPDATED.format(
                char_count=len(new_content),
                path=samples_path.absolute()
            ))
        else:
            await send_message(MSG_EDIT_CANCELLED)
            
    except Exception as e:
        await send_error(f"Error editing samples: {str(e)}")


async def handle_notes(note_text: Optional[str] = None):
    """
    Handle /notes command - log user notes about LLM responses.
    
    Notes are logged to the LLM log file for tracking feedback
    and issues with generated responses.
    
    Args:
        note_text: The note content to log
    """
    if not note_text or not note_text.strip():
        await send_message(
            "📝 **Usage:** `/notes <your feedback>`\n\n"
            "Add notes about the last response - what worked well or what went wrong.\n\n"
            "**Examples:**\n"
            "- `/notes SQL was correct but missed the date filter`\n"
            "- `/notes Great summary, very helpful breakdown`\n"
            "- `/notes Query returned wrong columns for this question`"
        )
        return
    
    # Get context from session
    response_id = cl.user_session.get("last_response_id", "no_response")
    question = cl.user_session.get("last_question", "unknown")
    sql = cl.user_session.get("last_sql", "unknown")
    
    # Log to LLM log
    llm_logger.info(f"[USER NOTE] response_id={response_id} note={note_text.strip()}")
    llm_logger.info(f"[USER NOTE CONTEXT] response_id={response_id} question={question}")
    
    await send_message(f"📝 Note recorded. Thanks for the feedback!")
