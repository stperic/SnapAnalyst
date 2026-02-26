"""
Vanna LLM Provider Configuration

Uses Vanna 0.x API with ChromaDB for DDL storage and RAG-based SQL generation.

ARCHITECTURE:
- Vanna 0.x: ChromaDB_VectorStore stores DDL, documentation, example queries
- train(ddl=...) stores schema in ChromaDB for RAG retrieval
- generate_sql() retrieves relevant DDL via get_related_ddl() before generating SQL

INITIALIZATION FLOW:
1. Create Vanna 0.x instance (provider-specific class)
2. Connect to PostgreSQL database
3. Train with DDL from database schema
"""

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from typing import TYPE_CHECKING

# Configure ONNX Runtime before any Vanna/ChromaDB imports
# CRITICAL: Multiple settings to completely disable CPU affinity in LXC containers
# See: https://github.com/chroma-core/chroma/issues/1420
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

from psycopg2 import pool
from vanna.legacy.anthropic.anthropic_chat import Anthropic_Chat
from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
from vanna.legacy.openai.openai_chat import OpenAI_Chat

from src.core.config import settings
from src.core.logging import get_logger

if TYPE_CHECKING:
    from psycopg2.extensions import connection as Connection

logger = get_logger(__name__)


# =============================================================================
# THREAD-LOCAL STORAGE FOR USER CONTEXT (Multi-User Safety)
# =============================================================================

_thread_local = threading.local()


def set_request_custom_prompt(custom_prompt: str | None):
    """
    Set custom prompt for current request thread.

    Thread-safe: Each request gets its own storage, preventing cross-user contamination.

    Args:
        custom_prompt: Custom system prompt for this request
    """
    _thread_local.custom_prompt = custom_prompt


def get_request_custom_prompt() -> str | None:
    """
    Get custom prompt for current request thread.

    Returns:
        Custom prompt for this thread, or None if not set
    """
    return getattr(_thread_local, "custom_prompt", None)


def set_request_llm_params(params: dict | None):
    """
    Set per-request LLM parameters for current thread.

    Thread-safe: Each request gets its own storage.

    Args:
        params: Dict with temperature, top_p, max_tokens, model (all optional)
    """
    _thread_local.llm_params = params


def get_request_llm_params() -> dict | None:
    """
    Get per-request LLM parameters for current thread.

    Returns:
        LLM params dict or None if not set
    """
    return getattr(_thread_local, "llm_params", None)


# =============================================================================
# SHARED DATABASE CONNECTION POOL
# =============================================================================

_db_pool: PostgresConnectionPool | None = None


class PostgresConnectionPool:
    """
    PostgreSQL connection pool for efficient database access.

    Manages a pool of reusable connections to avoid connection overhead.
    Thread-safe and handles connection lifecycle automatically.

    Features:
    - Pre-ping: validates connections with SELECT 1 before use, discards stale ones
    - Connection recycling: replaces connections older than MAX_CONN_AGE_SECONDS

    IMPORTANT: Use get_shared_db_pool() instead of creating instances directly
    to ensure connection pool is shared across all agents.
    """

    MAX_CONN_AGE_SECONDS = 3600  # Recycle connections older than 1 hour

    def __init__(
        self,
        host: str,
        dbname: str,
        user: str,
        password: str,
        port: int = 5432,
        minconn: int = 2,
        maxconn: int = 20,
    ):
        """
        Initialize connection pool.

        Args:
            host: Database host
            dbname: Database name
            user: Database user
            password: Database password
            port: Database port
            minconn: Minimum connections to maintain (default: 2)
            maxconn: Maximum connections allowed (default: 20)
        """
        self._pool = pool.ThreadedConnectionPool(
            minconn,
            maxconn,
            host=host,
            dbname=dbname,
            user=user,
            password=password,
            port=port,
            connect_timeout=10,
        )
        self._conn_created_at: dict[int, float] = {}  # id(conn) -> timestamp
        self._lock = threading.Lock()
        logger.info(f"Created PostgreSQL connection pool: {host}:{port}/{dbname} (min={minconn}, max={maxconn})")

    def _is_connection_alive(self, conn: Connection) -> bool:
        """Test if a connection is still usable with a SELECT 1 pre-ping."""
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            # Discard any transaction state from the ping
            conn.rollback()
            return True
        except Exception:
            return False

    def _is_connection_expired(self, conn: Connection) -> bool:
        """Check if a connection has exceeded the max age."""
        with self._lock:
            created = self._conn_created_at.get(id(conn))
        if created is None:
            return False
        return (time.monotonic() - created) > self.MAX_CONN_AGE_SECONDS

    @contextmanager
    def get_connection(self) -> Connection:
        """
        Get a healthy connection from the pool.

        Pre-pings the connection and discards stale/expired ones.
        Retries once on failure to get a fresh connection.

        Yields:
            Database connection
        """
        conn = self._pool.getconn()
        with self._lock:
            self._conn_created_at.setdefault(id(conn), time.monotonic())

        # Check if connection is alive and not expired
        if not self._is_connection_alive(conn) or self._is_connection_expired(conn):
            # Discard the bad/old connection and get a fresh one
            with self._lock:
                self._conn_created_at.pop(id(conn), None)
            self._pool.putconn(conn, close=True)
            conn = self._pool.getconn()
            with self._lock:
                self._conn_created_at[id(conn)] = time.monotonic()

        try:
            yield conn
        finally:
            with self._lock:
                # Clean up tracking if pool will close this connection
                if conn.closed:
                    self._conn_created_at.pop(id(conn), None)
            self._pool.putconn(conn)

    def close_all(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            with self._lock:
                self._conn_created_at.clear()
            logger.info("Closed all PostgreSQL connections")

    def health_check(self) -> dict:
        """
        Check connection pool health.

        Returns:
            Health status dictionary
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return {
                "healthy": True,
                "connections": {
                    "min": self._pool.minconn,
                    "max": self._pool.maxconn,
                },
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}


_db_pool_lock = threading.Lock()


def get_shared_db_pool() -> PostgresConnectionPool:
    """
    Get or create the shared database connection pool.

    All agents share ONE connection pool to the database.
    Thread-safe: uses double-checked locking for initialization.

    Returns:
        Shared PostgresConnectionPool instance
    """
    global _db_pool
    if _db_pool is not None:
        return _db_pool
    with _db_pool_lock:
        if _db_pool is not None:
            return _db_pool
        # Parse database_url to extract components
        db_url = str(settings.database_url)
        from urllib.parse import urlparse

        parsed = urlparse(db_url)
        if not all([parsed.hostname, parsed.path, parsed.username]):
            raise ValueError("Invalid database_url format: missing hostname, path, or username")

        user = parsed.username
        password = parsed.password or ""
        host = parsed.hostname
        port = parsed.port or 5432
        dbname = parsed.path.lstrip("/")

        _db_pool = PostgresConnectionPool(
            host=host,
            dbname=dbname,
            user=user,
            password=password,
            port=int(port),
            minconn=2,  # Keep 2 warm connections
            maxconn=20,  # Allow up to 20 concurrent queries
        )
    return _db_pool


def shutdown_db_pool() -> None:
    """
    Shutdown the shared database connection pool.

    Called from the FastAPI lifespan shutdown handler (with a timeout)
    rather than via atexit, which can block indefinitely if connections
    are checked out when SIGTERM arrives.
    """
    global _db_pool
    if _db_pool:
        logger.info("Shutting down database connection pool...")
        _db_pool.close_all()
        _db_pool = None


# =============================================================================
# VANNA 0.x CLASSES (with ChromaDB for DDL storage)
# =============================================================================


class _QuietLogMixin:
    """Override Vanna's log() to use Python logging instead of raw print()."""

    def log(self, message: str, title: str = "Info"):
        logger.debug("%s: %s", title, message[:200] if len(message) > 200 else message)


class OpenAIVanna(_QuietLogMixin, ChromaDB_VectorStore, OpenAI_Chat):
    """Vanna 0.x class using OpenAI + ChromaDB for DDL storage."""

    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, config=config)

    def system_message(self, message: str) -> dict:
        """
        Override to append per-user custom prompt (from /prompt set) to Vanna's context.

        The base system prompt is already injected via initial_prompt in Vanna config,
        so it appears BEFORE DDL/docs. This override only adds per-user customizations.
        """
        custom_prompt = get_request_custom_prompt()
        if custom_prompt:
            combined = f"{message}\n\n{custom_prompt}"
            return {"role": "system", "content": combined}
        return {"role": "system", "content": message}

    def submit_prompt(self, prompt, **kwargs):
        """Override to apply per-request LLM params from thread-local storage.

        Note: temperature is passed via kwargs rather than mutating self.temperature
        to avoid thread-safety issues with the shared singleton instance.
        """
        params = get_request_llm_params()
        if params:
            if params.get("temperature") is not None:
                kwargs["temperature"] = params["temperature"]
            if params.get("top_p") is not None:
                kwargs["top_p"] = params["top_p"]
        return super().submit_prompt(prompt, **kwargs)


class AnthropicVanna(_QuietLogMixin, ChromaDB_VectorStore, Anthropic_Chat):
    """Vanna 0.x class using Anthropic + ChromaDB for DDL storage."""

    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Anthropic_Chat.__init__(self, config=config)

    def system_message(self, message: str) -> dict:
        """
        Override to append per-user custom prompt (from /prompt set) to Vanna's context.

        The base system prompt is already injected via initial_prompt in Vanna config,
        so it appears BEFORE DDL/docs. This override only adds per-user customizations.
        """
        custom_prompt = get_request_custom_prompt()
        if custom_prompt:
            combined = f"{message}\n\n{custom_prompt}"
            return {"role": "system", "content": combined}
        return {"role": "system", "content": message}

    def submit_prompt(self, prompt, **kwargs):
        """Override to apply per-request LLM params from thread-local storage.

        Note: temperature is passed via kwargs rather than mutating self.temperature
        to avoid thread-safety issues with the shared singleton instance.
        """
        params = get_request_llm_params()
        if params:
            if params.get("temperature") is not None:
                kwargs["temperature"] = params["temperature"]
            if params.get("top_p") is not None:
                kwargs["top_p"] = params["top_p"]
        return super().submit_prompt(prompt, **kwargs)


class AzureOpenAIVanna(_QuietLogMixin, ChromaDB_VectorStore, OpenAI_Chat):
    """
    Vanna 0.x class using Azure OpenAI-compatible endpoint + ChromaDB for DDL storage.

    Uses OpenAI SDK with base_url for Azure OpenAI compatibility endpoints.
    This approach works with Azure endpoints that provide OpenAI-compatible APIs.
    """

    def __init__(self, config=None):
        from openai import OpenAI

        ChromaDB_VectorStore.__init__(self, config=config)

        # Create OpenAI client with Azure base_url (OpenAI-compatible endpoint)
        # This is simpler than using AzureOpenAI and works with OpenAI-compatible endpoints
        azure_client = OpenAI(
            base_url=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
        )

        OpenAI_Chat.__init__(self, client=azure_client, config=config)

        # Set temperature to None - Azure OpenAI deployments may not support custom temperature
        # Setting to None prevents temperature from being passed to the API
        self.temperature = None

    def system_message(self, message: str) -> dict:
        """
        Override to append per-user custom prompt (from /prompt set) to Vanna's context.

        The base system prompt is already injected via initial_prompt in Vanna config,
        so it appears BEFORE DDL/docs. This override only adds per-user customizations.
        """
        custom_prompt = get_request_custom_prompt()
        if custom_prompt:
            combined = f"{message}\n\n{custom_prompt}"
            return {"role": "system", "content": combined}
        return {"role": "system", "content": message}

    def submit_prompt(self, prompt, **kwargs):
        """Override to apply per-request LLM params from thread-local storage.

        Note: temperature is passed via kwargs rather than mutating self.temperature
        to avoid thread-safety issues with the shared singleton instance.
        """
        params = get_request_llm_params()
        if params:
            if params.get("temperature") is not None:
                kwargs["temperature"] = params["temperature"]
            if params.get("top_p") is not None:
                kwargs["top_p"] = params["top_p"]
        return super().submit_prompt(prompt, **kwargs)


class OllamaVanna(_QuietLogMixin, ChromaDB_VectorStore):
    """
    Vanna 0.x class using Ollama + ChromaDB for DDL storage.

    Uses Ollama Python SDK for local LLM inference.
    """

    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        self.config = config or {}
        self.model = self.config.get("model", "llama3.1:8b")
        self.temperature = self.config.get("temperature", 0.7)

        # Import Ollama client
        import ollama

        self.client = ollama.Client(host=settings.ollama_base_url)

    def system_message(self, message: str) -> dict:
        """
        Override to append per-user custom prompt (from /prompt set) to Vanna's context.

        The base system prompt is already injected via initial_prompt in Vanna config,
        so it appears BEFORE DDL/docs. This override only adds per-user customizations.
        """
        custom_prompt = get_request_custom_prompt()
        if custom_prompt:
            combined = f"{message}\n\n{custom_prompt}"
            return {"role": "system", "content": combined}
        return {"role": "system", "content": message}

    def submit_prompt(self, prompt, **kwargs):
        """Submit prompt to Ollama for completion."""
        if prompt is None or len(prompt) == 0:
            raise Exception("Prompt is None or empty")

        # Convert prompt to Ollama format
        messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]

        # Get model from kwargs or use default
        model = kwargs.get("model", self.model)

        # Apply per-request LLM params from thread-local storage
        temperature = self.temperature
        options = {}
        params = get_request_llm_params()
        if params:
            if params.get("temperature") is not None:
                temperature = params["temperature"]
            if params.get("top_p") is not None:
                options["top_p"] = params["top_p"]

        options["temperature"] = temperature

        # Call Ollama
        response = self.client.chat(
            model=model,
            messages=messages,
            options=options,
        )

        return response["message"]["content"]

    def generate_question(self, sql: str, **kwargs) -> str:
        """Generate a question from SQL (required by Vanna base class)."""
        prompt = f"Generate a natural language question that this SQL query answers:\n\n{sql}"
        return self.submit_prompt([{"role": "user", "content": prompt}], **kwargs)


# Global Vanna instance (cached, thread-safe)
_vanna_instance = None
_vanna_trained = False
_vanna_lock = threading.Lock()


def _get_vanna_instance():
    """
    Get or create the Vanna 0.x instance with ChromaDB.

    Thread-safe: uses double-checked locking to prevent duplicate initialization.

    Returns:
        Configured Vanna instance with DDL stored in ChromaDB
    """
    global _vanna_instance

    if _vanna_instance is not None:
        return _vanna_instance

    with _vanna_lock:
        if _vanna_instance is not None:
            return _vanna_instance

    from src.core.prompts import VANNA_SQL_SYSTEM_PROMPT

    provider = settings.llm_provider
    model = settings.sql_model
    chroma_path = f"{settings.vanna_chromadb_path}/vanna_ddl"

    logger.debug(f"Creating Vanna 0.x instance with ChromaDB at {chroma_path}")

    # Common config: initial_prompt places our system prompt BEFORE DDL/docs in the LLM context
    base_config = {
        "path": chroma_path,
        "model": model,
        "initial_prompt": VANNA_SQL_SYSTEM_PROMPT,
        "n_results_sql": settings.vanna_n_results_sql,
        "n_results_documentation": settings.vanna_n_results_docs,
        "log_level": "WARNING",
    }

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")

        _vanna_instance = OpenAIVanna(
            config={
                **base_config,
                "api_key": settings.openai_api_key,
            }
        )
        logger.debug(f"Created OpenAI Vanna with model: {model}")

    elif provider == "azure_openai":
        if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
            raise ValueError("Azure OpenAI endpoint and API key not configured")

        _vanna_instance = AzureOpenAIVanna(
            config={
                **base_config,
            }
        )
        logger.debug(f"Created Azure OpenAI Vanna with model: {model}")

    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key not configured")

        _vanna_instance = AnthropicVanna(
            config={
                **base_config,
                "api_key": settings.anthropic_api_key,
            }
        )
        logger.debug(f"Created Anthropic Vanna with model: {model}")

    elif provider == "ollama":
        _vanna_instance = OllamaVanna(
            config={
                **base_config,
                "temperature": 0.1,
            }
        )
        logger.debug(f"Created Ollama Vanna with model: {model} at {settings.ollama_base_url}")

    else:
        raise ValueError(f"Unsupported provider for Vanna 0.x: {provider}")

    # Connect to PostgreSQL
    db_url = str(settings.database_url)
    from urllib.parse import urlparse

    parsed = urlparse(db_url)
    if parsed.hostname and parsed.username:
        _vanna_instance.connect_to_postgres(
            host=parsed.hostname,
            dbname=parsed.path.lstrip("/"),
            user=parsed.username,
            password=parsed.password or "",
            port=parsed.port or 5432,
        )
        logger.debug(f"Connected Vanna to PostgreSQL: {parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}")

    return _vanna_instance


def train_vanna_with_ddl(force_retrain: bool = False):
    """
    Train Vanna with DDL from the database.

    This stores DDL in ChromaDB for RAG retrieval during ask().
    Checks if DDL is already in ChromaDB before re-training.

    Args:
        force_retrain: If True, re-train even if DDL already exists
    """
    global _vanna_trained

    if _vanna_trained and not force_retrain:
        logger.info("Vanna already trained this session, skipping")
        return

    vn = _get_vanna_instance()

    try:
        # Check if DDL is already in ChromaDB
        existing_data = vn.get_training_data()
        ddl_count = len(existing_data[existing_data["training_data_type"] == "ddl"]) if not existing_data.empty else 0

        if ddl_count > 0 and not force_retrain:
            logger.debug(f"Vanna already has {ddl_count} DDL statements in ChromaDB, skipping training")
            _vanna_trained = True
            return

        logger.debug(f"Training Vanna with DDL (existing: {ddl_count}, force: {force_retrain})")

        # Get DDL from database
        from src.database.ddl_extractor import get_all_ddl_statements

        ddl_statements = get_all_ddl_statements(include_samples=True)
        logger.debug(f"Training Vanna with {len(ddl_statements)} DDL statements")

        # Suppress verbose "Adding ddl:" print statements from Vanna
        ddl_success, ddl_fail = 0, 0
        with redirect_stdout(StringIO()):
            for i, ddl in enumerate(ddl_statements):
                try:
                    vn.train(ddl=ddl)
                    ddl_success += 1
                except Exception as e:
                    ddl_fail += 1
                    logger.warning(f"Failed to train DDL {i + 1}: {e}")
        logger.debug(f"DDL training: {ddl_success} succeeded, {ddl_fail} failed out of {len(ddl_statements)}")

        # Add all documentation files from datasets/snap/
        from src.services.kb_chromadb import _chunk_text
        from src.services.llm_training import get_documentation_files

        doc_success, doc_fail = 0, 0
        for doc_path in get_documentation_files():
            try:
                doc_text = doc_path.read_text(encoding="utf-8")
                chunks = _chunk_text(doc_text, filename=doc_path.name)
                with redirect_stdout(StringIO()):
                    for chunk in chunks:
                        vn.train(documentation=chunk)
                doc_success += len(chunks)
                logger.debug(f"Trained with {doc_path.name} ({len(chunks)} chunks)")
            except Exception as e:
                doc_fail += 1
                logger.warning(f"Failed to train {doc_path.name}: {e}")

        # Add query examples from training data folder
        from src.services.llm_training import load_training_examples

        examples = load_training_examples()
        example_success, example_fail = 0, 0
        if examples:
            with redirect_stdout(StringIO()):
                for ex in examples:
                    question = ex.get("question", "")
                    sql = ex.get("sql", "")
                    if question and sql:
                        try:
                            vn.train(question=question, sql=sql)
                            example_success += 1
                        except Exception as e:
                            example_fail += 1
                            logger.warning(f"Failed to train example '{question[:50]}': {e}")
            logger.debug(f"Query examples: {example_success}/{len(examples)} trained")

        _vanna_trained = True
        logger.debug(
            f"Vanna training complete - DDL: {ddl_success}, docs: {doc_success}, "
            f"examples: {example_success}, failures: {ddl_fail + doc_fail + example_fail}"
        )

    except Exception as e:
        logger.error(f"Failed to train Vanna: {e}")
        raise


def train_vanna(force_retrain: bool = False, reload_training_data: bool = False) -> dict:
    """
    Reset and retrain Vanna with DDL from the database.

    Clears all existing training data, then retrains with DDL extracted from
    PostgreSQL. Optionally reloads documentation and query examples from the
    training data folder (datasets/snap/training/).

    Args:
        force_retrain: If True, re-train even if DDL already exists
        reload_training_data: If True, also reload docs + query examples from training folder

    Returns:
        Dict with counts: {"ddl": N, "documentation": N, "sql": N}
    """
    global _vanna_trained

    vn = _get_vanna_instance()
    counts = {"ddl": 0, "documentation": 0, "sql": 0}

    # Clear existing training data to prevent duplicate accumulation
    try:
        existing_data = vn.get_training_data()
        if not existing_data.empty:
            ids_to_remove = existing_data["id"].tolist()
            logger.info(f"Clearing {len(ids_to_remove)} existing training entries")
            with redirect_stdout(StringIO()):
                for training_id in ids_to_remove:
                    try:
                        vn.remove_training_data(id=training_id)
                    except Exception as e:
                        logger.debug(f"Could not remove training data {training_id}: {e}")
    except Exception as e:
        logger.warning(f"Could not clear existing training data: {e}")

    # Determine which tables to train on
    from src.database.ddl_extractor import get_all_ddl_statements

    # Full mode: all tables DDL
    ddl_statements = get_all_ddl_statements(include_samples=True)
    logger.info(f"Training with {len(ddl_statements)} DDL statements")

    with redirect_stdout(StringIO()):
        for i, ddl in enumerate(ddl_statements):
            try:
                vn.train(ddl=ddl)
                counts["ddl"] += 1
            except Exception as e:
                logger.warning(f"Failed to train DDL {i + 1}: {e}")

    # Optionally reload training data from the training folder
    if reload_training_data:
        from src.services.kb_chromadb import _chunk_text
        from src.services.llm_training import get_documentation_files, load_training_examples

        # Load documentation files (.md, .txt)
        for doc_path in get_documentation_files():
            try:
                doc_text = doc_path.read_text(encoding="utf-8")
                chunks = _chunk_text(doc_text, filename=doc_path.name)
                with redirect_stdout(StringIO()):
                    for chunk in chunks:
                        vn.train(documentation=chunk)
                counts["documentation"] += len(chunks)
                logger.debug(f"Trained with {doc_path.name} ({len(chunks)} chunks)")
            except Exception as e:
                logger.warning(f"Failed to train {doc_path.name}: {e}")

        # Load query examples (.json)
        examples = load_training_examples()
        if examples:
            with redirect_stdout(StringIO()):
                for ex in examples:
                    question = ex.get("question", "")
                    sql = ex.get("sql", "")
                    explanation = ex.get("explanation", "")
                    if question and sql:
                        train_question = f"{question} ({explanation})" if explanation else question
                        try:
                            vn.train(question=train_question, sql=sql)
                            counts["sql"] += 1
                        except Exception as e:
                            logger.warning(f"Failed to train example '{question[:50]}': {e}")
            logger.info(f"Trained with {counts['sql']}/{len(examples)} query examples")

    _vanna_trained = True
    logger.info(f"Vanna training complete: {counts}")
    return counts


# =============================================================================
# INITIALIZATION
# =============================================================================


def initialize_vanna():
    """
    Initialize Vanna: create the 0.x instance and train with DDL.

    This is the main entry point for LLM service initialization.
    Creates the Vanna instance (with ChromaDB) and trains it with
    DDL from the database.
    """
    vn = _get_vanna_instance()
    train_vanna_with_ddl()
    logger.info(f"Vanna initialized: {settings.llm_provider.upper()} / {settings.sql_model}")
    return vn
