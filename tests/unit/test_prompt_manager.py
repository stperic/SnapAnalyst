"""
Unit tests for User Prompt Manager

Tests custom LLM prompt storage and retrieval functionality.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.database.prompt_manager import (
    get_default_prompt,
    get_user_prompt,
    has_custom_prompt,
    reset_user_prompt,
    set_user_prompt,
)


class TestGetDefaultPrompt:
    """Test get_default_prompt function"""

    def test_get_default_sql_prompt(self):
        """Test getting default SQL prompt"""
        prompt = get_default_prompt("sql")

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_default_kb_prompt(self):
        """Test getting default KB prompt"""
        prompt = get_default_prompt("kb")

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_invalid_prompt_type(self):
        """Test raises error for invalid prompt type"""
        with pytest.raises(ValueError, match="Invalid prompt_type"):
            get_default_prompt("invalid")


class TestGetUserPrompt:
    """Test get_user_prompt function"""

    @patch("src.database.prompt_manager.get_db_context")
    def test_get_custom_sql_prompt(self, mock_context):
        """Test retrieving custom SQL prompt"""
        # Mock database session
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session

        # Mock result with custom prompt
        mock_result = MagicMock()
        mock_result.prompt_text = "Custom SQL prompt"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_result

        prompt = get_user_prompt("user123", "sql")

        assert prompt == "Custom SQL prompt"

    @patch("src.database.prompt_manager.get_db_context")
    def test_get_prompt_falls_back_to_default(self, mock_context):
        """Test falls back to default when no custom prompt exists"""
        # Mock database session
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session

        # Mock no custom prompt found
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        prompt = get_user_prompt("user123", "sql")

        # Should return default prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @patch("src.database.prompt_manager.get_db_context")
    def test_get_prompt_handles_exception(self, mock_context):
        """Test handles database exception gracefully"""
        # Mock database session that raises exception
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session
        mock_session.execute.side_effect = Exception("Database error")

        # Should return default prompt on error
        prompt = get_user_prompt("user123", "sql")

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_prompt_invalid_type(self):
        """Test raises error for invalid prompt type"""
        with pytest.raises(ValueError, match="Invalid prompt_type"):
            get_user_prompt("user123", "invalid")


class TestSetUserPrompt:
    """Test set_user_prompt function"""

    @patch("src.database.prompt_manager.get_db_context")
    def test_create_new_prompt(self, mock_context):
        """Test creating new custom prompt"""
        # Mock database session
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session

        # Mock no existing prompt
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        result = set_user_prompt("user123", "sql", "My custom SQL prompt for better results")

        assert result is True
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("src.database.prompt_manager.get_db_context")
    def test_update_existing_prompt(self, mock_context):
        """Test updating existing custom prompt"""
        # Mock database session
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session

        # Mock existing prompt
        mock_existing = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_existing

        result = set_user_prompt("user123", "sql", "Updated SQL prompt text")

        assert result is True
        assert mock_existing.prompt_text == "Updated SQL prompt text"
        assert isinstance(mock_existing.updated_at, datetime)
        mock_session.commit.assert_called_once()

    def test_set_prompt_too_short(self):
        """Test raises error for prompt too short"""
        with pytest.raises(ValueError, match="must be between 20 and 5000"):
            set_user_prompt("user123", "sql", "Too short")

    def test_set_prompt_too_long(self):
        """Test raises error for prompt too long"""
        long_prompt = "A" * 5001  # 5001 characters
        with pytest.raises(ValueError, match="must be between 20 and 5000"):
            set_user_prompt("user123", "sql", long_prompt)

    def test_set_prompt_invalid_type(self):
        """Test raises error for invalid prompt type"""
        with pytest.raises(ValueError, match="Invalid prompt_type"):
            set_user_prompt("user123", "invalid", "Valid prompt text here")

    @patch("src.database.prompt_manager.get_db_context")
    def test_set_prompt_handles_exception(self, mock_context):
        """Test handles database exception"""
        # Mock database session that raises exception
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session
        mock_session.execute.side_effect = Exception("Database error")

        result = set_user_prompt("user123", "sql", "Valid prompt text here")

        assert result is False


class TestResetUserPrompt:
    """Test reset_user_prompt function"""

    @patch("src.database.prompt_manager.get_db_context")
    def test_reset_existing_prompt(self, mock_context):
        """Test resetting existing custom prompt"""
        # Mock database session
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session

        # Mock existing prompt
        mock_existing = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_existing

        result = reset_user_prompt("user123", "sql")

        assert result is True
        mock_session.delete.assert_called_once_with(mock_existing)
        mock_session.commit.assert_called_once()

    @patch("src.database.prompt_manager.get_db_context")
    def test_reset_nonexistent_prompt(self, mock_context):
        """Test resetting when no custom prompt exists"""
        # Mock database session
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session

        # Mock no existing prompt
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        result = reset_user_prompt("user123", "sql")

        # Should return True (not an error)
        assert result is True
        mock_session.delete.assert_not_called()

    def test_reset_prompt_invalid_type(self):
        """Test raises error for invalid prompt type"""
        with pytest.raises(ValueError, match="Invalid prompt_type"):
            reset_user_prompt("user123", "invalid")

    @patch("src.database.prompt_manager.get_db_context")
    def test_reset_prompt_handles_exception(self, mock_context):
        """Test handles database exception"""
        # Mock database session that raises exception
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session
        mock_session.execute.side_effect = Exception("Database error")

        result = reset_user_prompt("user123", "sql")

        assert result is False


class TestHasCustomPrompt:
    """Test has_custom_prompt function"""

    @patch("src.database.prompt_manager.get_db_context")
    def test_has_custom_prompt_true(self, mock_context):
        """Test returns True when custom prompt exists"""
        # Mock database session
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session

        # Mock existing prompt
        mock_result = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_result

        result = has_custom_prompt("user123", "sql")

        assert result is True

    @patch("src.database.prompt_manager.get_db_context")
    def test_has_custom_prompt_false(self, mock_context):
        """Test returns False when no custom prompt exists"""
        # Mock database session
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session

        # Mock no prompt found
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        result = has_custom_prompt("user123", "sql")

        assert result is False

    def test_has_custom_prompt_invalid_type(self):
        """Test raises error for invalid prompt type"""
        with pytest.raises(ValueError, match="Invalid prompt_type"):
            has_custom_prompt("user123", "invalid")

    @patch("src.database.prompt_manager.get_db_context")
    def test_has_custom_prompt_handles_exception(self, mock_context):
        """Test handles database exception"""
        # Mock database session that raises exception
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session
        mock_session.execute.side_effect = Exception("Database error")

        result = has_custom_prompt("user123", "sql")

        assert result is False


class TestPromptManagerIntegration:
    """Integration tests for prompt manager"""

    @patch("src.database.prompt_manager.get_db_context")
    def test_kb_prompt_type(self, mock_context):
        """Test KB prompt type works across all functions"""
        # Mock database session
        mock_session = MagicMock()
        mock_context.return_value.__enter__.return_value = mock_session
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        # Test all functions with 'kb' type
        get_user_prompt("user123", "kb")
        set_user_prompt("user123", "kb", "Custom KB prompt text here")
        reset_user_prompt("user123", "kb")
        has_custom_prompt("user123", "kb")

        # Should not raise any errors

    def test_prompt_validation_boundary(self):
        """Test prompt length validation at boundaries"""
        # Exactly 20 characters (minimum)
        valid_min = "A" * 20
        # Should not raise
        try:
            set_user_prompt("user123", "sql", valid_min)
        except ValueError as e:
            if "must be between" in str(e):
                pytest.fail("Minimum length validation incorrect")

        # Exactly 5000 characters (maximum)
        valid_max = "A" * 5000
        # Should not raise length error
        try:
            set_user_prompt("user123", "sql", valid_max)
        except ValueError as e:
            if "must be between" in str(e):
                pytest.fail("Maximum length validation incorrect")
