"""
Data Commands Module

Handles data loading and file operations:
- /load: Load CSV files
- /files: List available files
- /upload: Upload CSV from browser
- /reset: Reset database
"""

import asyncio
import logging
import re

import chainlit as cl

# Import from src/ for business logic
from src.clients.api_client import call_api, upload_file

# Import centralized prompts
from src.core.prompts import (
    MSG_DATA_LOADING_INITIATED,
    MSG_FILE_UPLOAD_SUCCESS,
)

# Import from ui/ for UI-specific config and message helpers
from ...config import DEFAULT_FISCAL_YEAR
from ...responses import send_error, send_message, send_warning
from ...services.startup import wait_for_load_and_refresh

logger = logging.getLogger(__name__)


async def handle_load(filename: str | None = None):
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
                    payload={"filename": file_info['filename']},
                    label=f"{file_info['filename']} ({file_info['size_mb']:.2f} MB)"
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
    await send_message(f"Loading `{filename}`...")

    try:
        # Extract fiscal year from filename
        fy_match = re.search(r'fy(\d{4})', filename, re.IGNORECASE)
        if fy_match:
            fiscal_year = int(fy_match.group(1))
        else:
            year_match = re.search(r'20(\d{2})', filename)
            fiscal_year = int('20' + year_match.group(1)) if year_match else DEFAULT_FISCAL_YEAR

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

        content = f"### Available CSV Files ({len(files)} found)\n\n"
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
        content += "\n💡 *Use `/load <filename>` to load a file*"

        await send_message(content)

    except Exception as e:
        await send_error(f"Error listing files: {str(e)}")


async def handle_upload():
    """Handle /upload command - upload CSV file from browser."""
    try:
        files = await cl.AskFileMessage(
            content="**Upload CSV File**\n\nPlease select a CSV file to upload to the database.\n\n**Accepted formats:**\n- CSV files (.csv)\n- Maximum size: 100 MB\n\n**File naming:**\n- Include fiscal year in filename (e.g., `qc_pub_fy2023.csv`)\n- File will be saved to the snapdata directory",
            accept=["text/csv", ".csv"],
            max_size_mb=100,
            max_files=1,
            timeout=180,
        ).send()

        if not files:
            await send_warning("No file uploaded.")
            return

        uploaded_file = files[0]

        await send_message(f"Uploading `{uploaded_file.name}`...")

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
                payload={"filename": file_info.get('filename')},
                label="Load Now"
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
    # Store pending operation in session for the top-level callback
    cl.user_session.set("pending_confirmation", {"operation": "reset_database"})

    await cl.Message(
        content="""### Reset Database

**Warning:** This will delete ALL data (households, members, QC errors, load history).

**This action cannot be undone.** Are you sure?""",
        actions=[
            cl.Action(name="confirm_action", payload={"confirm": "yes"}, label="Yes, Reset Database"),
            cl.Action(name="confirm_action", payload={"confirm": "no"}, label="Cancel"),
        ],
    ).send()
