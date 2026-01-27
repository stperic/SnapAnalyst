"""
Vanna LLM Provider Configuration

Uses LegacyVannaAdapter to bridge Vanna 0.x (with DDL training via ChromaDB)
to Vanna 2.x Agent architecture.

ARCHITECTURE:
- Vanna 0.x: ChromaDB_VectorStore stores DDL, documentation, example queries
- LegacyVannaAdapter: Wraps 0.x instance for 2.x Agent compatibility
- train(ddl=...) stores schema in ChromaDB for RAG retrieval
- ask() retrieves relevant DDL via get_related_ddl() before generating SQL

INITIALIZATION FLOW:
1. Create Vanna 0.x instance (MyVanna class)
2. Connect to PostgreSQL database
3. Train with DDL from database schema
4. Wrap with LegacyVannaAdapter for 2.x compatibility
"""

from __future__ import annotations

import atexit
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pandas as pd

# Configure ONNX Runtime before any Vanna/ChromaDB imports
# CRITICAL: Explicitly set thread count to prevent CPU affinity errors in LXC containers
# When thread count is explicit, ONNX Runtime skips automatic CPU affinity (which fails in LXC)
# See: https://github.com/chroma-core/chroma/issues/1420
if not os.environ.get('OMP_NUM_THREADS') or os.environ.get('OMP_NUM_THREADS') == '0':
    os.environ['OMP_NUM_THREADS'] = '4'

# Azure OpenAI support
from psycopg2 import pool

# Vanna 2.x agent imports
from vanna import Agent, AgentConfig
from vanna.core.user import RequestContext, User, UserResolver
from vanna.integrations.anthropic.llm import AnthropicLlmService
from vanna.integrations.openai.llm import OpenAILlmService
from vanna.legacy.adapter import LegacyVannaAdapter
from vanna.legacy.anthropic.anthropic_chat import Anthropic_Chat
from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore

# Vanna 2.x legacy imports (for 0.x-style DDL training with ChromaDB)
from vanna.legacy.openai.openai_chat import OpenAI_Chat

from src.core.config import settings
from src.core.logging import get_logger

if TYPE_CHECKING:
    from psycopg2.extensions import connection as Connection

logger = get_logger(__name__)


# =============================================================================
# SHARED DATABASE CONNECTION POOL
# =============================================================================

_db_pool: PostgresConnectionPool | None = None


class PostgresConnectionPool:
    """
    PostgreSQL connection pool for efficient database access.

    Manages a pool of reusable connections to avoid connection overhead.
    Thread-safe and handles connection lifecycle automatically.

    IMPORTANT: Use get_shared_db_pool() instead of creating instances directly
    to ensure connection pool is shared across all agents.
    """

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
        logger.info(
            f"Created PostgreSQL connection pool: {host}:{port}/{dbname} "
            f"(min={minconn}, max={maxconn})"
        )

    @contextmanager
    def get_connection(self) -> Connection:
        """
        Get a connection from the pool.

        Yields:
            Database connection

        Example:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users")
        """
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def close_all(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
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
                }
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }


def get_shared_db_pool() -> PostgresConnectionPool:
    """
    Get or create the shared database connection pool.

    All agents share ONE connection pool to the database.
    This prevents memory leaks and optimizes connection usage.

    Returns:
        Shared PostgresConnectionPool instance
    """
    global _db_pool
    if _db_pool is None:
        # Parse database_url to extract components
        db_url = str(settings.database_url)
        # Format: postgresql://user:password@host:port/dbname
        # Use psycopg2 to parse
        import re
        match = re.match(
            r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)',
            db_url
        )
        if not match:
            raise ValueError(f"Invalid database_url format: {db_url}")

        user, password, host, port, dbname = match.groups()

        _db_pool = PostgresConnectionPool(
            host=host,
            dbname=dbname,
            user=user,
            password=password,
            port=int(port),
            minconn=2,   # Keep 2 warm connections
            maxconn=20,  # Allow up to 20 concurrent queries
        )
    return _db_pool


def shutdown_db_pool() -> None:
    """
    Shutdown the shared database connection pool.

    Called automatically on application exit via atexit hook.
    """
    global _db_pool
    if _db_pool:
        logger.info("Shutting down database connection pool...")
        _db_pool.close_all()
        _db_pool = None


# Register shutdown hook
atexit.register(shutdown_db_pool)


# =============================================================================
# SQL RUNNER
# =============================================================================


class PostgresRunner:
    """
    PostgreSQL SQL runner for Vanna RunSqlTool.

    Implements the Vanna SqlRunner interface:
    - async run_sql(args, context) -> DataFrame

    Executes SQL queries using a connection pool for efficiency.
    """

    def __init__(self, pool: PostgresConnectionPool):
        """
        Initialize runner with connection pool.

        Args:
            pool: PostgreSQL connection pool
        """
        self.pool = pool

    async def run_sql(self, args, _context) -> pd.DataFrame:
        """
        Execute SQL query and return results as DataFrame.

        This method implements the Vanna SqlRunner interface.
        Captures SQL BEFORE execution for streaming display.

        Args:
            args: RunSqlToolArgs with .sql attribute
            _context: ToolContext (unused but required by interface)

        Returns:
            pandas DataFrame with query results

        Raises:
            psycopg2.Error: If query execution fails
        """
        sql = args.sql if hasattr(args, 'sql') else str(args)

        with self.pool.get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(sql)

            # Check if query returns data (SELECT, WITH)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return pd.DataFrame(rows, columns=columns)
            else:
                # DML statement (INSERT, UPDATE, DELETE)
                conn.commit()
                return pd.DataFrame([{"rows_affected": cursor.rowcount}])


# =============================================================================
# VANNA 0.x CLASSES (with ChromaDB for DDL storage)
# =============================================================================


class OpenAIVanna(ChromaDB_VectorStore, OpenAI_Chat):
    """Vanna 0.x class using OpenAI + ChromaDB for DDL storage."""

    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, config=config)

    def system_message(self, message: str) -> dict:
        """Override system message method to append custom prompt to Vanna's DDL context."""
        if hasattr(self, '_custom_system_prompt'):
            # Append custom prompt to Vanna's generated context (which includes DDL from ChromaDB)
            combined = f"{message}\n\n{self._custom_system_prompt}"
            return {"role": "system", "content": combined}
        return {"role": "system", "content": message}


class AnthropicVanna(ChromaDB_VectorStore, Anthropic_Chat):
    """Vanna 0.x class using Anthropic + ChromaDB for DDL storage."""

    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Anthropic_Chat.__init__(self, config=config)


class AzureOpenAIVanna(ChromaDB_VectorStore, OpenAI_Chat):
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
        """Override system message method to append custom prompt to Vanna's DDL context."""
        if hasattr(self, '_custom_system_prompt'):
            # Append custom prompt to Vanna's generated context (which includes DDL from ChromaDB)
            combined = f"{message}\n\n{self._custom_system_prompt}"
            return {"role": "system", "content": combined}
        return {"role": "system", "content": message}


class OllamaVanna(ChromaDB_VectorStore):
    """
    Vanna 0.x class using Ollama + ChromaDB for DDL storage.

    Uses Ollama Python SDK for local LLM inference.
    """

    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        self.config = config or {}
        self.model = self.config.get('model', 'llama3.1:8b')
        self.temperature = self.config.get('temperature', 0.7)

        # Import Ollama client
        import ollama
        self.client = ollama.Client(host=settings.ollama_base_url)

    def submit_prompt(self, prompt, **kwargs):
        """Submit prompt to Ollama for completion."""
        if prompt is None or len(prompt) == 0:
            raise Exception("Prompt is None or empty")

        # Convert prompt to Ollama format
        messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]

        # Get model from kwargs or use default
        model = kwargs.get('model', self.model)

        # Call Ollama
        response = self.client.chat(
            model=model,
            messages=messages,
            options={
                'temperature': self.temperature,
            }
        )

        return response['message']['content']

    def generate_question(self, sql: str, **kwargs) -> str:
        """Generate a question from SQL (required by Vanna base class)."""
        prompt = f"Generate a natural language question that this SQL query answers:\n\n{sql}"
        return self.submit_prompt([{"role": "user", "content": prompt}], **kwargs)


# Global Vanna instance (cached)
_vanna_instance = None
_vanna_trained = False


def _get_vanna_instance():
    """
    Get or create the Vanna 0.x instance with ChromaDB.

    Returns:
        Configured Vanna instance with DDL stored in ChromaDB
    """
    global _vanna_instance

    if _vanna_instance is not None:
        return _vanna_instance

    provider = settings.llm_provider
    model = settings.sql_model
    chroma_path = f"{settings.vanna_chromadb_path}/vanna_ddl"

    logger.info(f"Creating Vanna 0.x instance with ChromaDB at {chroma_path}")

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")

        _vanna_instance = OpenAIVanna(config={
            'api_key': settings.openai_api_key,
            'model': model,
            'path': chroma_path,
        })
        logger.info(f"Created OpenAI Vanna with model: {model}")

    elif provider == "azure_openai":
        if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
            raise ValueError("Azure OpenAI endpoint and API key not configured")

        _vanna_instance = AzureOpenAIVanna(config={
            'model': model,  # Use sql_model from settings
            'path': chroma_path,
        })
        logger.info(f"Created Azure OpenAI Vanna with model: {model}")

    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key not configured")

        _vanna_instance = AnthropicVanna(config={
            'api_key': settings.anthropic_api_key,
            'model': model,
            'path': chroma_path,
        })
        logger.info(f"Created Anthropic Vanna with model: {model}")

    elif provider == "ollama":
        _vanna_instance = OllamaVanna(config={
            'model': model,
            'path': chroma_path,
            'temperature': 0.1,  # Lower temperature for SQL generation
        })
        logger.info(f"Created Ollama Vanna with model: {model} at {settings.ollama_base_url}")

    else:
        raise ValueError(f"Unsupported provider for Vanna 0.x: {provider}")

    # Connect to PostgreSQL
    db_url = str(settings.database_url)
    import re
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
    if match:
        user, password, host, port, dbname = match.groups()
        _vanna_instance.connect_to_postgres(
            host=host,
            dbname=dbname,
            user=user,
            password=password,
            port=int(port)
        )
        logger.info(f"Connected Vanna to PostgreSQL: {host}:{port}/{dbname}")

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
        ddl_count = len(existing_data[existing_data['training_data_type'] == 'ddl']) if not existing_data.empty else 0

        if ddl_count > 0 and not force_retrain:
            logger.info(f"Vanna already has {ddl_count} DDL statements in ChromaDB, skipping training")
            _vanna_trained = True
            return

        logger.info(f"Training Vanna with DDL (existing: {ddl_count}, force: {force_retrain})")

        # Get DDL from database
        from src.database.ddl_extractor import get_all_ddl_statements

        ddl_statements = get_all_ddl_statements(include_samples=True)
        logger.info(f"Training Vanna with {len(ddl_statements)} DDL statements")

        for i, ddl in enumerate(ddl_statements):
            try:
                vn.train(ddl=ddl)
                logger.debug(f"Trained DDL {i+1}/{len(ddl_statements)}")
            except Exception as e:
                logger.warning(f"Failed to train DDL {i+1}: {e}")

        # Add business documentation
        from src.core.prompts import BUSINESS_CONTEXT_DOCUMENTATION
        try:
            vn.train(documentation=BUSINESS_CONTEXT_DOCUMENTATION)
            logger.info("Trained with business documentation")
        except Exception as e:
            logger.warning(f"Failed to train documentation: {e}")

        _vanna_trained = True
        logger.info("Vanna training complete - DDL stored in ChromaDB")

    except Exception as e:
        logger.error(f"Failed to train Vanna: {e}")
        raise


# =============================================================================
# AGENT CREATION (using LegacyVannaAdapter)
# =============================================================================


class SnapAnalystUserResolver(UserResolver):
    """User resolver for Vanna 2.x agent."""

    async def resolve_user(self, request_context: RequestContext) -> User:
        user_id = request_context.get_header("x-user-id") or "guest"
        return User(
            id=user_id,
            username=user_id,
            email=f"{user_id}@snapanalyst.local",
            group_memberships=["user"],
            metadata={"source": "snapanalyst"},
        )


def _create_llm_service(provider: str, model: str):
    """Create LLM service for Vanna 2.x Agent."""
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        return OpenAILlmService(model=model, api_key=settings.openai_api_key)

    elif provider == "azure_openai":
        # For Azure OpenAI, we don't use the Agent (LegacyVannaAdapter handles it)
        # Just return a basic OpenAI service for compatibility
        # The actual Azure calls are made through AzureOpenAIVanna class
        if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
            raise ValueError("Azure OpenAI endpoint and API key not configured")

        # Return OpenAI service with model from settings
        # This is used for Agent creation but actual SQL gen uses AzureOpenAIVanna
        return OpenAILlmService(
            model=model,  # Use the model parameter passed in
            api_key=settings.azure_openai_api_key
        )

    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key not configured")
        return AnthropicLlmService(model=model, api_key=settings.anthropic_api_key)

    elif provider == "ollama":
        # For Ollama, we don't use the Agent (LegacyVannaAdapter handles it)
        # Return a dummy OpenAI service for compatibility
        # The actual Ollama calls are made through OllamaVanna class
        return OpenAILlmService(model=model, api_key="dummy-key-not-used")

    else:
        raise ValueError(f"Unsupported provider: {provider}")


def create_agent(dataset: str = "snap_qc", max_memory_items: int = 10000):
    """
    Create a Vanna 2.x Agent using LegacyVannaAdapter.

    This wraps a Vanna 0.x instance (with ChromaDB DDL storage) for use
    with the Vanna 2.x Agent architecture.

    The LegacyVannaAdapter:
    - Implements ToolRegistry (exposes vn.run_sql() as run_sql tool)
    - Implements AgentMemory (exposes training data for RAG retrieval)
    - Maintains existing ChromaDB training data (DDL, docs, examples)

    Args:
        dataset: Dataset name (for logging)
        max_memory_items: Unused (kept for API compatibility)

    Returns:
        Vanna 2.x Agent with LegacyVannaAdapter
    """
    # 1. Get or create Vanna 0.x instance with ChromaDB
    vn = _get_vanna_instance()

    # 2. Train with DDL from database (only runs once, persisted in ChromaDB)
    train_vanna_with_ddl()

    # 3. Create LegacyVannaAdapter (implements ToolRegistry + AgentMemory)
    legacy_adapter = LegacyVannaAdapter(vn)

    # 4. Create LLM service for the 2.x Agent
    llm_service = _create_llm_service(settings.llm_provider, settings.sql_model)

    # 5. Configure agent behavior
    config = AgentConfig(
        max_tool_iterations=10,
        stream_responses=False,
        auto_save_conversations=False,
        temperature=settings.llm_temperature,
        max_tokens=4000,
    )

    # 6. Create Vanna 2.x Agent with the legacy adapter
    agent = Agent(
        llm_service=llm_service,
        tool_registry=legacy_adapter,      # LegacyVannaAdapter is a ToolRegistry
        agent_memory=legacy_adapter,       # LegacyVannaAdapter is also AgentMemory
        user_resolver=SnapAnalystUserResolver(),
        config=config,
    )

    logger.info(f"Created Vanna 2.x Agent for dataset '{dataset}'")
    logger.info(f"  Provider: {settings.llm_provider.upper()}")
    logger.info(f"  Model: {settings.sql_model}")
    logger.info("  DDL Storage: ChromaDB (persistent, RAG retrieval)")
    logger.info("  Adapter: LegacyVannaAdapter (bridges 0.x DDL to 2.x Agent)")

    return agent
