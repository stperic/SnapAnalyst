"""
Insight Service

Generates AI-powered insights using the /chat/kb API endpoint with thread context support.
Implements two-tier insight system:
- /? : Knowledge base only (fast, lightweight)
- /??: Knowledge base + full thread context (comprehensive)

Configuration via .env:
- LLM_KB_MAX_TOKENS: Max response tokens for insights (default: 150)
- LLM_KB_MAX_PROMPT_SIZE: Total max prompt size (default: 15000)
- LLM_KB_TEMPERATURE: Temperature for insights (default: uses LLM_TEMPERATURE)
"""
from __future__ import annotations

from ..clients.api_client import call_api
from ..core.config import settings
from ..core.logging import get_logger

# Import context builder
from .insight_context_builder import build_insight_context

logger = get_logger(__name__)


async def generate_chromadb_insight(
    insight_question: str,
    include_thread: bool = False,
    max_tokens: int | None = None
) -> str:
    """
    Generate insight using ChromaDB + optional thread context.

    Two modes:
    - /? : Knowledge base only (include_thread=False)
    - /??: Knowledge base + full thread (include_thread=True)

    Args:
        insight_question: The insight question
        include_thread: Include full thread history (/??=True, /?=False)
        max_tokens: Maximum tokens for context (uses config default if None)

    Returns:
        AI-generated insight with transparency indicators
    """
    try:
        # Use configured token limit if not specified
        if max_tokens is None:
            max_tokens = settings.llm_kb_max_prompt_size or 15000

        logger.info(f"Generating insight: include_thread={include_thread}, max_tokens={max_tokens}")

        # Query ChromaDB for relevant knowledge base docs
        # Note: This should be done by the API endpoint, but we log it here
        logger.info(f"Calling /chat/kb endpoint for: {insight_question[:60]}...")

        # Build context with smart token management
        context = build_insight_context(
            insight_question=insight_question,
            include_thread=include_thread,
            knowledge_base_results=None,  # Let API fetch KB results
            max_tokens=max_tokens
        )

        # Prepare API request data
        request_data = {
            "question": insight_question,
            "include_thread": include_thread,
        }

        # Include thread context if available
        if include_thread and context.thread_queries:
            request_data["thread_history"] = context.thread_queries

        # Include query data if available
        if include_thread and context.query_data:
            request_data["query_data"] = context.query_data

        # Call the /chat/kb endpoint
        response = await call_api(
            "/chat/kb",
            method="POST",
            data=request_data
        )

        if response and "insight" in response:
            insight_text = response["insight"].strip()

            # Build response with transparency indicators
            response_parts = [insight_text]

            # Add footer with context info
            response_parts.append("\n---")

            token_usage = context.token_usage or {}

            if include_thread:
                # Full thread mode
                thread_count = len(context.thread_queries) if context.thread_queries else 0
                data_count = len(context.query_data) if context.query_data else 0

                context_info = f"_Used knowledge base + {thread_count} queries in thread"
                if data_count > 0:
                    context_info += f" ({data_count} with data)"
                context_info += "_"

                response_parts.append(context_info)

                # Show token usage if available
                if token_usage.get("total"):
                    response_parts.append(f"_Tokens: {token_usage['total']:,} / {max_tokens:,}_")
            else:
                # KB only mode
                response_parts.append("_Used knowledge base only (no query data)_")

            return "\n".join(response_parts)
        else:
            logger.warning("Empty response from /chat/kb endpoint")
            return "Unable to generate insight. Please try rephrasing your question."

    except Exception as e:
        logger.error(f"Error generating insight: {e}")
        return f"Error generating insight: {str(e)}"


