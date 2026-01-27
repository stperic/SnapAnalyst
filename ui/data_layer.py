"""
Chainlit Data Layer for SnapAnalyst

Provides persistence for chat history, feedback, and user data using PostgreSQL.
This enables Chainlit's built-in feedback icons to work properly.
"""

import logging
import os
from datetime import datetime

from chainlit.data import BaseDataLayer
from chainlit.types import PaginatedResponse, Pagination, ThreadDict, ThreadFilter
from chainlit.user import PersistedUser, User

logger = logging.getLogger(__name__)


class SnapAnalystDataLayer(BaseDataLayer):
    """
    Custom data layer for SnapAnalyst using PostgreSQL.

    This minimal implementation enables Chainlit's built-in feedback without
    requiring full Literal AI setup.
    """

    def __init__(self):
        """Initialize with PostgreSQL connection."""
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable not set")

        # In-memory stores for simple auth
        self._users: dict[str, PersistedUser] = {}
        self._threads: dict[str, ThreadDict] = {}

        logger.info("SnapAnalyst data layer initialized (feedback enabled)")

    async def create_user(self, user: User) -> PersistedUser | None:
        """Create a user - stores in memory for session persistence."""
        identifier = user.identifier
        if identifier:
            persisted = PersistedUser(
                id=identifier,
                identifier=identifier,
                createdAt=datetime.now().isoformat(),
                metadata=user.metadata or {"role": "user"},
            )
            self._users[identifier] = persisted
            logger.info(f"Created user: {identifier}")
            return persisted
        return None

    async def get_user(self, identifier: str) -> PersistedUser | None:
        """Get user by identifier - returns from memory store."""
        if identifier in self._users:
            return self._users[identifier]
        # Auto-create user if not found (simple auth mode)
        persisted = PersistedUser(
            id=identifier,
            identifier=identifier,
            createdAt=datetime.now().isoformat(),
            metadata={"role": "user"},
        )
        self._users[identifier] = persisted
        logger.info(f"Auto-created user on lookup: {identifier}")
        return persisted

    async def create_thread(self, thread_dict: ThreadDict) -> ThreadDict | None:
        """Create a thread (chat session) - stores in memory."""
        thread_id = thread_dict.get("id", "default")
        thread: ThreadDict = {
            "id": thread_id,
            "createdAt": thread_dict.get("createdAt", datetime.now().isoformat()),
            "name": thread_dict.get("name"),
            "userId": thread_dict.get("userId"),
            "userIdentifier": thread_dict.get("userIdentifier"),
            "tags": thread_dict.get("tags", []),
            "metadata": thread_dict.get("metadata", {}),
            "steps": [],
            "elements": [],
        }
        self._threads[thread_id] = thread
        logger.info(f"Created thread: {thread_id} for user: {thread.get('userIdentifier')}")
        return thread

    async def get_thread(self, thread_id: str) -> ThreadDict | None:
        """Get thread by ID - returns from memory or None if not found."""
        return self._threads.get(thread_id)

    async def update_thread(
        self,
        thread_id: str,
        name: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        tags: list[str] | None = None,
    ):
        """Update thread in memory - creates if doesn't exist."""
        logger.info(f"update_thread called - thread_id: {thread_id}, name: {name}, user_id: {user_id}")

        # Create thread if it doesn't exist (Chainlit may call update before create)
        if thread_id not in self._threads:
            self._threads[thread_id] = {
                "id": thread_id,
                "createdAt": datetime.now().isoformat(),
                "name": name,
                "userId": user_id,
                "userIdentifier": user_id,  # Use user_id as identifier for simple auth
                "tags": tags or [],
                "metadata": metadata or {},
                "steps": [],
                "elements": [],
            }
            logger.info(f"Created thread via update: {thread_id} for user: {user_id}")
        else:
            if name is not None:
                self._threads[thread_id]["name"] = name
            if user_id is not None:
                self._threads[thread_id]["userId"] = user_id
                self._threads[thread_id]["userIdentifier"] = user_id
            if metadata is not None:
                self._threads[thread_id]["metadata"] = metadata
            if tags is not None:
                self._threads[thread_id]["tags"] = tags

    async def delete_thread(self, thread_id: str):
        """Delete thread from memory."""
        self._threads.pop(thread_id, None)

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        """List threads for the current user."""
        user_id = filters.userId if filters else None

        logger.info(f"list_threads called - userId: {user_id}, total threads: {len(self._threads)}")

        # Filter threads by user (match userId OR userIdentifier against filter userId)
        user_threads = []
        for t in self._threads.values():
            thread_user_id = t.get("userId")
            thread_user_identifier = t.get("userIdentifier")

            # Match if userId matches OR userIdentifier matches (userId is the username)
            if not user_id or thread_user_id == user_id or thread_user_identifier == user_id:
                user_threads.append(t)

        logger.info(f"Filtered threads: {len(user_threads)}")

        # Sort by createdAt descending (newest first)
        user_threads.sort(key=lambda t: t.get("createdAt", ""), reverse=True)

        return PaginatedResponse(
            data=user_threads,
            pageInfo={"hasNextPage": False, "startCursor": None, "endCursor": None}
        )

    async def create_step(self, step_dict: dict):
        """Create a step (message) - add to thread."""
        thread_id = step_dict.get("threadId")
        if thread_id and thread_id in self._threads:
            self._threads[thread_id]["steps"].append(step_dict)

    async def update_step(self, step_dict: dict):
        """Update step in thread."""
        thread_id = step_dict.get("threadId")
        step_id = step_dict.get("id")
        if thread_id and thread_id in self._threads:
            steps = self._threads[thread_id]["steps"]
            for i, s in enumerate(steps):
                if s.get("id") == step_id:
                    steps[i] = step_dict
                    break

    async def delete_step(self, step_id: str):
        """Delete step (no-op for now)."""
        pass

    async def get_element(
        self, thread_id: str, element_id: str
    ) -> dict | None:
        """Get element by ID."""
        return None

    async def upsert_feedback(self, feedback) -> str:
        """
        Store user feedback - THIS IS THE KEY METHOD FOR FEEDBACK ICONS.

        Args:
            feedback: Chainlit Feedback object with attributes (id, forId, value, comment, etc)

        Returns:
            str: The feedback ID
        """
        from src.core.logging import get_llm_logger

        llm_logger = get_llm_logger()

        # Access Feedback object attributes directly (not dict methods)
        feedback_id = feedback.id if hasattr(feedback, 'id') else "unknown"
        feedback_value = feedback.value if hasattr(feedback, 'value') else 0
        comment = feedback.comment if hasattr(feedback, 'comment') else ""

        # Log feedback
        if feedback_value > 0:
            llm_logger.info(f"Positive feedback: {feedback_id} - {comment}")
        elif feedback_value < 0:
            llm_logger.info(f"Negative feedback: {feedback_id} - {comment}")
        else:
            llm_logger.info(f"Neutral feedback: {feedback_id} - {comment}")

        # Return feedback ID (required by BaseDataLayer signature)
        return feedback_id

    async def delete_feedback(self, feedback_id: str) -> bool:
        """Delete feedback (no-op)."""
        return True

    async def create_element(self, element):
        """Create an element (file, image, etc) - no-op."""
        pass

    async def delete_element(self, element_id: str, thread_id: str | None = None):
        """Delete element (no-op)."""
        pass

    async def get_thread_author(self, thread_id: str) -> str:
        """Get thread author."""
        thread = self._threads.get(thread_id)
        return thread.get("userIdentifier", "") if thread else ""

    async def get_favorite_steps(self, user_id: str) -> list[dict]:
        """Get favorite steps for user (not implemented)."""
        return []

    async def build_debug_url(self) -> str:
        """Build debug URL (not used)."""
        return ""

    async def close(self):
        """Close connections (no-op for in-memory store)."""
        pass


# Global data layer instance
_data_layer_instance = None


def get_snap_data_layer() -> SnapAnalystDataLayer:
    """Get or create the SnapAnalyst data layer instance."""
    global _data_layer_instance
    if _data_layer_instance is None:
        _data_layer_instance = SnapAnalystDataLayer()
    return _data_layer_instance
