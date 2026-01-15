"""
Action Handlers

Handles button click actions (CSV download, reset, file load, feedback, etc.)
Uses centralized message templates from src/core/prompts.py.

All messages use APP_PERSONA (SnapAnalyst) - the app persona.
"""

import chainlit as cl
import csv
import os
import re
from datetime import datetime
from typing import Optional
import logging

# Import from src/ for business logic
from src.clients.api_client import call_api

# Import from ui/ for UI-specific config and responses
from ..config import APP_PERSONA, DEFAULT_FISCAL_YEAR
from ..responses import (
    send_message, send_error,
    csv_ready_message, no_results_message, csv_error_message
)

# Import centralized prompts
from src.core.prompts import (
    MSG_DATA_LOADING_INITIATED,
    MSG_DATABASE_RESET_COMPLETE,
)

# Import LLM logger for feedback logging
from src.core.logging import get_llm_logger

logger = logging.getLogger(__name__)
llm_logger = get_llm_logger()


async def handle_csv_download():
    """
    Handle CSV download action - create CSV file on-demand.
    Called when user clicks the CSV download button.
    """
    try:
        # Get stored results from session
        results = cl.user_session.get("last_query_results")
        
        if not results or len(results) == 0:
            await no_results_message()
            return
        
        # Create CSV file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"query_results_{timestamp}.csv"
        csv_file_path = f"/tmp/{csv_filename}"
        
        headers = list(results[0].keys())
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results)
        
        # Calculate file size
        file_size_bytes = os.path.getsize(csv_file_path)
        file_size_kb = file_size_bytes / 1024
        
        # Create file element
        file_element = cl.File(
            name=csv_filename,
            path=csv_file_path,
            display="inline"
        )
        
        # Send personalized response
        await csv_ready_message(
            filename=csv_filename,
            row_count=len(results),
            column_count=len(headers),
            file_size_kb=file_size_kb,
            file_element=file_element
        )
        
    except Exception as e:
        logger.error(f"Error creating CSV: {e}")
        await csv_error_message(str(e))


async def handle_execute():
    """
    Handle execute action - run pending SQL query.
    Called when user confirms query execution.
    """
    from .queries import execute_pending_query
    await execute_pending_query()


async def handle_cancel():
    """
    Handle cancel action - cancel pending query.
    """
    cl.user_session.set("pending_sql", None)
    cl.user_session.set("pending_question", None)
    await send_message("✅ Query cancelled.")


async def handle_followup(question: str):
    """
    Handle follow-up question click.
    
    Args:
        question: The follow-up question to execute
    """
    from .queries import handle_chat_query
    
    await cl.Message(content=question, author="User").send()
    await handle_chat_query(question)


async def handle_reset_confirm():
    """
    Handle database reset confirmation.
    Called when user confirms they want to reset the database.
    """
    await send_message("⚙️ Resetting database...")
    
    try:
        result = await call_api("/data/reset", method="POST", data={"confirm": True})
        
        await send_message(MSG_DATABASE_RESET_COMPLETE.format(
            message=result.get('message', 'All data has been cleared')
        ))
        
    except Exception as e:
        await send_error(f"Error resetting database: {str(e)}")


async def handle_reset_cancel():
    """
    Handle reset cancellation.
    """
    await send_message("✅ Database reset cancelled. No changes made.")


async def handle_file_load(filename: str):
    """
    Handle file loading action.
    Called when user clicks to load a specific file.
    
    Args:
        filename: Name of the file to load
    """
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
        
        await send_message(MSG_DATA_LOADING_INITIATED.format(
            job_id=job_id or 'N/A',
            status=result.get('status', 'Unknown'),
            filename=filename,
            fiscal_year=fiscal_year
        ))
        
        # Start background task to monitor job and refresh filters when done
        if job_id:
            asyncio.create_task(wait_for_load_and_refresh(job_id))
        
    except Exception as e:
        await send_error(f"Error loading file: {str(e)}")


async def handle_refresh_database():
    """
    Handle database stats refresh action.
    Called when user clicks the refresh button on database stats.
    """
    from .commands import handle_database
    await handle_database()


async def handle_feedback_positive(response_id: str):
    """
    Handle positive feedback (thumbs up) for an LLM response.
    Logs the feedback to the LLM log file.
    
    Args:
        response_id: The unique ID of the response being rated
    """
    # Get context from session
    question = cl.user_session.get("last_question", "unknown")
    sql = cl.user_session.get("last_sql", "unknown")
    
    # Log to LLM log
    llm_logger.info(f"[FEEDBACK] rating=positive response_id={response_id} question={question}")
    llm_logger.info(f"[FEEDBACK SQL] response_id={response_id} sql={sql}")
    
    # Acknowledge to user
    await send_message("👍 Thanks for the feedback! This helps improve responses.")


async def handle_feedback_negative(response_id: str):
    """
    Handle negative feedback (thumbs down) for an LLM response.
    Logs the feedback to the LLM log file.
    
    Args:
        response_id: The unique ID of the response being rated
    """
    # Get context from session
    question = cl.user_session.get("last_question", "unknown")
    sql = cl.user_session.get("last_sql", "unknown")
    
    # Log to LLM log
    llm_logger.info(f"[FEEDBACK] rating=negative response_id={response_id} question={question}")
    llm_logger.info(f"[FEEDBACK SQL] response_id={response_id} sql={sql}")
    
    # Acknowledge and suggest using /notes
    await send_message("👎 Thanks for the feedback. Use `/notes <your feedback>` to add details about what went wrong.")
