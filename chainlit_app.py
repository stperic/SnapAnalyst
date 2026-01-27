"""
Chainlit Web UI for SnapAnalyst AI Chatbot

This is the THIN UI LAYER - all business logic is in the ui/ package.
This file only contains Chainlit decorators and routing.

Structure:
- ui/config.py: Constants, persona settings
- ui/api_client.py: API communication
- ui/formatters.py: HTML formatting
- ui/responses.py: Message templates with persona
- ui/handlers/: Business logic handlers
- ui/services/: Data processing services
"""

# Configure ONNX Runtime before any imports
# CRITICAL: Explicitly set thread count to prevent CPU affinity errors in LXC containers
# When thread count is explicit, ONNX Runtime skips automatic CPU affinity (which fails in LXC)
# See: https://github.com/chroma-core/chroma/issues/1420
import os  # noqa: I001 - Must be first to configure ONNX before other imports
if not os.environ.get('OMP_NUM_THREADS') or os.environ.get('OMP_NUM_THREADS') == '0':
    os.environ['OMP_NUM_THREADS'] = '4'

# Suppress noisy libraries BEFORE importing chainlit
# This must happen first to catch loggers before they're configured
import logging
from datetime import datetime

logging.getLogger("websockets").setLevel(logging.ERROR)
logging.getLogger("websockets.protocol").setLevel(logging.ERROR)
logging.getLogger("websockets.server").setLevel(logging.ERROR)
logging.getLogger("websockets.client").setLevel(logging.ERROR)
logging.getLogger("engineio").setLevel(logging.ERROR)
logging.getLogger("socketio").setLevel(logging.ERROR)

import chainlit as cl
from chainlit.types import ThreadDict

# Initialize centralized logging (suppresses additional noisy libraries)
from src.core.logging import setup_logging

setup_logging()

# Initialize Chainlit database tables on startup
from scripts.init_chainlit_db import init_chainlit_tables_sync

try:
    init_chainlit_tables_sync()
except Exception as e:
    logging.getLogger(__name__).warning(f"Could not initialize Chainlit tables: {e}")


# =============================================================================
# DATA PERSISTENCE (SQLAlchemy with PostgreSQL)
# =============================================================================

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer


@cl.data_layer
def get_data_layer():
    """Configure SQLAlchemy data layer for chat history persistence."""
    # Use the same DATABASE_URL from environment
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://snapanalyst:snapanalyst_dev_password@localhost:5432/snapanalyst_db")
    # Convert to asyncpg format if needed
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    return SQLAlchemyDataLayer(conninfo=db_url)


# =============================================================================
# AUTHENTICATION (First Login = Registration)
# =============================================================================

import asyncpg
import bcrypt


async def get_db_connection():
    """Get async database connection."""
    db_url = os.getenv("DATABASE_URL", "postgresql://snapanalyst:snapanalyst_dev_password@localhost:5432/snapanalyst_db")
    # Convert to asyncpg format
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgres://")
    return await asyncpg.connect(db_url)

async def get_user_by_email(email: str) -> dict | None:
    """Fetch user from database by email/identifier."""
    try:
        conn = await get_db_connection()
        row = await conn.fetchrow(
            "SELECT id, identifier, password_hash, metadata FROM users WHERE identifier = $1",
            email.lower()
        )
        await conn.close()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logging.getLogger(__name__).error(f"Error fetching user: {e}")
        return None

async def save_password_hash(email: str, password: str) -> bool:
    """Save password hash for a user (creates or updates)."""
    try:
        conn = await get_db_connection()
        # Hash the password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Update existing user or this will be called after Chainlit creates the user
        await conn.execute(
            """UPDATE users SET password_hash = $1 WHERE identifier = $2""",
            password_hash,
            email.lower()
        )

        await conn.close()
        logging.getLogger(__name__).info(f"Saved password hash for user: {email}")
        return True
    except Exception as e:
        logging.getLogger(__name__).error(f"Error saving password hash: {e}")
        return False

@cl.password_auth_callback
async def auth_callback(email: str, password: str) -> cl.User | None:
    """
    Authentication with persistent user accounts.

    - First login: Creates account with email + password
    - Next login: Validates password against stored hash

    Note: Use a valid email as your username. Your password will be securely hashed.
    """
    if not email or not password:
        return None

    email = email.lower().strip()

    # Check if user exists
    user = await get_user_by_email(email)

    if user is None:
        # First login = Registration
        # Return user object - Chainlit will create the user in DB
        # Then save password hash (after a small delay to let Chainlit create the user first)
        import asyncio
        async def save_password_delayed():
            await asyncio.sleep(0.5)  # Wait for Chainlit to create user
            await save_password_hash(email, password)
        asyncio.create_task(save_password_delayed())

        return cl.User(
            identifier=email,
            metadata={"role": "user", "provider": "credentials", "is_new": True}
        )

    # Existing user - validate password
    stored_hash = user.get("password_hash")

    if stored_hash is None:
        # Legacy user without password - update with new password
        try:
            conn = await get_db_connection()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await conn.execute(
                "UPDATE users SET password_hash = $1 WHERE identifier = $2",
                password_hash,
                email
            )
            await conn.close()
            return cl.User(
                identifier=email,
                metadata={"role": "user", "provider": "credentials"}
            )
        except Exception as e:
            logging.getLogger(__name__).error(f"Error updating legacy user: {e}")
            return None

    # Validate password
    try:
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            return cl.User(
                identifier=email,
                metadata={"role": "user", "provider": "credentials"}
            )
    except Exception as e:
        logging.getLogger(__name__).error(f"Password validation error: {e}")

    # Wrong password
    return None


# Import handlers from ui package
from ui.handlers.actions import (
    handle_cancel,
    handle_csv_download,
    handle_execute,
    handle_feedback_negative,
    handle_feedback_positive,
    handle_file_load,
    handle_followup,
    handle_refresh_database,
    handle_reset_cancel,
    handle_reset_confirm,
)
from ui.handlers.commands import handle_command
from ui.handlers.queries import handle_chat_query, handle_insight_request
from ui.handlers.settings import handle_settings_update
from ui.services.startup import initialize_session, setup_filter_settings

# =============================================================================
# CHAT RESUME (Restore previous chat sessions)
# =============================================================================

@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    """
    Called when a user resumes a previous chat session.
    Chainlit automatically displays the messages from the thread.
    We just need to restore our session state.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"on_chat_resume called for thread: {thread.get('id')}, name: {thread.get('name')}")
    logger.info(f"Thread has {len(thread.get('steps', []))} steps")

    # Initialize session for resumed chat
    await initialize_session()
    await setup_filter_settings()

    # Restore chat history to session
    for step in thread.get("steps", []):
        step_type = step.get("type")
        if step_type == "user_message":
            cl.user_session.get("chat_history").append({
                "timestamp": step.get("createdAt"),
                "role": "user",
                "content": step.get("output", "")
            })
        elif step_type == "assistant_message":
            cl.user_session.get("chat_history").append({
                "timestamp": step.get("createdAt"),
                "role": "assistant",
                "content": step.get("output", "")
            })

    logger.info(f"Restored {len(cl.user_session.get('chat_history', []))} messages to session")


# =============================================================================
# STARTERS - Centered prompts on empty chat (replaces show_readme_as_default)
# =============================================================================

@cl.set_starters
async def set_starters():
    """
    Display starter prompts when chat is empty.
    This creates the centered input experience shown in Chainlit GitHub screenshots.
    """
    return [
        cl.Starter(
            label="Error Rates by State",
            message="What is the payment error rate in 2023 for each state?",
        ),
        cl.Starter(
            label="Root Causes",
            message="What are the top 3 causes of payment errors?",
        ),
        cl.Starter(
            label="Error Trends",
            message="How have error rates changed from 2021 to 2023?",
        ),
    ]


# =============================================================================
# CHAINLIT EVENT HANDLERS
# =============================================================================

@cl.on_chat_start
async def start():
    """Initialize chat session."""
    # Initialize session variables
    await initialize_session()

    # Set up filter settings UI
    await setup_filter_settings()

    # Clean startup - no system status display
    # (System health checks still happen in the background via API calls)


@cl.on_settings_update
async def on_settings_update(settings: dict):
    """Handle filter settings updates."""
    await handle_settings_update(settings)


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages."""
    user_input = message.content.strip()

    # Capture attached files from message elements
    attached_files = []
    if message.elements:
        for element in message.elements:
            # Check if element is a file (has path attribute)
            if hasattr(element, 'path') and hasattr(element, 'name'):
                attached_files.append(element)

    # Store files in session for /memadd command
    cl.user_session.set("message_files", attached_files)

    # Update chat history
    history = cl.user_session.get("chat_history")
    history.append({
        "timestamp": datetime.now().isoformat(),
        "role": "user",
        "content": user_input
    })

    # Check for pending prompt confirmation
    from ui.handlers.commands.prompt_commands import handle_prompt_confirmation
    is_confirmation = await handle_prompt_confirmation(user_input)
    if is_confirmation:
        return

    # Handle insight requests (/? or /??)
    if user_input.startswith("/?"):
        await handle_insight_request(user_input)
        return

    # Handle special commands
    if user_input.startswith("/"):
        parts = user_input.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else None
        await handle_command(command, args)
        return

    # Normal chat query - send to LLM
    await handle_chat_query(user_input)


# =============================================================================
# ACTION CALLBACKS
# =============================================================================

@cl.action_callback("download_csv")
async def on_download_csv(action: cl.Action):
    """Handle CSV download action."""
    await handle_csv_download()


@cl.action_callback("execute")
async def on_execute(action: cl.Action):
    """Execute the pending SQL query."""
    await handle_execute()


@cl.action_callback("cancel")
async def on_cancel(action: cl.Action):
    """Cancel the pending query."""
    await handle_cancel()


@cl.action_callback("followup_*")
async def on_followup(action: cl.Action):
    """Handle follow-up question click."""
    await handle_followup(action.payload.get("question"))


@cl.action_callback("confirm_reset")
async def on_confirm_reset(action: cl.Action):
    """Handle database reset confirmation."""
    await handle_reset_confirm()


@cl.action_callback("cancel_reset")
async def on_cancel_reset(action: cl.Action):
    """Cancel database reset."""
    await handle_reset_cancel()


@cl.action_callback("load_*")
async def on_load_file(action: cl.Action):
    """Handle file loading."""
    await handle_file_load(action.payload.get("filename"))


@cl.action_callback("refresh_database")
async def on_refresh_database(action: cl.Action):
    """Refresh database statistics."""
    await handle_refresh_database()


@cl.action_callback("feedback_positive")
async def on_feedback_positive(action: cl.Action):
    """Handle positive feedback (thumbs up)."""
    await handle_feedback_positive(action.payload.get("response_id"))


@cl.action_callback("feedback_negative")
async def on_feedback_negative(action: cl.Action):
    """Handle negative feedback (thumbs down)."""
    await handle_feedback_negative(action.payload.get("response_id"))


@cl.action_callback("confirm_memreset")
async def on_confirm_memreset(action: cl.Action):
    """Handle memory reset confirmation."""
    from ui.handlers.actions import handle_memreset_confirm
    await handle_memreset_confirm()


@cl.action_callback("cancel_memreset")
async def on_cancel_memreset(action: cl.Action):
    """Cancel memory reset."""
    from ui.handlers.actions import handle_memreset_cancel
    await handle_memreset_cancel()


@cl.action_callback("confirm_prompt_update")
async def on_confirm_prompt_update(action: cl.Action):
    """Handle prompt update confirmation."""
    from ui.handlers.commands.prompt_commands import handle_prompt_confirmation
    await handle_prompt_confirmation("yes")


@cl.action_callback("cancel_prompt_update")
async def on_cancel_prompt_update(action: cl.Action):
    """Cancel prompt update."""
    from ui.handlers.commands.prompt_commands import handle_prompt_confirmation
    await handle_prompt_confirmation("no")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # This is handled by chainlit CLI
    pass
