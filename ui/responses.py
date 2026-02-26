"""
Responses

Message builders with consistent persona.
All messages from the assistant should use these functions to ensure
consistent voice and branding.

Templates are imported from src/core/prompts.py for centralized management.
"""

import chainlit as cl

from src.core.prompts import (
    MSG_CSV_ERROR,
    MSG_CSV_NO_RESULTS,
    MSG_CSV_READY,
    MSG_FILTER_APPLIED,
    MSG_FILTER_CLEARED,
    MSG_SYSTEM_DEGRADED,
    MSG_SYSTEM_READY,
    MSG_SYSTEM_STATUS,
    MSG_WELCOME,
)

from .config import AI_PERSONA, APP_PERSONA


async def send_message(
    content: str, elements: list | None = None, actions: list | None = None, author: str = APP_PERSONA
) -> cl.Message:
    """
    Send a message with the app persona.

    Args:
        content: Message content
        elements: Optional list of Chainlit elements (files, images, etc.)
        actions: Optional list of Chainlit actions (buttons)
        author: Message author (defaults to APP_PERSONA)

    Returns:
        The sent message
    """
    msg = cl.Message(content=content, elements=elements, actions=actions, author=author)
    await msg.send()
    return msg


async def send_ai_message(content: str, elements: list | None = None, actions: list | None = None) -> cl.Message:
    """
    Send a message with the AI persona.

    Use this for AI-generated responses (query answers, analysis).

    Args:
        content: Message content
        elements: Optional list of Chainlit elements
        actions: Optional list of Chainlit actions

    Returns:
        The sent message
    """
    return await send_message(content, elements, actions, author=AI_PERSONA)


async def send_error(content: str) -> cl.Message:
    """Send an error message with the app persona."""
    return await send_message(content)


async def send_warning(content: str) -> cl.Message:
    """Send a warning message with the app persona."""
    return await send_message(content)


# =============================================================================
# SPECIFIC MESSAGE TEMPLATES
# =============================================================================


async def csv_ready_message(
    filename: str, row_count: int, column_count: int, file_size_kb: float, file_element: cl.File
) -> cl.Message:
    """Send CSV ready message with file download."""
    content = MSG_CSV_READY.format(
        row_count=row_count, column_count=column_count, file_size_kb=file_size_kb, filename=filename
    )
    return await send_message(content, elements=[file_element])


async def no_results_message() -> cl.Message:
    """Send message when no query results are available for export."""
    return await send_message(MSG_CSV_NO_RESULTS)


async def csv_error_message(error: str) -> cl.Message:
    """Send CSV creation error message."""
    return await send_message(MSG_CSV_ERROR.format(error=error))


async def system_status_message(
    api_ok: bool, api_version: str, db_ok: bool, db_name: str, llm_ok: bool, llm_provider: str
) -> cl.Message:
    """Send system status message on startup."""
    api_status = "✅" if api_ok else "❌"
    db_status = "✅" if db_ok else "❌"
    llm_status = "✅" if llm_ok else "❌"

    all_ok = api_ok and db_ok and llm_ok
    ready_message = MSG_SYSTEM_READY if all_ok else MSG_SYSTEM_DEGRADED

    content = MSG_SYSTEM_STATUS.format(
        api_status=api_status,
        api_version=api_version,
        db_status=db_status,
        db_name=db_name,
        llm_status=llm_status,
        llm_provider=llm_provider,
        ready_message=ready_message,
    )
    return await send_message(content)


async def welcome_message() -> cl.Message:
    """Send welcome message after startup."""
    return await cl.Message(content=MSG_WELCOME).send()


async def filter_applied_message(state: str | None, year: int | None) -> cl.Message:
    """Send filter applied confirmation message."""
    if state or year:
        content = MSG_FILTER_APPLIED.format(state=state or "All", year=year or "All")
    else:
        content = MSG_FILTER_CLEARED

    return await send_message(content)
