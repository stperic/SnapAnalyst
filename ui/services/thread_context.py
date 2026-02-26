"""
Thread Context Manager

Manages query history storage and retrieval for insight generation.
Tracks full conversation thread with structured data for Insights chat mode.

This provides a clean interface for storing and accessing query history
beyond just the last query.
"""

from dataclasses import asdict, dataclass
from datetime import datetime

import chainlit as cl

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ThreadQuery:
    """
    Single query entry in thread history.

    Stores question, SQL, results, and metadata for a single query execution.
    """

    question: str
    sql: str
    results: list[dict]
    row_count: int
    timestamp: str
    response_id: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    def get_summary(self) -> dict:
        """Get summary without full results (for token efficiency)."""
        return {
            "question": self.question,
            "sql": self.sql,
            "row_count": self.row_count,
            "timestamp": self.timestamp,
            "response_id": self.response_id,
        }


class ThreadContext:
    """
    Manages thread context for insight queries.

    Stores all queries from the current session in Chainlit user_session.
    Provides methods to add queries and retrieve context for insights.
    """

    SESSION_KEY = "thread_queries"
    MAX_THREAD_SIZE = 20  # Limit to last 20 queries
    MAX_STORED_ROWS = 50  # Cap stored result rows per query to limit memory

    def __init__(self):
        """Initialize thread context from session."""
        self._ensure_session_exists()

    def _ensure_session_exists(self):
        """Ensure thread_queries exists in session."""
        if not cl.user_session.get(self.SESSION_KEY):
            cl.user_session.set(self.SESSION_KEY, [])

    def add_query(
        self, question: str, sql: str, results: list[dict], row_count: int, response_id: str | None = None
    ) -> None:
        """
        Add a query to the thread history.

        Args:
            question: The natural language question
            sql: The executed SQL
            results: Query results (list of dicts)
            row_count: Number of rows returned
            response_id: Unique response identifier
        """
        self._ensure_session_exists()

        # Truncate results to cap memory usage while preserving enough for insight generation
        stored_results = results[: self.MAX_STORED_ROWS] if results else []

        query = ThreadQuery(
            question=question,
            sql=sql,
            results=stored_results,
            row_count=row_count,
            timestamp=datetime.now().isoformat(),
            response_id=response_id or "unknown",
        )

        queries = cl.user_session.get(self.SESSION_KEY)
        queries.append(query.to_dict())

        # Keep only last MAX_THREAD_SIZE queries
        if len(queries) > self.MAX_THREAD_SIZE:
            queries = queries[-self.MAX_THREAD_SIZE :]
            cl.user_session.set(self.SESSION_KEY, queries)

        logger.info(f"Added query to thread: {question[:60]}... (total: {len(queries)} queries)")

    def get_all_queries(self) -> list[ThreadQuery]:
        """
        Get all queries from thread history.

        Returns:
            List of ThreadQuery objects, oldest first
        """
        self._ensure_session_exists()
        queries_data = cl.user_session.get(self.SESSION_KEY)

        return [ThreadQuery(**q) for q in queries_data]

    def get_last_query(self) -> ThreadQuery | None:
        """
        Get the most recent query.

        Returns:
            ThreadQuery object or None if no queries
        """
        queries = self.get_all_queries()
        return queries[-1] if queries else None

    def get_thread_summary(self) -> dict:
        """
        Get thread summary for display (/history command).

        Returns:
            Summary dict with count and recent queries
        """
        queries = self.get_all_queries()

        return {
            "total_queries": len(queries),
            "recent_queries": [
                {"question": q.question[:100], "row_count": q.row_count, "timestamp": q.timestamp}
                for q in queries[-10:]  # Last 10 queries
            ],
        }

    def get_queries_for_insight(self, max_queries: int | None = None) -> list[ThreadQuery]:
        """
        Get queries for insight generation (most recent first).

        Args:
            max_queries: Maximum number of queries to return (None = all)

        Returns:
            List of ThreadQuery objects, newest first
        """
        queries = self.get_all_queries()
        queries.reverse()  # Newest first

        if max_queries:
            queries = queries[:max_queries]

        return queries

    def clear(self) -> None:
        """Clear all queries from thread."""
        cl.user_session.set(self.SESSION_KEY, [])
        logger.info("Thread context cleared")

    def get_count(self) -> int:
        """Get number of queries in thread."""
        self._ensure_session_exists()
        return len(cl.user_session.get(self.SESSION_KEY))


def get_thread_context() -> ThreadContext:
    """
    Get thread context instance for current session.

    Returns:
        ThreadContext instance
    """
    return ThreadContext()
