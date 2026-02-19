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


class ChatQueryRequest(BaseModel):
    """Request model for natural language query"""

    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language question about SNAP QC data",
        examples=["How many households received SNAP benefits in 2023?"]
    )
    execute: bool = Field(
        default=True,
        description="If True, execute the generated SQL and return results"
    )
    explain: bool = Field(
        default=True,
        description="If True, include explanation of the generated SQL"
    )
    user_id: str | None = Field(
        default=None,
        description="User identifier for custom prompt lookup"
    )


class TextGenerationRequest(BaseModel):
    """Request model for general text generation"""

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=50000,  # Increased to support full dataset summaries
        description="Text prompt for the LLM"
    )
    max_tokens: int = Field(
        default=150,
        ge=10,
        le=500,
        description="Maximum tokens to generate"
    )


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
        description="Question to answer using knowledge base and optional data context"
    )
    data_context: str | None = Field(
        None,
        description="Optional data context from a previous query (JSON or summary)"
    )
    previous_question: str | None = Field(
        None,
        description="The original data question (for context)"
    )
    previous_sql: str | None = Field(
        None,
        description="SQL query that was executed (for context)"
    )


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

    @field_serializer('results')
    def serialize_results(self, results: list[dict] | None, _info) -> list[dict] | None:
        """Convert Decimal values to float in results for JSON serialization"""
        if results is None:
            return None
        return [
            {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}
            for row in results
        ]


class ProviderInfoResponse(BaseModel):
    """Response model for LLM provider information"""

    provider: str = Field(..., description="Current LLM provider (openai, anthropic, azure_openai, ollama)")
    model: str = Field(..., description="Model name")
    vanna_version: str = Field(..., description="Vanna version")
    initialized: bool = Field(..., description="Whether service is initialized")
    datasets_loaded: list[str] = Field(default_factory=list, description="Datasets loaded in memory")


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
    if exc_type in ("AuthenticationError", "PermissionDeniedError") or "authentication" in err or "invalid api key" in err or "incorrect api key" in err or "401" in err:
        return (
            f"LLM authentication failed ({settings.llm_provider.upper()}). "
            f"Check that your API key is valid in the .env file. "
            f"(Key variable: {_api_key_var_for_provider(settings.llm_provider)})"
        )

    # Connection / network errors
    if exc_type in ("APIConnectionError", "ConnectError", "ConnectionError") or "connection error" in err or "connect" in err and ("refused" in err or "timeout" in err or "failed" in err):
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

        # Generate SQL from question
        # This will raise ValueError if LLM returns non-SQL response
        sql, explanation = llm_service.generate_sql(request.question, user_id=request.user_id)

        if not sql:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not generate SQL from the question. Please rephrase."
            )

        # At this point, sql is validated to be actual SQL
        # Debug: Log SQL before filter
        logger.info(f"SQL before filter: {sql}")

        # Apply global filter to generated SQL
        from src.core.filter_manager import get_filter_manager
        filter_manager = get_filter_manager()
        sql_after_filter = filter_manager.apply_to_sql(sql)

        # Debug: Log SQL after filter
        logger.info(f"SQL after filter: {sql_after_filter}")
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Chat query failed: {e}")
        detail = _classify_llm_error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


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
    examples = [
        "How many households received SNAP benefits in 2023?",
        "What is the average SNAP benefit amount by state?",
        "Show me the top 10 states by total SNAP recipients",
        "How many households have children under 5?",
        "What percentage of households are elderly?",
        "What are the most common error types in QC reviews?",
        "Show me households with income between $1000 and $2000",
        "How many households received expedited service?",
        "What is the average household size by region?",
        "Show me error rates by state",
        "How many households have disabled members?",
        "What is the distribution of SNAP benefits by household composition?",
        "Show me households with overissuance errors",
        "What percentage of households pass all income tests?",
        "How many households receive the minimum benefit?",
    ]
    return examples


@router.post(
    "/insights",
    response_model=KBInsightResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate insights from knowledge base",
    description="Generate insights using KB ChromaDB with filtering support",
)
async def chat_insights(
    request: KBInsightRequest,
    user_id: str = Query("anonymous@snapanalyst.com")
) -> KBInsightResponse:
    """
    Generate insights using KB ChromaDB with filtering support.

    Supports: hashtags (#policy), categories (category:name), user scope (@me)
    """
    from src.services.kb_chromadb import query_documents
    from src.utils.kb_filter_parser import format_search_scope, parse_kb_filters

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
            if filters['chromadb_path'] == 'kb':
                # Query KB only
                results = query_documents(
                    question=filters['question'],
                    user_id=user_id,
                    tags=filters['tags'],
                    category=filters['category'],
                    user_scope=filters['user_scope'],
                    n_results=5
                )
            elif filters['chromadb_path'] == 'all':
                # Query everything
                results = query_all(
                    question=filters['question'],
                    user_id=user_id,
                    n_results=10
                )
            else:
                # Query specific dataset
                results = query_dataset(
                    question=filters['question'],
                    dataset_path=filters['chromadb_path'],
                    collections=filters['collections'],
                    n_results=5
                )

            if results:
                context_parts = ["**Sources:**\n"]
                for i, result in enumerate(results, 1):
                    doc = result['document'][:300] + "..." if len(result['document']) > 300 else result['document']
                    source = result['source_display']
                    context_parts.append(f"{i}. {source}\n   {doc}\n")
                    sources_used.append(source)

                chromadb_context = "\n".join(context_parts)
                logger.info(f"Retrieved {len(results)} results")
        except Exception as e:
            logger.warning(f"Could not retrieve context: {e}")

        # Build prompt
        from src.core.prompts import build_kb_insight_prompt

        if request.data_context:
            sources_used.append("Previous query data")

        prompt = build_kb_insight_prompt(
            question=filters['question'],
            data_context=request.data_context,
            chromadb_context=chromadb_context,
            user_id=user_id
        )

        # Generate insight
        from src.core.config import settings
        insight_text = llm_service.generate_text(prompt, settings.llm_kb_max_tokens)

        # Add scope info
        scope_info = format_search_scope(filters)
        response_text = f"{scope_info}\n\n{insight_text}"

        provider_info = llm_service.get_provider_info()

        return KBInsightResponse(
            insight=response_text.strip(),
            sources_used=sources_used,
            provider=provider_info["provider"]
        )

    except Exception as e:
        logger.error(f"KB insight error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate insight: {str(e)}"
        )


# ============================================================================
# Streaming Endpoints
# ============================================================================


class StreamChatRequest(BaseModel):
    """Request model for streaming SQL generation"""

    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language question about SNAP QC data"
    )
    user_id: str = Field(
        default="system",
        description="User ID for context"
    )


class StreamKBRequest(BaseModel):
    """Request model for streaming KB insight"""

    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Question to answer using knowledge base"
    )
    user_id: str = Field(
        default="anonymous@snapanalyst.com",
        description="User ID for filtering"
    )
    data_context: str | None = Field(
        None,
        description="Optional data context from a previous query"
    )


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
        try:
            from src.api.routers.query import SQLQueryRequest, execute_sql_query
            from src.core.filter_manager import get_filter_manager
            from src.services.llm_providers import _get_vanna_instance

            filter_manager = get_filter_manager()

            # Generate SQL using Vanna 0.x (with DDL from ChromaDB)
            vn = _get_vanna_instance()

            # Debug log the request
            logger.info(f"🔍 Streaming request - user_id: {request.user_id}, question: {request.question[:50]}...")

            # Set custom prompt if user_id provided
            if request.user_id and request.user_id != "system":
                from src.core.prompts import VANNA_SQL_SYSTEM_PROMPT
                from src.database.prompt_manager import get_user_prompt
                try:
                    system_prompt = get_user_prompt(request.user_id, 'sql')
                    logger.info(f"Streaming: Using custom SQL prompt for user {request.user_id}: {system_prompt[:100]}...")
                except Exception as e:
                    logger.warning(f"Streaming: Failed to get custom prompt for {request.user_id}: {e}")
                    system_prompt = VANNA_SQL_SYSTEM_PROMPT
                vn._custom_system_prompt = system_prompt

            sql = vn.generate_sql(request.question)

            if not sql:
                yield {"event": "error", "data": json.dumps({"error": "Could not generate SQL. Please rephrase your question."})}
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
                    "rows": query_response.data
                }
                yield {"event": "results", "data": json.dumps(results)}
            else:
                yield {"event": "error", "data": json.dumps({"error": query_response.error or "Query execution failed"})}

            yield {"event": "done", "data": json.dumps({"status": "complete"})}

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
            yield {"event": "done", "data": json.dumps({"status": "error"})}

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

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            # Parse filters
            filters = parse_kb_filters(request.question, request.user_id)

            yield {"event": "progress", "data": json.dumps({"message": "🔍 Searching knowledge base..."})}

            # Query based on path
            results = []
            try:
                if filters['chromadb_path'] == 'kb':
                    results = query_documents(
                        question=filters['question'],
                        user_id=request.user_id,
                        tags=filters['tags'],
                        category=filters['category'],
                        user_scope=filters['user_scope'],
                        n_results=5
                    )
                elif filters['chromadb_path'] == 'all':
                    results = query_all(
                        question=filters['question'],
                        user_id=request.user_id,
                        n_results=10
                    )
                else:
                    results = query_dataset(
                        question=filters['question'],
                        dataset_path=filters['chromadb_path'],
                        collections=filters['collections'],
                        n_results=5
                    )
            except Exception as e:
                logger.warning(f"Could not retrieve context: {e}")

            # Send sources
            sources_used = []
            chromadb_context = ""
            if results:
                context_parts = ["**Sources:**\n"]
                for i, result in enumerate(results, 1):
                    doc = result['document'][:300] + "..." if len(result['document']) > 300 else result['document']
                    source = result['source_display']
                    context_parts.append(f"{i}. {source}\n   {doc}\n")
                    sources_used.append(source)
                chromadb_context = "\n".join(context_parts)

                yield {"event": "sources", "data": json.dumps({"sources": sources_used, "count": len(results)})}
            elif not request.data_context:
                # KB-only lookup (/??): no documents and no thread context — stop early
                yield {"event": "text", "data": json.dumps({"chunk": "No documents found in the Knowledge Base.\n\nUpload documents with `/mem` and try again."})}
                yield {"event": "done", "data": json.dumps({"status": "complete", "sources": []})}
                return

            # Build prompt
            prompt = build_kb_insight_prompt(
                question=filters['question'],
                data_context=request.data_context,
                chromadb_context=chromadb_context,
                user_id=request.user_id
            )

            # Stream text generation
            llm_service = get_llm_service()
            if not llm_service._initialized:
                initialize_llm_service()

            # Use streaming text generation
            async for chunk in _generate_text_streaming(prompt, settings.llm_kb_max_tokens):
                yield {"event": "text", "data": json.dumps({"chunk": chunk})}

            yield {"event": "done", "data": json.dumps({"status": "complete", "sources": sources_used})}

        except Exception as e:
            logger.error(f"KB stream error: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


async def _generate_text_streaming(prompt: str, max_tokens: int = 500) -> AsyncGenerator[str, None]:
    """
    Stream text generation using LLM API.

    Supports OpenAI and Anthropic providers with native streaming.
    Falls back to non-streaming for other providers.
    """
    import asyncio

    from openai import OpenAIError

    from src.core.config import settings

    provider = settings.llm_provider

    try:
        if provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)

            try:
                stream = client.chat.completions.create(
                    model=settings.kb_model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    stream=True
                )

                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            except OpenAIError as e:
                error_msg = str(e)
                if hasattr(e, 'message'):
                    error_msg = e.message
                raise Exception(f"OpenAI API Error: {error_msg}")

        elif provider == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=settings.anthropic_api_key)

            # Run sync streaming in thread pool to avoid blocking event loop
            def sync_stream():
                chunks = []
                with client.messages.stream(
                    model=settings.kb_model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                ) as stream:
                    for text in stream.text_stream:
                        chunks.append(text)
                return chunks

            loop = asyncio.get_event_loop()
            chunks = await loop.run_in_executor(None, sync_stream)
            for chunk in chunks:
                yield chunk

        else:
            # Fallback to non-streaming for other providers
            text = get_llm_service().generate_text(prompt, max_tokens)
            yield text

    except Exception as e:
        logger.error(f"Streaming text generation failed: {e}")
        raise


