"""
SnapAnalyst Chatbot API Router

Natural language query interface for SQL generation and execution.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_serializer
from sse_starlette.sse import EventSourceResponse

from src.api.routers.query import SQLQueryRequest, execute_sql_query
from src.core.logging import get_logger
from src.services.llm_service import get_llm_service, initialize_llm_service

logger = get_logger(__name__)


router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class LLMParams(BaseModel):
    """Per-request LLM parameters (from session settings)."""

    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=16000)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    context_window: int | None = None


class ChatQueryRequest(BaseModel):
    """Request model for natural language query"""

    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language question about the data",
        examples=["How many records are in the database?"],
    )
    execute: bool = Field(default=True, description="If True, execute the generated SQL and return results")
    explain: bool = Field(default=True, description="If True, include explanation of the generated SQL")
    user_id: str | None = Field(default=None, description="User identifier for custom prompt lookup")
    llm_params: LLMParams | None = Field(default=None, description="Optional per-request LLM parameters")


class TextGenerationRequest(BaseModel):
    """Request model for general text generation"""

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=500000,  # Large context window support
        description="Text prompt for the LLM",
    )
    max_tokens: int = Field(default=1000, ge=10, le=8000, description="Maximum tokens to generate")


class TextGenerationResponse(BaseModel):
    """Response model for text generation"""

    text: str = Field(..., description="Generated text")
    tokens_used: int | None = Field(None, description="Approximate tokens used")


class KBInsightRequest(BaseModel):
    """Request model for knowledge base insight"""

    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Question to answer using knowledge base and optional data context",
    )
    data_context: str | None = Field(None, description="Optional data context from a previous query (JSON or summary)")
    previous_question: str | None = Field(None, description="The original data question (for context)")
    previous_sql: str | None = Field(None, description="SQL query that was executed (for context)")


class KBInsightResponse(BaseModel):
    """Response model for knowledge base insight"""

    insight: str = Field(..., description="Generated insight text")
    sources_used: list[str] = Field(default_factory=list, description="Context sources used")
    provider: str = Field(..., description="LLM provider used")


class ChatQueryResponse(BaseModel):
    """Response model for natural language query"""

    question: str = Field(..., description="Original question")
    sql: str = Field(..., description="Generated SQL query")
    explanation: str | None = Field(None, description="Explanation of the SQL query")
    executed: bool = Field(..., description="Whether the query was executed")
    results: list[dict] | None = Field(None, description="Query results (if executed)")
    row_count: int | None = Field(None, description="Number of rows returned")
    followup_questions: list[str] | None = Field(None, description="Suggested followup questions")
    provider: str = Field(..., description="LLM provider used (openai/anthropic/ollama)")
    model: str = Field(..., description="LLM model used")

    @field_serializer("results")
    def serialize_results(self, results: list[dict] | None, _info) -> list[dict] | None:
        """Convert Decimal values to float in results for JSON serialization"""
        if results is None:
            return None
        return [{k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()} for row in results]


class ProviderInfoResponse(BaseModel):
    """Response model for LLM provider information"""

    provider: str = Field(..., description="Current LLM provider (openai, anthropic, azure_openai, ollama)")
    model: str = Field(..., description="Model name")
    vanna_version: str = Field(..., description="Vanna version")
    initialized: bool = Field(..., description="Whether service is initialized")


class LLMHealthResponse(BaseModel):
    """Response model for LLM health check"""

    healthy: bool = Field(..., description="Whether LLM service is healthy and available")
    provider: str = Field(..., description="LLM provider name (OPENAI, ANTHROPIC, OLLAMA)")
    model: str = Field(..., description="Configured model name")
    status: str = Field(..., description="Status: connected, not_configured, not_reachable, model_not_found, etc.")
    error: str | None = Field(None, description="Error message if not healthy")


class TrainingStatusResponse(BaseModel):
    """Response model for training status"""

    status: str = Field(..., description="Training status")
    message: str = Field(..., description="Status message")


# ============================================================================
# Error Classification
# ============================================================================


def _classify_llm_error(exc: Exception) -> str:
    """Turn raw LLM/provider exceptions into user-friendly error messages."""
    from src.core.config import settings

    err = str(exc).lower()
    exc_type = type(exc).__name__

    # Authentication / API key errors
    if (
        exc_type in ("AuthenticationError", "PermissionDeniedError")
        or "authentication" in err
        or "invalid api key" in err
        or "incorrect api key" in err
        or "401" in err
    ):
        return (
            f"LLM authentication failed ({settings.llm_provider.upper()}). "
            f"Check that your API key is valid in the .env file. "
            f"(Key variable: {_api_key_var_for_provider(settings.llm_provider)})"
        )

    # Connection / network errors
    if (
        exc_type in ("APIConnectionError", "ConnectError", "ConnectionError")
        or "connection error" in err
        or "connect" in err
        and ("refused" in err or "timeout" in err or "failed" in err)
    ):
        return (
            f"Cannot connect to {settings.llm_provider.upper()} API. "
            f"Check your network connection and API key. "
            f"(Provider: {settings.llm_provider}, Model: {settings.sql_model})"
        )

    # Rate limiting
    if exc_type == "RateLimitError" or "rate limit" in err or "429" in err or "quota" in err:
        return (
            f"LLM rate limit exceeded ({settings.llm_provider.upper()}). "
            f"Wait a moment and try again, or check your billing/quota."
        )

    # Model not found
    if "model" in err and ("not found" in err or "does not exist" in err or "404" in err):
        return (
            f"Model '{settings.sql_model}' not found on {settings.llm_provider.upper()}. "
            f"Check LLM_SQL_MODEL in your .env file."
        )

    # Timeout
    if "timeout" in err or exc_type == "Timeout":
        return (
            f"LLM request timed out ({settings.llm_provider.upper()}). "
            f"The model may be overloaded — try again in a moment."
        )

    # Fallback: include the original error but with context
    return f"LLM error ({settings.llm_provider.upper()}, {settings.sql_model}): {exc}"


def _api_key_var_for_provider(provider: str) -> str:
    """Return the environment variable name for the given provider's API key."""
    return {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "azure_openai": "AZURE_OPENAI_API_KEY",
        "ollama": "OLLAMA_BASE_URL",
    }.get(provider, f"{provider.upper()}_API_KEY")


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/data",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Data request - Convert natural language to SQL",
    description="Convert natural language question to SQL and optionally execute it",
    response_description="Generated SQL query and optional results",
)
async def chat_data(request: ChatQueryRequest) -> ChatQueryResponse:
    """
    Convert natural language question to SQL query using LLM.

    This endpoint uses the configured LLM (OpenAI/Anthropic/Ollama) to:
    1. Convert your question to a SQL query
    2. Optionally execute the query
    3. Provide an explanation of the SQL
    4. Suggest followup questions

    **Examples:**
    - "How many households received SNAP in 2023?"
    - "What's the average benefit amount by state?"
    - "Show me households with children and income over $2000"
    - "What are the most common error types?"

    **Configuration:**
    Set these environment variables:
    - `LLM_PROVIDER`: openai, anthropic, or ollama
    - `OPENAI_API_KEY`: If using OpenAI
    - `ANTHROPIC_API_KEY`: If using Anthropic
    - `OLLAMA_BASE_URL`: If using Ollama (default: http://localhost:11434)
    """
    try:
        # Get LLM service
        llm_service = get_llm_service()

        # Ensure service is initialized
        if not llm_service._initialized:
            logger.info("LLM service not initialized, initializing now...")
            initialize_llm_service()

        # Generate SQL from question (async to avoid blocking the event loop)
        # This will raise ValueError if LLM returns non-SQL response
        llm_params_dict = request.llm_params.model_dump(exclude_none=True) if request.llm_params else None
        sql, explanation = await llm_service.generate_sql_async(
            request.question, user_id=request.user_id, llm_params=llm_params_dict
        )

        if not sql:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not generate SQL from the question. Please rephrase.",
            )

        # At this point, sql is validated to be actual SQL
        logger.debug(f"SQL before filter: {sql}")

        # Apply global filter to generated SQL
        from src.core.filter_manager import get_filter_manager

        filter_manager = get_filter_manager()
        sql_after_filter = filter_manager.apply_to_sql(sql)

        logger.debug(f"SQL after filter: {sql_after_filter}")
        sql = sql_after_filter

        # Get provider info
        provider_info = llm_service.get_provider_info()

        # Execute query if requested
        results = None
        row_count = None
        if request.execute:
            try:
                sql_request = SQLQueryRequest(sql=sql)
                query_response = await execute_sql_query(sql_request)
                # Pass data directly - Pydantic field_serializer will handle Decimal conversion
                results = query_response.data
                row_count = query_response.row_count
            except Exception as e:
                logger.error(f"Failed to execute generated SQL: {e}")
                # Don't fail the whole request, just note execution failed
                results = None
                row_count = 0

        # Followup questions feature not implemented
        followup_questions = None

        return ChatQueryResponse(
            question=request.question,
            sql=sql,
            explanation=explanation if request.explain else None,
            executed=request.execute,
            results=results,
            row_count=row_count,
            followup_questions=followup_questions,
            provider=provider_info["provider"],
            model=provider_info["model"],
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Chat query failed: {e}")
        detail = _classify_llm_error(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


@router.get(
    "/examples",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="Get example questions",
    description="Returns a list of example questions you can ask",
)
async def get_example_questions() -> list[str]:
    """
    Get example questions to help users understand what they can ask.

    Returns a curated list of example questions from the training data.
    """
    # Try loading from active dataset first
    try:
        from datasets import get_active_dataset

        ds = get_active_dataset()
        if ds:
            dataset_examples = ds.get_example_questions()
            if dataset_examples:
                return dataset_examples
    except Exception:
        pass

    # Fallback generic examples
    return [
        "How many records are in the database?",
        "Show me the top 10 results by count",
        "What are the unique values in the main table?",
    ]


@router.post(
    "/insights",
    response_model=KBInsightResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate insights from knowledge base",
    description="Generate insights using KB ChromaDB with filtering support",
)
async def chat_insights(
    request: KBInsightRequest, user_id: str = Query(None)
) -> KBInsightResponse:
    """
    Generate insights using KB ChromaDB with filtering support.

    Supports: hashtags (#policy), categories (category:name), user scope (@me)
    """
    from src.services.kb_chromadb import query_documents
    from src.utils.kb_filter_parser import format_search_scope, parse_kb_filters

    if user_id is None:
        from datasets import get_active_dataset

        ds = get_active_dataset()
        user_id = ds.get_anonymous_email() if ds else "anonymous@app.com"

    try:
        llm_service = get_llm_service()
        if not llm_service._initialized:
            initialize_llm_service()
            llm_service = get_llm_service()

        # Parse filters
        filters = parse_kb_filters(request.question, user_id)

        logger.info(f"KB insight: path={filters['chromadb_path']}, question={filters['question'][:60]}")

        sources_used = []
        chromadb_context = ""

        # Query based on path
        from src.services.kb_chromadb import query_all, query_dataset

        try:
            if filters["chromadb_path"] == "kb":
                # Query KB only
                results = query_documents(
                    question=filters["question"],
                    user_id=user_id,
                    tags=filters["tags"],
                    category=filters["category"],
                    user_scope=filters["user_scope"],
                    n_results=5,
                )
            elif filters["chromadb_path"] == "all":
                # Query everything
                results = query_all(question=filters["question"], user_id=user_id, n_results=10)
            else:
                # Query specific dataset
                results = query_dataset(
                    question=filters["question"],
                    dataset_path=filters["chromadb_path"],
                    collections=filters["collections"],
                    n_results=5,
                )

            if results:
                # Send full documents to LLM for maximum context
                context_parts = ["**Sources:**\n"]
                for i, result in enumerate(results, 1):
                    source = result["source_display"]
                    context_parts.append(f"{i}. {source}\n   {result['document']}\n")
                    sources_used.append(source)

                chromadb_context = "\n".join(context_parts)
                logger.info(f"Retrieved {len(results)} results")
        except Exception as e:
            logger.warning(f"Could not retrieve context: {e}")

        # Build prompt
        from src.core.prompts import build_kb_insight_prompt

        if request.data_context:
            sources_used.append("Previous query data")

        system_message, user_message = build_kb_insight_prompt(
            question=filters["question"],
            data_context=request.data_context,
            chromadb_context=chromadb_context,
            user_id=user_id,
        )

        # Generate insight (async to avoid blocking the event loop)
        import asyncio

        from src.core.config import settings

        insight_text = await asyncio.to_thread(
            llm_service.generate_text, user_message, settings.llm_kb_max_tokens, system_prompt=system_message
        )

        # Add scope info
        scope_info = format_search_scope(filters)
        response_text = f"{scope_info}\n\n{insight_text}"

        provider_info = llm_service.get_provider_info()

        return KBInsightResponse(
            insight=response_text.strip(), sources_used=sources_used, provider=provider_info["provider"]
        )

    except Exception as e:
        logger.error(f"KB insight error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate insight: {str(e)}"
        )


# ============================================================================
# Streaming Endpoints
# ============================================================================


class StreamChatRequest(BaseModel):
    """Request model for streaming SQL generation"""

    question: str = Field(..., min_length=3, max_length=500, description="Natural language question about the data")
    user_id: str = Field(default="system", description="User ID for context")


class StreamKBRequest(BaseModel):
    """Request model for streaming KB insight"""

    question: str = Field(..., min_length=3, max_length=1000, description="Question to answer using knowledge base")
    user_id: str | None = Field(default=None, description="User ID for filtering")
    data_context: str | None = Field(None, description="Optional data context from a previous query")
    llm_params: LLMParams | None = Field(default=None, description="Optional per-request LLM parameters")


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
    summary="Stream SQL generation",
    description="Stream SQL generation progress via Server-Sent Events",
)
async def chat_stream(request: StreamChatRequest):
    """
    Stream SQL generation progress via SSE.

    Events:
    - progress: Intermediate progress messages
    - sql: Final SQL query
    - error: Error message
    - done: Stream complete
    """

    async def event_generator() -> AsyncGenerator[dict, None]:
        from src.services.llm_providers import set_request_custom_prompt, set_request_llm_params

        try:
            from src.api.routers.query import SQLQueryRequest, execute_sql_query
            from src.core.filter_manager import get_filter_manager
            from src.services.llm_providers import _get_vanna_instance

            # Ensure Vanna is initialized
            llm_service = get_llm_service()
            if not llm_service._initialized:
                logger.info("LLM service not initialized, initializing now...")
                initialize_llm_service()

            filter_manager = get_filter_manager()

            # Generate SQL using Vanna 0.x (with DDL from ChromaDB)
            vn = _get_vanna_instance()

            # Debug log the request
            logger.info(f"Streaming request - user_id: {request.user_id}, question: {request.question[:50]}...")

            # Set custom prompt if user has one (thread-safe via thread-local storage)
            custom_prompt = None
            if request.user_id and request.user_id != "system":
                from src.database.prompt_manager import get_user_prompt, has_custom_prompt

                try:
                    if has_custom_prompt(request.user_id, "sql"):
                        custom_prompt = get_user_prompt(request.user_id, "sql")
                        logger.info(
                            f"Streaming: Using custom SQL prompt for user {request.user_id}: {custom_prompt[:100]}..."
                        )
                except Exception as e:
                    logger.warning(f"Streaming: Failed to get custom prompt for {request.user_id}: {e}")
            set_request_custom_prompt(custom_prompt)
            set_request_llm_params(None)

            sql = vn.generate_sql(request.question)

            if not sql:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Could not generate SQL. Please rephrase your question."}),
                }
                yield {"event": "done", "data": json.dumps({"status": "complete"})}
                return

            # Apply filters
            sql = filter_manager.apply_to_sql(sql)
            yield {"event": "sql", "data": json.dumps({"sql": sql})}

            # Execute SQL
            sql_request = SQLQueryRequest(sql=sql)
            query_response = await execute_sql_query(sql_request)

            if query_response.success:
                results = {
                    "columns": list(query_response.data[0].keys()) if query_response.data else [],
                    "rows": query_response.data,
                }
                yield {"event": "results", "data": json.dumps(results)}
            else:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": query_response.error or "Query execution failed"}),
                }

            yield {"event": "done", "data": json.dumps({"status": "complete"})}

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
            yield {"event": "done", "data": json.dumps({"status": "error"})}
        finally:
            set_request_custom_prompt(None)
            set_request_llm_params(None)

    return EventSourceResponse(event_generator())


@router.post(
    "/insights/stream",
    status_code=status.HTTP_200_OK,
    summary="Stream insight generation",
    description="Stream KB insight generation with Server-Sent Events",
)
async def insights_stream(request: StreamKBRequest):
    """
    Stream KB insight generation via SSE.

    Events:
    - sources: Retrieved sources from ChromaDB
    - text: Streaming text chunks
    - done: Stream complete
    """
    from src.core.config import settings
    from src.core.prompts import build_kb_insight_prompt
    from src.services.kb_chromadb import query_all, query_dataset, query_documents
    from src.services.llm_service import get_llm_service, initialize_llm_service
    from src.utils.kb_filter_parser import parse_kb_filters

    # Resolve anonymous email default
    if request.user_id is None:
        from datasets import get_active_dataset

        ds = get_active_dataset()
        request.user_id = ds.get_anonymous_email() if ds else "anonymous@app.com"

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            # Parse filters
            filters = parse_kb_filters(request.question, request.user_id)

            yield {"event": "progress", "data": json.dumps({"message": "🔍 Searching knowledge base..."})}

            # Query based on path
            results = []
            try:
                if filters["chromadb_path"] == "kb":
                    results = query_documents(
                        question=filters["question"],
                        user_id=request.user_id,
                        tags=filters["tags"],
                        category=filters["category"],
                        user_scope=filters["user_scope"],
                        n_results=5,
                    )
                elif filters["chromadb_path"] == "all":
                    results = query_all(question=filters["question"], user_id=request.user_id, n_results=10)
                else:
                    results = query_dataset(
                        question=filters["question"],
                        dataset_path=filters["chromadb_path"],
                        collections=filters["collections"],
                        n_results=5,
                    )
            except Exception as e:
                logger.warning(f"Could not retrieve context: {e}")

            # Send sources — full documents to LLM, truncated display for UI
            sources_used = []
            chromadb_context = ""
            if results:
                context_parts = ["**Sources:**\n"]
                display_sources = []
                for i, result in enumerate(results, 1):
                    source = result["source_display"]
                    # Full document for LLM context
                    context_parts.append(f"{i}. {source}\n   {result['document']}\n")
                    # Truncated for UI display
                    display_sources.append(source)
                    sources_used.append(source)
                chromadb_context = "\n".join(context_parts)

                yield {"event": "sources", "data": json.dumps({"sources": display_sources, "count": len(results)})}
            elif not request.data_context:
                # KB-only lookup (Knowledge mode): no documents and no thread context — stop early
                yield {
                    "event": "text",
                    "data": json.dumps(
                        {
                            "chunk": "No documents found in the Knowledge Base.\n\nUpload documents via **Settings > Knowledge** and try again."
                        }
                    ),
                }
                yield {"event": "done", "data": json.dumps({"status": "complete", "sources": []})}
                return

            # Build prompt (returns system, user tuple)
            system_message, user_message = build_kb_insight_prompt(
                question=filters["question"],
                data_context=request.data_context,
                chromadb_context=chromadb_context,
                user_id=request.user_id,
            )

            # Stream text generation
            llm_service = get_llm_service()
            if not llm_service._initialized:
                initialize_llm_service()

            # Use streaming text generation with per-request params
            async for chunk in _generate_text_streaming(
                user_message, settings.llm_kb_max_tokens, request.llm_params, system_message
            ):
                yield {"event": "text", "data": json.dumps({"chunk": chunk})}

            yield {"event": "done", "data": json.dumps({"status": "complete", "sources": sources_used})}

        except Exception as e:
            logger.error(f"KB stream error: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


async def _generate_text_streaming(
    prompt: str, max_tokens: int = 500, llm_params: LLMParams | None = None, system_prompt: str | None = None
) -> AsyncGenerator[str, None]:
    """
    Stream text generation using LLM API.

    Supports OpenAI and Anthropic providers with native streaming.
    Falls back to non-streaming for other providers.

    Args:
        prompt: The user prompt to send
        max_tokens: Default max tokens
        llm_params: Optional per-request LLM parameters
        system_prompt: Optional system message (sent as system role)
    """
    import asyncio

    from openai import OpenAIError

    from src.core.config import settings

    provider = settings.llm_provider

    # Apply per-request overrides
    effective_model = llm_params.model if llm_params and llm_params.model else settings.kb_model
    effective_temperature = (
        llm_params.temperature
        if llm_params and llm_params.temperature is not None
        else settings.effective_kb_temperature
    )
    effective_max_tokens = llm_params.max_tokens if llm_params and llm_params.max_tokens is not None else max_tokens
    effective_top_p = llm_params.top_p if llm_params and llm_params.top_p is not None else None

    # Build messages with optional system role
    messages = []
    if system_prompt and provider != "anthropic":
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        if provider in ("openai", "azure_openai"):
            if provider == "azure_openai":
                from src.services.llm_service import _get_azure_openai_client

                client = _get_azure_openai_client()
            else:
                from src.services.llm_service import _get_openai_client

                client = _get_openai_client()

            try:
                stream_kwargs = {
                    "model": effective_model,
                    "max_tokens": effective_max_tokens,
                    "messages": messages,
                    "stream": True,
                }
                if effective_temperature is not None:
                    stream_kwargs["temperature"] = effective_temperature
                if effective_top_p is not None:
                    stream_kwargs["top_p"] = effective_top_p

                stream = client.chat.completions.create(**stream_kwargs)

                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            except OpenAIError as e:
                error_msg = str(e)
                if hasattr(e, "message"):
                    error_msg = e.message
                provider_label = "Azure OpenAI" if provider == "azure_openai" else "OpenAI"
                raise Exception(f"{provider_label} API Error: {error_msg}")

        elif provider == "anthropic":
            from src.services.llm_service import _get_anthropic_client

            client = _get_anthropic_client()

            # Run sync streaming in thread pool to avoid blocking event loop
            def sync_stream():
                chunks = []
                stream_kwargs = {
                    "model": effective_model,
                    "max_tokens": effective_max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if effective_temperature is not None:
                    stream_kwargs["temperature"] = effective_temperature
                if system_prompt:
                    stream_kwargs["system"] = system_prompt
                if effective_top_p is not None:
                    stream_kwargs["top_p"] = effective_top_p
                with client.messages.stream(**stream_kwargs) as stream:
                    for text in stream.text_stream:
                        chunks.append(text)
                return chunks

            loop = asyncio.get_running_loop()
            chunks = await loop.run_in_executor(None, sync_stream)
            for chunk in chunks:
                yield chunk

        else:
            # Fallback to non-streaming for Ollama and other providers
            llm_params_dict = llm_params.model_dump(exclude_none=True) if llm_params else None
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(
                None,
                lambda: get_llm_service().generate_text(
                    prompt, effective_max_tokens, llm_params=llm_params_dict, system_prompt=system_prompt
                ),
            )
            if text:
                yield text

    except Exception as e:
        logger.error(f"Streaming text generation failed: {e}")
        raise
