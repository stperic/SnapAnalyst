"""
LLM Service for Vanna 2.x

Handles SQL generation (via Vanna agents) and text generation (direct LLM API).
Multi-provider: OpenAI, Anthropic, Ollama.
"""

from __future__ import annotations

import asyncio
import os
import threading

# Configure ONNX Runtime before any Vanna/ChromaDB imports
# CRITICAL: Explicitly set thread count to prevent CPU affinity errors in LXC containers
# When thread count is explicit, ONNX Runtime skips automatic CPU affinity (which fails in LXC)
# See: https://github.com/chroma-core/chroma/issues/1420
if not os.environ.get('OMP_NUM_THREADS') or os.environ.get('OMP_NUM_THREADS') == '0':
    os.environ['OMP_NUM_THREADS'] = '4'

from anthropic import Anthropic
from openai import OpenAI
from vanna import Agent

from src.core.config import settings
from src.core.logging import get_llm_logger, get_logger

logger = get_logger(__name__)
llm_logger = get_llm_logger()

# Agent cache (per dataset)
_agents: dict[str, Agent] = {}
_agents_lock = threading.Lock()


def _get_agent(dataset: str = "snap_qc") -> Agent:
    """Get or create agent for dataset."""
    if dataset not in _agents:
        with _agents_lock:
            if dataset not in _agents:
                from .llm_providers import create_agent
                _agents[dataset] = create_agent(dataset)
    return _agents[dataset]


def _generate_sql_sync(question: str, dataset: str | None = None, user_id: str | None = None) -> tuple[str, str]:
    """
    Generate SQL using Vanna 0.x with DDL from ChromaDB.

    This function:
    1. Retrieves the Vanna 0.x instance (with ChromaDB DDL storage)
    2. Gets user's custom SQL prompt (or default)
    3. Calls vn.generate_sql() which performs RAG retrieval of relevant DDL
    4. Returns the generated SQL query

    Args:
        question: Natural language question
        dataset: Dataset name (currently unused, for future multi-dataset support)
        user_id: User identifier for custom prompt lookup

    Returns:
        Tuple of (sql_query, explanation)

    Raises:
        ValueError: If question is empty or SQL generation fails
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    from src.core.prompts import VANNA_SQL_SYSTEM_PROMPT
    from src.database.prompt_manager import get_user_prompt
    from src.services.llm_providers import _get_vanna_instance

    vn = _get_vanna_instance()

    # Get user's custom prompt or default
    if user_id:
        try:
            system_prompt = get_user_prompt(user_id, 'sql')
            logger.info(f"Using custom SQL prompt for user {user_id}: {system_prompt[:100]}...")
        except Exception as e:
            logger.warning(f"Failed to get custom prompt for {user_id}: {e}, using default")
            system_prompt = VANNA_SQL_SYSTEM_PROMPT
    else:
        logger.info("No user_id provided, using default SQL prompt")
        system_prompt = VANNA_SQL_SYSTEM_PROMPT

    # Set custom prompt as attribute (used by overridden system_message method)
    vn._custom_system_prompt = system_prompt
    logger.debug(f"Set custom system prompt on Vanna instance (length: {len(system_prompt)} chars)")

    sql = vn.generate_sql(question)

    if not sql:
        raise ValueError("Could not generate SQL. Please rephrase your question.")

    logger.info(f"Generated SQL: {sql[:100]}...")
    return sql, f"Query for: {question}"


async def _generate_sql_async(question: str, dataset: str | None = None, user_id: str | None = None) -> tuple[str, str]:
    """
    Async wrapper for SQL generation.

    Runs the synchronous vn.generate_sql() in a thread pool to avoid blocking
    the event loop during LLM API calls.
    """
    return await asyncio.to_thread(_generate_sql_sync, question, dataset, user_id)


def _generate_text(prompt: str, max_tokens: int = 500) -> str:
    """Generate text using direct LLM API."""
    provider = settings.llm_provider

    try:
        if provider == "openai":
            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.kb_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()

        elif provider == "azure_openai":
            # Use OpenAI-compatible endpoint with base_url
            client = OpenAI(
                base_url=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
            )
            response = client.chat.completions.create(
                model=settings.kb_model,  # Use kb_model for text generation
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()

        elif provider == "anthropic":
            client = Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model=settings.kb_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.content[0].text.strip()

        elif provider == "ollama":
            import ollama
            client = ollama.Client(host=settings.ollama_base_url)
            response = client.chat(
                model=settings.kb_model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    'temperature': 0.3,
                    'num_predict': max_tokens,
                }
            )
            return response['message']['content'].strip()

        else:
            return "Text generation not available for this provider."

    except Exception as e:
        logger.error(f"Text generation failed: {e}")
        # Return the full raw error from LLM API (quota, billing, model, etc.)
        return f"❌ **LLM Error**: {str(e)}"


class LLMService:
    """Main LLM service - SQL and text generation."""

    def __init__(self):
        self._initialized = False
        logger.info(f"LLM Service: {settings.llm_provider}/{settings.sql_model}")

    def initialize(self, force_retrain: bool = False) -> None:
        """
        Initialize service (pre-load default agent).

        Args:
            force_retrain: If True, reinitialize even if already initialized
        """
        if not self._initialized or force_retrain:
            if force_retrain:
                # Clear agents cache to force reload
                global _agents
                _agents.clear()
                logger.info("Force retraining - clearing agent cache")

            _get_agent("snap_qc")  # Pre-load agent
            # Note: Agent memory seeding happens in data-loader (Phase 2)
            # See scripts/docker_init_data.py train_ai_model()
            self._initialized = True
            logger.info("LLM Service initialized")

    def generate_sql(self, question: str, dataset: str | None = None, user_id: str | None = None) -> tuple[str, str]:
        """Generate SQL query from natural language question."""
        return _generate_sql_sync(question, dataset, user_id)

    async def generate_sql_async(self, question: str, dataset: str | None = None, user_id: str | None = None) -> tuple[str, str]:
        """Generate SQL query from natural language question (async)."""
        return await _generate_sql_async(question, dataset, user_id)

    def generate_text(self, prompt: str, max_tokens: int = 500) -> str:
        """Generate text."""
        return _generate_text(prompt, max_tokens)

    def get_provider_info(self) -> dict:
        """Get service info."""
        return {
            "provider": settings.llm_provider,
            "model": settings.sql_model,
            "vanna_version": "2.0.1",
            "initialized": self._initialized,
            "datasets_loaded": list(_agents.keys())
        }

    def check_health(self) -> dict:
        """Check service health."""
        provider = settings.llm_provider
        model = settings.sql_model

        if provider == "openai" and not settings.openai_api_key:
            return {"provider": "OPENAI", "model": model, "healthy": False, "status": "not_configured", "error": "API key not set"}

        if provider == "azure_openai" and (not settings.azure_openai_api_key or not settings.azure_openai_endpoint):
            return {"provider": "AZURE_OPENAI", "model": model, "healthy": False, "status": "not_configured", "error": "Azure endpoint or API key not set"}

        if provider == "anthropic" and not settings.anthropic_api_key:
            return {"provider": "ANTHROPIC", "model": model, "healthy": False, "status": "not_configured", "error": "API key not set"}

        return {"provider": provider.upper(), "model": model, "healthy": True, "status": "configured"}


# Singleton
_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get global service instance."""
    global _service
    if _service is None:
        _service = LLMService()
    return _service


def initialize_llm_service(force_retrain: bool = False) -> None:
    """
    Initialize global service.

    Args:
        force_retrain: If True, reinitialize even if already initialized
    """
    get_llm_service().initialize(force_retrain=force_retrain)
