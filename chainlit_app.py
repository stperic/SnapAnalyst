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
# CRITICAL: Multiple settings to completely disable CPU affinity in LXC containers
# See: https://github.com/chroma-core/chroma/issues/1420
import os  # noqa: I001 - Must be first to configure ONNX before other imports

if not os.environ.get("OMP_NUM_THREADS") or os.environ.get("OMP_NUM_THREADS") == "0":
    os.environ["OMP_NUM_THREADS"] = "4"
if not os.environ.get("ORT_DISABLE_CPU_EP_AFFINITY"):
    os.environ["ORT_DISABLE_CPU_EP_AFFINITY"] = "1"
if not os.environ.get("ORT_DISABLE_THREAD_AFFINITY"):
    os.environ["ORT_DISABLE_THREAD_AFFINITY"] = "1"
if not os.environ.get("OMP_WAIT_POLICY"):
    os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
if not os.environ.get("OMP_PROC_BIND"):
    os.environ["OMP_PROC_BIND"] = "false"

# Suppress noisy library warnings before imports
import warnings

warnings.filterwarnings("ignore", message="urllib3.*doesn't match a supported version")

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


# Filter out noisy Chainlit warnings (e.g. "SQLAlchemyDataLayer storage client is not initialized")
class _ChainlitLogFilter(logging.Filter):
    _suppressed = ("storage client is not initialized",)

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(s in msg for s in self._suppressed)


logging.getLogger("chainlit").addFilter(_ChainlitLogFilter())

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

from ui.services.feedback_training import handle_feedback_training


class TrainingFeedbackDataLayer(SQLAlchemyDataLayer):
    """Extends SQLAlchemyDataLayer to trigger Vanna training on feedback."""

    async def upsert_feedback(self, feedback) -> str:
        # Persist to PostgreSQL first (parent handles all DB logic)
        result = await super().upsert_feedback(feedback)
        # Trigger Vanna training (non-blocking, errors logged but not raised)
        await handle_feedback_training(
            feedback_for_id=feedback.forId,
            feedback_value=feedback.value,
            comment=getattr(feedback, "comment", None),
        )
        return result


@cl.data_layer
def get_data_layer():
    """Configure SQLAlchemy data layer for chat history persistence."""
    # Use the same DATABASE_URL from environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is required")
    # Convert to asyncpg format if needed
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    return TrainingFeedbackDataLayer(conninfo=db_url)


# =============================================================================
# AUTHENTICATION (First Login = Registration)
# =============================================================================

import asyncio

import asyncpg
import bcrypt

# Lazy-initialized connection pool for auth operations
_auth_pool: asyncpg.Pool | None = None
_auth_pool_lock: asyncio.Lock | None = None


def _get_auth_pool_lock() -> asyncio.Lock:
    """Get or create the auth pool lock (handles event loop lifecycle)."""
    global _auth_pool_lock
    if _auth_pool_lock is None:
        _auth_pool_lock = asyncio.Lock()
    return _auth_pool_lock


async def _get_auth_pool() -> asyncpg.Pool:
    """Get or create the auth connection pool (lazy-initialized, min=1, max=5)."""
    global _auth_pool
    if _auth_pool is not None and not _auth_pool._closed:
        return _auth_pool
    async with _get_auth_pool_lock():
        # Double-check after acquiring lock
        if _auth_pool is not None and not _auth_pool._closed:
            return _auth_pool
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is required")
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgres://")
        _auth_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)
    return _auth_pool


async def get_user_by_email(email: str) -> dict | None:
    """Fetch user from database by email/identifier."""
    try:
        pool = await _get_auth_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, identifier, password_hash, metadata FROM users WHERE identifier = $1", email.lower()
            )
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.getLogger(__name__).error(f"Error fetching user: {e}")
        return None


async def save_password_hash(email: str, password: str) -> bool:
    """Save password hash for a user (creates or updates)."""
    try:
        pool = await _get_auth_pool()
        async with pool.acquire() as conn:
            # Hash the password
            password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

            # Update existing user or this will be called after Chainlit creates the user
            await conn.execute(
                """UPDATE users SET password_hash = $1 WHERE identifier = $2""", password_hash, email.lower()
            )

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
        # Save password hash after Chainlit creates the user record.
        # We retry briefly since the user row is created asynchronously by Chainlit.
        # IMPORTANT: We await this to ensure the password is saved before returning.
        # A fire-and-forget approach risks the password never being saved, which would
        # allow any password on subsequent login via the legacy-user path.
        saved = False
        for _ in range(10):
            await asyncio.sleep(0.3)
            if await save_password_hash(email, password):
                saved = True
                break
        if not saved:
            logging.getLogger(__name__).error(f"Failed to save password hash for new user: {email}")

        return cl.User(identifier=email, metadata={"role": "user", "provider": "credentials", "is_new": True})

    # Existing user - validate password
    stored_hash = user.get("password_hash")

    if stored_hash is None:
        # Legacy user without password — check if this user was just created (within last 30s)
        # and the password save may have failed. For safety, only allow password set
        # for users created by Chainlit's data layer (no password_hash column yet).
        # Log a warning so admins can investigate.
        logging.getLogger(__name__).warning(
            f"User {email} has no password hash — setting password on first post-migration login"
        )
        try:
            pool = await _get_auth_pool()
            async with pool.acquire() as conn:
                password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                await conn.execute("UPDATE users SET password_hash = $1 WHERE identifier = $2", password_hash, email)
            return cl.User(identifier=email, metadata={"role": "user", "provider": "credentials"})
        except Exception as e:
            logging.getLogger(__name__).error(f"Error updating legacy user: {e}")
            return None

    # Validate password
    try:
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return cl.User(identifier=email, metadata={"role": "user", "provider": "credentials"})
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
    handle_vanna_reset_cancel,
    handle_vanna_reset_confirm,
)
from ui.handlers.commands import handle_command
from ui.handlers.queries import handle_chat_query, handle_insight_query
from ui.responses import send_message
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
    logger.debug(f"Resuming thread {thread.get('id')} ({len(thread.get('steps', []))} steps)")

    # Initialize session for resumed chat
    await initialize_session()
    await setup_filter_settings()

    # Register native slash commands for autocomplete
    await register_commands()

    # Restore chat history to session
    for step in thread.get("steps", []):
        step_type = step.get("type")
        if step_type == "user_message":
            cl.user_session.get("chat_history").append(
                {"timestamp": step.get("createdAt"), "role": "user", "content": step.get("output", "")}
            )
        elif step_type == "assistant_message":
            cl.user_session.get("chat_history").append(
                {"timestamp": step.get("createdAt"), "role": "assistant", "content": step.get("output", "")}
            )

    logger.debug(f"Restored {len(cl.user_session.get('chat_history', []))} messages to session")


# =============================================================================
# STARTERS - Centered prompts on empty chat (replaces show_readme_as_default)
# =============================================================================


@cl.set_starters
async def set_starters():
    """
    Display starter prompts when chat is empty.
    Prompts are defined in the active dataset configuration.
    """
    from datasets import get_active_dataset

    ds = get_active_dataset()
    prompts = ds.get_starter_prompts() if ds else []
    if not prompts:
        return None
    return [cl.Starter(label=p["label"], message=p["message"]) for p in prompts]


# =============================================================================
# CHAINLIT EVENT HANDLERS
# =============================================================================


async def register_commands():
    """Register native Chainlit tools as persistent buttons in the composer bar.

    Two mode buttons: Insights and Knowledge (they modify message handling).
    Settings is a push button injected via custom JS next to the attachment icon.
    """
    await cl.context.emitter.set_commands(
        [
            {"id": "Insights", "icon": "lightbulb", "description": "Analyze with previous query data", "button": True},
            {"id": "Knowledge", "icon": "book-open", "description": "Search knowledge base only", "button": True},
        ]
    )


@cl.on_chat_start
async def start():
    """Initialize chat session."""
    # Initialize session variables
    await initialize_session()

    # Set up filter settings UI
    await setup_filter_settings()

    # Register native slash commands for autocomplete
    await register_commands()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages."""
    user_input = message.content.strip()

    # Capture attached files from message elements
    attached_files = []
    if message.elements:
        for element in message.elements:
            # Check if element is a file (has path attribute)
            if hasattr(element, "path") and hasattr(element, "name"):
                attached_files.append(element)

    # Store files in session for panel upload actions
    cl.user_session.set("message_files", attached_files)

    # Update chat history
    history = cl.user_session.get("chat_history")
    history.append({"timestamp": datetime.now().isoformat(), "role": "user", "content": user_input})

    # Mode-based routing via native Chainlit tools (Insights / Knowledge)
    if message.command:
        cmd = message.command.lower()
        if cmd == "insights":
            if not user_input:
                await send_message("Please type your question with the Insights mode selected.")
                return
            await handle_insight_query(user_input, include_thread=True)
            return
        elif cmd == "knowledge":
            if not user_input:
                await send_message("Please type your question with the Knowledge mode selected.")
                return
            await handle_insight_query(user_input, include_thread=False)
            return

    # Handle slash commands (text-based /command + Enter)
    if user_input.startswith("/"):
        parts = user_input.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else None
        await handle_command(command, args)
        return

    # Default: SQL mode
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


# =============================================================================
# CONFIRMATION ACTION CALLBACKS
# Reliable pattern: cl.Message + actions + top-level @cl.action_callback
# (cl.AskActionMessage has known bugs causing buttons to become unresponsive)
# =============================================================================


@cl.action_callback("confirm_action")
async def on_confirm_action(action: cl.Action):
    """Handle confirmation for destructive operations (reset, memreset, prompt update)."""
    from ui.handlers.actions import (
        handle_memreset_cancel,
        handle_memreset_confirm,
        handle_reset_cancel,
        handle_reset_confirm,
    )

    # Remove buttons immediately to prevent double-clicks
    await action.remove()

    pending = cl.user_session.get("pending_confirmation")
    if not pending:
        return

    confirmed = action.payload.get("confirm") == "yes"
    operation = pending.get("operation")

    # Clear pending state
    cl.user_session.set("pending_confirmation", None)

    if operation == "reset_database":
        if confirmed:
            await handle_reset_confirm()
        else:
            await handle_reset_cancel()
    elif operation == "reset_memory":
        if confirmed:
            await handle_memreset_confirm()
        else:
            await handle_memreset_cancel()
    elif operation == "reset_vanna":
        if confirmed:
            await handle_vanna_reset_confirm()
        else:
            await handle_vanna_reset_cancel()


# =============================================================================
# PANEL ACTION CALLBACK (CustomElement JSX → Python via callAction)
# =============================================================================


@cl.action_callback("panel_action")
async def on_panel_action(action: cl.Action):
    """Handle actions from sidebar CustomElement panels (MemPanel, MemsqlPanel).

    The JSX components call callAction({name: 'panel_action', payload: {...}})
    after performing API operations (delete, reset, upload) via fetch().
    This callback refreshes the panel with fresh data.
    """
    payload = action.payload or {}
    panel_type = payload.get("type")
    panel_action = payload.get("action")

    if panel_type == "memsql" and panel_action == "refresh":
        from ui.handlers.commands.memsql_commands import handle_memsql_panel

        await handle_memsql_panel()

    elif panel_type == "mem" and panel_action == "refresh":
        from ui.handlers.commands.memory_commands import handle_mem_panel

        await handle_mem_panel()


@cl.action_callback("filter_applied")
async def on_filter_applied(action: cl.Action):
    """Handle filter change from FilterPanel sidebar."""
    payload = action.payload or {}
    state = payload.get("state")
    year = payload.get("fiscal_year")
    cl.user_session.set("current_state_filter", state or "All States")
    cl.user_session.set("current_year_filter", str(year) if year else "All Years")


@cl.action_callback("llm_settings_changed")
async def on_llm_settings_changed(action: cl.Action):
    """Handle LLM settings change from LlmPanel sidebar."""
    payload = action.payload or {}
    mode = payload.get("mode")  # "sql", "insights", or "knowledge"
    settings = payload.get("settings", {})
    if mode in ("sql", "insights", "knowledge", "summary"):
        cl.user_session.set(f"llm_{mode}_settings", settings)


@cl.action_callback("open_settings_panel")
async def on_open_settings_panel(action: cl.Action):
    """Dispatch from SettingsPanel navigation to the correct sub-panel."""
    payload = action.payload or {}
    panel = payload.get("panel", "settings")
    if panel == "settings":
        from ui.handlers.commands.info_commands import handle_settings_panel

        await handle_settings_panel()
    elif panel == "filter":
        from ui.handlers.commands.utility_commands import handle_filter

        await handle_filter()
    elif panel == "llm":
        from ui.handlers.commands.info_commands import handle_llm

        await handle_llm()
    elif panel == "mem":
        from ui.handlers.commands.memory_commands import handle_mem_panel

        await handle_mem_panel()
    elif panel == "memsql":
        from ui.handlers.commands.memsql_commands import handle_memsql_panel

        await handle_memsql_panel()
    elif panel == "database":
        from ui.handlers.commands.info_commands import handle_database_panel

        await handle_database_panel()


@cl.action_callback("open_readme_panel")
async def on_open_readme_panel(action: cl.Action):
    """Open the Readme panel in the sidebar."""
    from ui.handlers.commands.info_commands import handle_readme_panel

    await handle_readme_panel()


@cl.action_callback("close_sidebar")
async def on_close_sidebar(action: cl.Action):
    """Close the sidebar."""
    await cl.ElementSidebar.set_elements([])


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # This is handled by chainlit CLI
    pass
