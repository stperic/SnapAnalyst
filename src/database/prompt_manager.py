"""
User Prompt Management

Helper functions for storing and retrieving custom LLM prompts per user.
Supports SQL generation prompts and KB insight prompts.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from src.core.logging import get_logger
from src.core.prompts import KB_INSIGHT_SYSTEM_PROMPT, VANNA_SQL_SYSTEM_PROMPT
from src.database.engine import get_db_context
from src.database.models import UserPrompt

logger = get_logger(__name__)


def get_user_prompt(user_id: str, prompt_type: str) -> str:
    """
    Get user's custom prompt or fallback to default.

    Args:
        user_id: User identifier
        prompt_type: 'sql' or 'kb'

    Returns:
        Prompt text (custom if exists, default otherwise)
    """
    if prompt_type not in ['sql', 'kb']:
        raise ValueError(f"Invalid prompt_type: {prompt_type}")

    try:
        with get_db_context() as session:
            stmt = select(UserPrompt).where(
                UserPrompt.user_id == user_id,
                UserPrompt.prompt_type == prompt_type
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                logger.debug(f"Using custom {prompt_type} prompt for user {user_id}")
                return result.prompt_text
            else:
                logger.debug(f"Using default {prompt_type} prompt for user {user_id}")
                return get_default_prompt(prompt_type)

    except Exception as e:
        logger.error(f"Error fetching prompt for {user_id}: {e}")
        return get_default_prompt(prompt_type)


def get_default_prompt(prompt_type: str) -> str:
    """
    Get system default prompt.

    Args:
        prompt_type: 'sql' or 'kb'

    Returns:
        Default prompt from prompts.py
    """
    if prompt_type == 'sql':
        return VANNA_SQL_SYSTEM_PROMPT
    elif prompt_type == 'kb':
        return KB_INSIGHT_SYSTEM_PROMPT
    else:
        raise ValueError(f"Invalid prompt_type: {prompt_type}")


def set_user_prompt(user_id: str, prompt_type: str, prompt_text: str) -> bool:
    """
    Set or update user's custom prompt.

    Args:
        user_id: User identifier
        prompt_type: 'sql' or 'kb'
        prompt_text: The custom prompt text

    Returns:
        True if successful, False otherwise
    """
    if prompt_type not in ['sql', 'kb']:
        raise ValueError(f"Invalid prompt_type: {prompt_type}")

    # Validate length
    if len(prompt_text) < 20 or len(prompt_text) > 5000:
        raise ValueError(f"Prompt must be between 20 and 5000 characters (got {len(prompt_text)})")

    try:
        with get_db_context() as session:
            # Check if prompt exists
            stmt = select(UserPrompt).where(
                UserPrompt.user_id == user_id,
                UserPrompt.prompt_type == prompt_type
            )
            existing = session.execute(stmt).scalar_one_or_none()

            if existing:
                # Update existing
                existing.prompt_text = prompt_text
                existing.updated_at = datetime.utcnow()
                logger.info(f"Updated {prompt_type} prompt for user {user_id}")
            else:
                # Create new
                new_prompt = UserPrompt(
                    user_id=user_id,
                    prompt_type=prompt_type,
                    prompt_text=prompt_text
                )
                session.add(new_prompt)
                logger.info(f"Created {prompt_type} prompt for user {user_id}")

            session.commit()
            return True

    except Exception as e:
        logger.error(f"Error setting prompt for {user_id}: {e}")
        return False


def reset_user_prompt(user_id: str, prompt_type: str) -> bool:
    """
    Reset user's prompt to default (delete custom prompt).

    Args:
        user_id: User identifier
        prompt_type: 'sql' or 'kb'

    Returns:
        True if successful, False otherwise
    """
    if prompt_type not in ['sql', 'kb']:
        raise ValueError(f"Invalid prompt_type: {prompt_type}")

    try:
        with get_db_context() as session:
            stmt = select(UserPrompt).where(
                UserPrompt.user_id == user_id,
                UserPrompt.prompt_type == prompt_type
            )
            existing = session.execute(stmt).scalar_one_or_none()

            if existing:
                session.delete(existing)
                session.commit()
                logger.info(f"Reset {prompt_type} prompt for user {user_id}")
                return True
            else:
                logger.debug(f"No custom {prompt_type} prompt to reset for user {user_id}")
                return True  # Not an error, already at default

    except Exception as e:
        logger.error(f"Error resetting prompt for {user_id}: {e}")
        return False


def has_custom_prompt(user_id: str, prompt_type: str) -> bool:
    """
    Check if user has a custom prompt.

    Args:
        user_id: User identifier
        prompt_type: 'sql' or 'kb'

    Returns:
        True if custom prompt exists, False otherwise
    """
    if prompt_type not in ['sql', 'kb']:
        raise ValueError(f"Invalid prompt_type: {prompt_type}")

    try:
        with get_db_context() as session:
            stmt = select(UserPrompt).where(
                UserPrompt.user_id == user_id,
                UserPrompt.prompt_type == prompt_type
            )
            result = session.execute(stmt).scalar_one_or_none()
            return result is not None

    except Exception as e:
        logger.error(f"Error checking prompt for {user_id}: {e}")
        return False
