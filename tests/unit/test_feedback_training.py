"""Tests for feedback-driven Vanna training."""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock chainlit before importing ui.services (ui/services/__init__.py imports startup.py which needs chainlit).
# Use spec-less MagicMock but configure user_session.get to return None by default,
# so filter_manager._get_user_id() falls through to the DB fallback path correctly.
if "chainlit" not in sys.modules:
    _mock_chainlit = MagicMock()
    _mock_chainlit.user_session.get.return_value = None
    sys.modules["chainlit"] = _mock_chainlit

from ui.services.feedback_training import (  # noqa: E402
    _QUERY_MAP_MAX,
    _compute_training_id,
    _query_map,
    get_query_for_feedback,
    handle_feedback_training,
    store_query_for_feedback,
)


@pytest.fixture(autouse=True)
def clear_query_map():
    """Clear the module-level query map before each test."""
    _query_map.clear()
    yield
    _query_map.clear()


class TestQueryMap:
    def test_store_and_retrieve_query(self):
        """Round-trip through query map."""
        store_query_for_feedback("msg-1", "What is the error rate?", "SELECT * FROM error_rates")
        result = get_query_for_feedback("msg-1")
        assert result == ("What is the error rate?", "SELECT * FROM error_rates")

    def test_get_missing_returns_none(self):
        """Non-SQL messages (Insights, Knowledge) are not stored — returns None."""
        assert get_query_for_feedback("nonexistent-id") is None

    def test_query_map_bounded(self):
        """Verify oldest entries evicted at max size."""
        for i in range(_QUERY_MAP_MAX + 10):
            store_query_for_feedback(f"msg-{i}", f"question-{i}", f"sql-{i}")

        assert len(_query_map) == _QUERY_MAP_MAX
        # First 10 should be evicted
        assert get_query_for_feedback("msg-0") is None
        assert get_query_for_feedback("msg-9") is None
        # Last entries should still be present
        assert get_query_for_feedback(f"msg-{_QUERY_MAP_MAX + 9}") is not None


class TestComputeTrainingId:
    def test_deterministic(self):
        """Same input always produces the same ID."""
        id1 = _compute_training_id("What is X?", "SELECT x FROM t")
        id2 = _compute_training_id("What is X?", "SELECT x FROM t")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        """Different inputs produce different IDs."""
        id1 = _compute_training_id("What is X?", "SELECT x FROM t")
        id2 = _compute_training_id("What is Y?", "SELECT y FROM t")
        assert id1 != id2

    def test_ends_with_sql_suffix(self):
        """Training IDs for SQL pairs end with -sql."""
        training_id = _compute_training_id("question", "SELECT 1")
        assert training_id.endswith("-sql")

    def test_matches_vanna_computation(self):
        """Verify our ID computation matches Vanna's deterministic_uuid + '-sql'."""
        import hashlib
        import json
        import uuid

        question = "What is the payment error rate?"
        sql = "SELECT state, error_rate FROM state_error_rates"

        # Our computation
        our_id = _compute_training_id(question, sql)

        # Replicate Vanna's computation exactly
        content = json.dumps({"question": question, "sql": sql}, ensure_ascii=False)
        content_bytes = content.encode("utf-8")
        hash_hex = hashlib.sha256(content_bytes).hexdigest()
        namespace = uuid.UUID("00000000-0000-0000-0000-000000000000")
        vanna_id = str(uuid.uuid5(namespace, hash_hex)) + "-sql"

        assert our_id == vanna_id


class TestHandleFeedbackTraining:
    @pytest.mark.asyncio
    async def test_positive_trains(self):
        """Thumbs up calls vn.train() with correct question+sql."""
        store_query_for_feedback("msg-1", "What is X?", "SELECT x FROM t")

        mock_vn = MagicMock()
        mock_vn.train.return_value = "fake-training-id-sql"

        with (
            patch("src.services.llm_providers._get_vanna_instance", return_value=mock_vn),
            patch("ui.services.feedback_training.settings") as mock_settings,
        ):
            mock_settings.vanna_store_user_queries = True
            await handle_feedback_training("msg-1", feedback_value=1)

        mock_vn.train.assert_called_once_with(question="What is X?", sql="SELECT x FROM t")

    @pytest.mark.asyncio
    async def test_negative_removes(self):
        """Thumbs down calls vn.remove_training_data() with computed ID."""
        store_query_for_feedback("msg-1", "What is X?", "SELECT x FROM t")

        expected_id = _compute_training_id("What is X?", "SELECT x FROM t")
        mock_vn = MagicMock()
        mock_vn.remove_training_data.return_value = True

        with (
            patch("src.services.llm_providers._get_vanna_instance", return_value=mock_vn),
            patch("ui.services.feedback_training.settings") as mock_settings,
        ):
            mock_settings.vanna_store_user_queries = True
            await handle_feedback_training("msg-1", feedback_value=0, comment="Wrong SQL")

        mock_vn.remove_training_data.assert_called_once_with(id=expected_id)

    @pytest.mark.asyncio
    async def test_disabled_skips_training(self):
        """When vanna_store_user_queries=False, no training occurs."""
        store_query_for_feedback("msg-1", "What is X?", "SELECT x FROM t")

        with (
            patch("src.services.llm_providers._get_vanna_instance") as mock_get_vn,
            patch("ui.services.feedback_training.settings") as mock_settings,
        ):
            mock_settings.vanna_store_user_queries = False
            await handle_feedback_training("msg-1", feedback_value=1)

        mock_get_vn.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_sql_message_noop(self):
        """Feedback on unknown message ID (non-SQL) is a no-op."""
        with (
            patch("src.services.llm_providers._get_vanna_instance") as mock_get_vn,
            patch("ui.services.feedback_training.settings") as mock_settings,
        ):
            mock_settings.vanna_store_user_queries = True
            await handle_feedback_training("unknown-msg-id", feedback_value=1)

        mock_get_vn.assert_not_called()

    @pytest.mark.asyncio
    async def test_training_error_does_not_propagate(self):
        """Training errors are logged but don't propagate."""
        store_query_for_feedback("msg-1", "What is X?", "SELECT x FROM t")

        mock_vn = MagicMock()
        mock_vn.train.side_effect = RuntimeError("ChromaDB connection failed")

        with (
            patch("src.services.llm_providers._get_vanna_instance", return_value=mock_vn),
            patch("ui.services.feedback_training.settings") as mock_settings,
        ):
            mock_settings.vanna_store_user_queries = True
            # Should not raise
            await handle_feedback_training("msg-1", feedback_value=1)
