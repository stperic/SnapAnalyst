"""
LLM Service

Handles SQL generation (via Vanna 0.x with ChromaDB RAG) and text generation (direct LLM API).
Multi-provider: OpenAI, Anthropic, Ollama, Azure OpenAI.
"""

from __future__ import annotations

import asyncio
import os
import threading

# Configure ONNX Runtime before any Vanna/ChromaDB imports
# CRITICAL: Explicitly set thread count to prevent CPU affinity errors in LXC containers
# When thread count is explicit, ONNX Runtime skips automatic CPU affinity (which fails in LXC)
# See: https://github.com/chroma-core/chroma/issues/1420
if not os.environ.get("OMP_NUM_THREADS") or os.environ.get("OMP_NUM_THREADS") == "0":
    os.environ["OMP_NUM_THREADS"] = "4"

from src.core.config import settings
from src.core.logging import get_llm_logger, get_logger

logger = get_logger(__name__)
llm_logger = get_llm_logger()

# Cached LLM API clients (created once per provider, thread-safe)
_client_lock = threading.Lock()
_openai_client = None
_anthropic_client = None
_azure_openai_client = None
_ollama_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        with _client_lock:
            if _openai_client is None:
                from openai import OpenAI

                _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def _get_azure_openai_client():
    global _azure_openai_client
    if _azure_openai_client is None:
        with _client_lock:
            if _azure_openai_client is None:
                from openai import OpenAI

                _azure_openai_client = OpenAI(
                    base_url=settings.azure_openai_endpoint,
                    api_key=settings.azure_openai_api_key,
                )
    return _azure_openai_client


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        with _client_lock:
            if _anthropic_client is None:
                from anthropic import Anthropic

                _anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def _get_ollama_client():
    global _ollama_client
    if _ollama_client is None:
        with _client_lock:
            if _ollama_client is None:
                import ollama

                _ollama_client = ollama.Client(host=settings.ollama_base_url)
    return _ollama_client


def _generate_sql_sync(
    question: str, dataset: str | None = None, user_id: str | None = None, llm_params: dict | None = None
) -> tuple[str, str]:
    """
    Generate SQL using Vanna 0.x with DDL from ChromaDB.

    This function:
    1. Retrieves the Vanna 0.x instance (with ChromaDB DDL storage)
    2. Gets user's custom SQL prompt (or default)
    3. Stores prompt in thread-local storage (THREAD-SAFE for multi-user)
    4. Calls vn.generate_sql() which performs RAG retrieval of relevant DDL
    5. Returns the generated SQL query

    Args:
        question: Natural language question
        dataset: Dataset name (currently unused, for future multi-dataset support)
        user_id: User identifier for custom prompt lookup
        llm_params: Optional per-request LLM parameters dict

    Returns:
        Tuple of (sql_query, explanation)

    Raises:
        ValueError: If question is empty or SQL generation fails
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    from src.database.prompt_manager import get_user_prompt, has_custom_prompt
    from src.services.llm_providers import _get_vanna_instance, set_request_custom_prompt, set_request_llm_params

    vn = _get_vanna_instance()

    # Only set thread-local prompt when user has a CUSTOM prompt.
    # The default system prompt is already in Vanna's initial_prompt config
    # (positioned BEFORE DDL/docs for maximum LLM attention).
    custom_prompt = None
    if user_id:
        try:
            if has_custom_prompt(user_id, "sql"):
                custom_prompt = get_user_prompt(user_id, "sql")
                logger.info(f"Using custom SQL prompt for user {user_id}: {custom_prompt[:100]}...")
        except Exception as e:
            logger.warning(f"Failed to get custom prompt for {user_id}: {e}")

    set_request_custom_prompt(custom_prompt)
    set_request_llm_params(llm_params)

    try:
        # Log prompt metadata for observability
        try:
            training_data = vn.get_training_data()
            if not training_data.empty:
                ddl_count = len(training_data[training_data["training_data_type"] == "ddl"])
                doc_count = len(training_data[training_data["training_data_type"] == "documentation"])
                sql_count = len(training_data[training_data["training_data_type"] == "sql"])
                logger.debug(
                    f"Vanna prompt context: DDL={ddl_count}, docs={doc_count}, examples={sql_count}, "
                    f"question='{question[:60]}...'"
                )
        except Exception:
            pass  # Don't let logging failures break SQL generation

        sql = vn.generate_sql(question)

        if not sql:
            raise ValueError("Could not generate SQL. Please rephrase your question.")

        logger.debug(f"Generated SQL: {sql[:100]}...")
        return sql, f"Query for: {question}"
    finally:
        # Clean up thread-local storage after request
        set_request_custom_prompt(None)
        set_request_llm_params(None)


async def _generate_sql_async(
    question: str, dataset: str | None = None, user_id: str | None = None, llm_params: dict | None = None
) -> tuple[str, str]:
    """
    Async wrapper for SQL generation.

    Runs the synchronous vn.generate_sql() in a thread pool to avoid blocking
    the event loop during LLM API calls.
    """
    return await asyncio.to_thread(_generate_sql_sync, question, dataset, user_id, llm_params)


def _build_messages(prompt: str, system_prompt: str | None = None) -> list[dict]:
    """Build message list with optional system role."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


def _generate_text(
    prompt: str, max_tokens: int = 500, llm_params: dict | None = None, system_prompt: str | None = None
) -> str:
    """
    Generate text using direct LLM API.

    Args:
        prompt: The user prompt to send
        max_tokens: Default max tokens
        llm_params: Optional per-request LLM params dict with model, temperature, max_tokens, top_p
        system_prompt: Optional system message (sent as system role for better LLM attention)
    """
    provider = settings.llm_provider

    # Apply per-request overrides
    effective_model = llm_params.get("model") if llm_params and llm_params.get("model") else settings.kb_model
    effective_temperature = (
        llm_params.get("temperature")
        if llm_params and llm_params.get("temperature") is not None
        else settings.effective_kb_temperature
    )
    effective_max_tokens = (
        llm_params.get("max_tokens") if llm_params and llm_params.get("max_tokens") is not None else max_tokens
    )
    effective_top_p = llm_params.get("top_p") if llm_params and llm_params.get("top_p") is not None else None

    messages = _build_messages(prompt, system_prompt)

    try:
        if provider in ("openai", "azure_openai"):
            client = _get_azure_openai_client() if provider == "azure_openai" else _get_openai_client()
            kwargs = {
                "model": effective_model,
                "max_tokens": effective_max_tokens,
                "messages": messages,
            }
            if effective_temperature is not None:
                kwargs["temperature"] = effective_temperature
            if effective_top_p is not None:
                kwargs["top_p"] = effective_top_p
            response = client.chat.completions.create(**kwargs)
            if not response.choices:
                return "No response generated."
            return response.choices[0].message.content.strip()

        elif provider == "anthropic":
            client = _get_anthropic_client()
            # Anthropic uses a separate 'system' param, not in messages
            api_kwargs = {
                "model": effective_model,
                "max_tokens": effective_max_tokens,
                "messages": [m for m in messages if m["role"] != "system"],
            }
            if effective_temperature is not None:
                api_kwargs["temperature"] = effective_temperature
            if system_prompt:
                api_kwargs["system"] = system_prompt
            if effective_top_p is not None:
                api_kwargs["top_p"] = effective_top_p
            response = client.messages.create(**api_kwargs)
            if not response.content:
                return "No response generated."
            return response.content[0].text.strip()

        elif provider == "ollama":
            client = _get_ollama_client()
            options = {
                "num_predict": effective_max_tokens,
            }
            if effective_temperature is not None:
                options["temperature"] = effective_temperature
            if effective_top_p is not None:
                options["top_p"] = effective_top_p
            response = client.chat(
                model=effective_model,
                messages=messages,
                options=options,
            )
            if not response.get("message") or not response["message"].get("content"):
                return "No response generated."
            return response["message"]["content"].strip()

        else:
            return "Text generation not available for this provider."

    except Exception as e:
        logger.error(f"Text generation failed: {e}")
        return f"**LLM Error**: {str(e)}"


class LLMService:
    """Main LLM service - SQL and text generation."""

    def __init__(self):
        self._initialized = False

    def initialize(self, force_retrain: bool = False) -> None:
        """
        Initialize service (create Vanna instance and train with DDL).

        Args:
            force_retrain: If True, reinitialize even if already initialized
        """
        if not self._initialized or force_retrain:
            if force_retrain:
                import src.services.llm_providers as providers

                providers._vanna_instance = None
                providers._vanna_trained = False
                logger.info("Force retraining - resetting Vanna instance")

            from .llm_providers import initialize_vanna

            initialize_vanna()
            self._initialized = True

    def generate_sql(
        self, question: str, dataset: str | None = None, user_id: str | None = None, llm_params: dict | None = None
    ) -> tuple[str, str]:
        """Generate SQL query from natural language question."""
        return _generate_sql_sync(question, dataset, user_id, llm_params)

    async def generate_sql_async(
        self, question: str, dataset: str | None = None, user_id: str | None = None, llm_params: dict | None = None
    ) -> tuple[str, str]:
        """Generate SQL query from natural language question (async)."""
        return await _generate_sql_async(question, dataset, user_id, llm_params)

    def generate_text(
        self, prompt: str, max_tokens: int = 500, llm_params: dict | None = None, system_prompt: str | None = None
    ) -> str:
        """Generate text with optional system prompt."""
        return _generate_text(prompt, max_tokens, llm_params, system_prompt)

    def get_provider_info(self) -> dict:
        """Get service info."""
        return {
            "provider": settings.llm_provider,
            "model": settings.sql_model,
            "vanna_version": "0.x",
            "initialized": self._initialized,
        }

    def check_health(self) -> dict:
        """Check service health."""
        provider = settings.llm_provider
        model = settings.sql_model

        if provider == "openai" and not settings.openai_api_key:
            return {
                "provider": "OPENAI",
                "model": model,
                "healthy": False,
                "status": "not_configured",
                "error": "API key not set",
            }

        if provider == "azure_openai" and (not settings.azure_openai_api_key or not settings.azure_openai_endpoint):
            return {
                "provider": "AZURE_OPENAI",
                "model": model,
                "healthy": False,
                "status": "not_configured",
                "error": "Azure endpoint or API key not set",
            }

        if provider == "anthropic" and not settings.anthropic_api_key:
            return {
                "provider": "ANTHROPIC",
                "model": model,
                "healthy": False,
                "status": "not_configured",
                "error": "API key not set",
            }

        return {"provider": provider.upper(), "model": model, "healthy": True, "status": "configured"}


# Singleton (thread-safe)
_service: LLMService | None = None
_service_lock = threading.Lock()


def get_llm_service() -> LLMService:
    """Get global service instance (thread-safe)."""
    global _service
    if _service is None:
        with _service_lock:
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
