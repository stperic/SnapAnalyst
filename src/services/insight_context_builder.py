"""
Insight Context Builder

Builds context for insight queries with smart token budget management.
Implements priority-based inclusion of ChromaDB results, thread history,
and query data within configurable token limits.
"""

import json
import logging
from dataclasses import dataclass

import tiktoken

from ui.services.thread_context import ThreadQuery, get_thread_context

logger = logging.getLogger(__name__)


@dataclass
class InsightContext:
    """
    Container for insight generation context.

    Stores all context components with token usage tracking.
    """
    insight_question: str
    knowledge_base_results: list[str] | None = None
    thread_queries: list[dict] | None = None  # Questions + SQL + metadata
    query_data: list[dict] | None = None      # Actual row data (newest first)
    token_usage: dict[str, int] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API call."""
        return {
            "question": self.insight_question,
            "knowledge_base_results": self.knowledge_base_results,
            "thread_history": self.thread_queries,
            "query_data": self.query_data,
            "token_usage": self.token_usage
        }


class TokenCounter:
    """
    Token counter using tiktoken (same as OpenAI).
    Provides rough estimation for token budget management.
    """

    def __init__(self, model: str = "gpt-3.5-turbo"):
        """Initialize with model encoding."""
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base (GPT-3.5/GPT-4)
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def count_tokens_dict(self, data: dict) -> int:
        """Count tokens in dictionary (convert to JSON first)."""
        return self.count_tokens(json.dumps(data, default=str))

    def count_tokens_list(self, data: list) -> int:
        """Count tokens in list (convert to JSON first)."""
        return self.count_tokens(json.dumps(data, default=str))


class InsightContextBuilder:
    """
    Builds context for insight generation with smart token management.

    Priority:
    1. ChromaDB KB results (always included)
    2. Thread questions + SQL + counts (if include_thread=True)
    3. Last query data (always if include_thread=True)
    4. Earlier query data (work backwards, fit what we can)
    """

    def __init__(self, max_tokens: int = 15000):
        """
        Initialize context builder.

        Args:
            max_tokens: Maximum tokens for entire context
        """
        self.max_tokens = max_tokens
        self.token_counter = TokenCounter()
        self.token_usage = {
            "total": 0,
            "question": 0,
            "knowledge_base": 0,
            "thread_metadata": 0,
            "query_data": 0,
            "budget_remaining": max_tokens
        }

    def build_context(
        self,
        insight_question: str,
        include_thread: bool = False,
        knowledge_base_results: list[str] | None = None
    ) -> InsightContext:
        """
        Build insight context with smart token management.

        Args:
            insight_question: The insight question
            include_thread: Include thread history (/??=True, /?=False)
            knowledge_base_results: Pre-fetched KB results (or None to fetch)

        Returns:
            InsightContext with all components
        """
        logger.info(f"Building context for insight: include_thread={include_thread}")

        # Reset token usage
        self.token_usage = {
            "total": 0,
            "question": 0,
            "knowledge_base": 0,
            "thread_metadata": 0,
            "query_data": 0,
            "budget_remaining": self.max_tokens
        }

        # 1. Count question tokens
        question_tokens = self.token_counter.count_tokens(insight_question)
        self._use_tokens("question", question_tokens)
        logger.info(f"Question tokens: {question_tokens}")

        # 2. Include KB results (priority 1)
        kb_results = knowledge_base_results or []
        if kb_results:
            kb_tokens = self.token_counter.count_tokens_list(kb_results)
            self._use_tokens("knowledge_base", kb_tokens)
            logger.info(f"KB results tokens: {kb_tokens}")

        # 3. Build thread context if requested
        thread_queries = None
        query_data = None

        if include_thread:
            thread_ctx = get_thread_context()
            queries = thread_ctx.get_queries_for_insight()  # Newest first

            if queries:
                # Build thread metadata (questions + SQL + counts)
                thread_queries = self._build_thread_metadata(queries)

                # Build query data (newest first, fit what we can)
                query_data = self._build_query_data(queries)

        # Create context object
        context = InsightContext(
            insight_question=insight_question,
            knowledge_base_results=kb_results,
            thread_queries=thread_queries,
            query_data=query_data,
            token_usage=self.token_usage.copy()
        )

        logger.info(f"Context built - Total tokens: {self.token_usage['total']}/{self.max_tokens}")

        return context

    def _build_thread_metadata(self, queries: list[ThreadQuery]) -> list[dict]:
        """
        Build thread metadata (questions + SQL + counts only, no data).

        Args:
            queries: List of ThreadQuery objects (newest first)

        Returns:
            List of thread query summaries
        """
        thread_metadata = []

        for query in queries:
            summary = {
                "question": query.question,
                "sql": query.sql,
                "row_count": query.row_count,
                "timestamp": query.timestamp
            }

            # Check if we have budget for this
            summary_tokens = self.token_counter.count_tokens_dict(summary)

            if self.token_usage["budget_remaining"] >= summary_tokens:
                thread_metadata.append(summary)
                self._use_tokens("thread_metadata", summary_tokens)
            else:
                logger.warning(f"Skipping query metadata (insufficient tokens): {query.question[:50]}")
                break

        logger.info(f"Thread metadata: {len(thread_metadata)} queries, {self.token_usage['thread_metadata']} tokens")

        return thread_metadata

    def _build_query_data(self, queries: list[ThreadQuery]) -> list[dict]:
        """
        Build query data (actual results), newest first, fit what we can.

        Args:
            queries: List of ThreadQuery objects (newest first)

        Returns:
            List of query data entries with results
        """
        query_data = []

        for i, query in enumerate(queries):
            # Prepare data entry
            data_entry = {
                "question": query.question,
                "row_count": query.row_count,
                "results": query.results
            }

            # Count tokens
            data_tokens = self.token_counter.count_tokens_dict(data_entry)

            # Check budget
            if self.token_usage["budget_remaining"] >= data_tokens:
                query_data.append(data_entry)
                self._use_tokens("query_data", data_tokens)
                logger.info(f"Included query data {i+1}/{len(queries)}: {query.question[:50]} ({data_tokens} tokens)")
            else:
                # Try with truncated results
                truncated_entry = self._try_truncate_results(query, data_entry)

                if truncated_entry:
                    query_data.append(truncated_entry)
                    logger.info(f"Included truncated query data {i+1}/{len(queries)}: {query.question[:50]}")
                else:
                    logger.warning(f"Skipping query data {i+1}/{len(queries)} (insufficient tokens)")
                    break

        logger.info(f"Query data: {len(query_data)} queries, {self.token_usage['query_data']} tokens")

        return query_data

    def _try_truncate_results(self, query: ThreadQuery, _data_entry: dict) -> dict | None:
        """
        Try to fit query data by truncating results.

        Args:
            query: ThreadQuery object
            _data_entry: Original data entry (unused, rebuilt from query)

        Returns:
            Truncated data entry or None if can't fit
        """
        # Try including just first 10, 5, then 1 row
        for limit in [10, 5, 1]:
            truncated_results = query.results[:limit]
            truncated_entry = {
                "question": query.question,
                "row_count": query.row_count,
                "results": truncated_results,
                "truncated": True,
                "rows_included": len(truncated_results)
            }

            truncated_tokens = self.token_counter.count_tokens_dict(truncated_entry)

            if self.token_usage["budget_remaining"] >= truncated_tokens:
                self._use_tokens("query_data", truncated_tokens)
                logger.info(f"Truncated results to {limit} rows ({truncated_tokens} tokens)")
                return truncated_entry

        return None

    def _use_tokens(self, category: str, tokens: int):
        """
        Update token usage tracking.

        Args:
            category: Token category (question, knowledge_base, etc.)
            tokens: Number of tokens used
        """
        self.token_usage[category] += tokens
        self.token_usage["total"] += tokens
        self.token_usage["budget_remaining"] = self.max_tokens - self.token_usage["total"]


def build_insight_context(
    insight_question: str,
    include_thread: bool = False,
    knowledge_base_results: list[str] | None = None,
    max_tokens: int = 15000
) -> InsightContext:
    """
    Build context for insight generation.

    Convenience function that creates a builder and builds context.

    Args:
        insight_question: The insight question
        include_thread: Include thread history (/??=True, /?=False)
        knowledge_base_results: Pre-fetched KB results
        max_tokens: Maximum tokens for context

    Returns:
        InsightContext with all components
    """
    builder = InsightContextBuilder(max_tokens=max_tokens)
    return builder.build_context(
        insight_question=insight_question,
        include_thread=include_thread,
        knowledge_base_results=knowledge_base_results
    )
