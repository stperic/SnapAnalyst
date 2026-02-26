"""Feedback-driven Vanna training — maps user thumbs up/down to ChromaDB updates."""

import asyncio
import hashlib
import json
import uuid
from collections import OrderedDict

from src.core.config import settings
from src.core.logging import get_llm_logger, get_logger

logger = get_logger(__name__)
llm_logger = get_llm_logger()

# Bounded mapping: message_id → (question, sql)
# Only SQL mode messages are stored here; Insights/Knowledge messages are not.
_query_map: OrderedDict[str, tuple[str, str]] = OrderedDict()
_QUERY_MAP_MAX = 500


def store_query_for_feedback(message_id: str, question: str, sql: str) -> None:
    """Store a message_id → (question, sql) mapping for later feedback lookup."""
    if len(_query_map) >= _QUERY_MAP_MAX:
        _query_map.popitem(last=False)  # Remove oldest
    _query_map[message_id] = (question, sql)


def get_query_for_feedback(message_id: str) -> tuple[str, str] | None:
    """Look up question+sql for a message ID. Returns None if not found (non-SQL message)."""
    return _query_map.get(message_id)


def _compute_training_id(question: str, sql: str) -> str:
    """Compute the deterministic training ID that Vanna would use for this pair.

    Mirrors Vanna's ChromaDB_VectorStore.add_question_sql() ID computation:
    deterministic_uuid(json.dumps({"question": q, "sql": s})) + "-sql"
    """
    content = json.dumps({"question": question, "sql": sql}, ensure_ascii=False)
    content_bytes = content.encode("utf-8")
    hash_hex = hashlib.sha256(content_bytes).hexdigest()
    namespace = uuid.UUID("00000000-0000-0000-0000-000000000000")
    content_uuid = str(uuid.uuid5(namespace, hash_hex))
    return content_uuid + "-sql"


def _train_positive(question: str, sql: str) -> str:
    """Add question+SQL pair to Vanna ChromaDB (synchronous)."""
    from src.services.llm_providers import _get_vanna_instance

    vn = _get_vanna_instance()
    training_id = vn.train(question=question, sql=sql)
    return training_id


def _train_negative(question: str, sql: str) -> bool:
    """Remove question+SQL pair from Vanna ChromaDB if it exists (synchronous)."""
    from src.services.llm_providers import _get_vanna_instance

    vn = _get_vanna_instance()
    training_id = _compute_training_id(question, sql)
    return vn.remove_training_data(id=training_id)


async def handle_feedback_training(feedback_for_id: str, feedback_value: int, comment: str | None = None) -> None:
    """
    Process feedback for Vanna training. Called from data layer's upsert_feedback().

    Args:
        feedback_for_id: The Chainlit message ID (feedback.forId)
        feedback_value: 1 = thumbs up, 0 = thumbs down
        comment: Optional user comment
    """
    if not settings.vanna_store_user_queries:
        return  # Feature disabled

    query = get_query_for_feedback(feedback_for_id)
    if not query:
        return  # Not a SQL query message (Insights, Knowledge, etc.)

    question, sql = query

    try:
        if feedback_value == 1:  # Thumbs up
            training_id = await asyncio.to_thread(_train_positive, question, sql)
            llm_logger.info(f"[FEEDBACK TRAIN] thumbs_up question={question[:80]} training_id={training_id}")
            logger.info(f"Feedback training: added pair (id={training_id})")
        else:  # Thumbs down (value == 0)
            removed = await asyncio.to_thread(_train_negative, question, sql)
            llm_logger.info(
                f"[FEEDBACK TRAIN] thumbs_down question={question[:80]} removed={removed} comment={comment}"
            )
            logger.info(f"Feedback training: {'removed' if removed else 'not found (ok)'} pair")
    except Exception as e:
        logger.error(f"Feedback training error: {e}")
        # Don't propagate — feedback persistence should still succeed
