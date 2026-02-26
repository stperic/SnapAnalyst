"""
Unit tests for Database Engine and Session Management

Tests engine creation, session management, and database operations.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.database.engine import (
    _create_engine,
    get_active_engine,
    get_db,
    get_db_context,
    get_engine_for_dataset,
    get_session_for_dataset,
)


class TestCreateEngine:
    """Test engine creation"""

    @patch("src.database.engine.create_engine")
    @patch("src.database.engine.settings")
    def test_create_engine_with_connect_args(self, mock_settings, mock_create_engine):
        """Test engine creation with connection arguments"""
        # Mock settings
        mock_settings.database_url = "postgresql://localhost/test"
        mock_settings.database_pool_size = 5
        mock_settings.database_max_overflow = 10
        mock_settings.database_pool_timeout = 30
        mock_settings.database_pool_recycle = 3600
        mock_settings.debug = False

        # Call _create_engine
        _create_engine()

        # Verify create_engine was called with connect_args
        call_kwargs = mock_create_engine.call_args[1]
        assert "connect_args" in call_kwargs
        assert call_kwargs["connect_args"]["options"] == "-c search_path=public,app"


class TestGetEngineForDataset:
    """Test dataset-specific engine retrieval"""

    def test_get_engine_returns_cached(self):
        """Test returns cached engine for same dataset"""
        from src.database.engine import _dataset_engines

        # Clear cache first
        _dataset_engines.clear()

        # Get engine twice for same dataset
        engine1 = get_engine_for_dataset("snap")
        engine2 = get_engine_for_dataset("snap")

        # Should return same cached instance
        assert engine1 is engine2
        assert "snap" in _dataset_engines

    def test_get_engine_for_new_dataset(self):
        """Test engine creation for new dataset"""
        from src.database.engine import _dataset_engines

        # Clear cache
        _dataset_engines.clear()

        # Get engine for new dataset
        engine = get_engine_for_dataset("new_dataset")

        assert engine is not None
        assert "new_dataset" in _dataset_engines


class TestGetActiveEngine:
    """Test active engine retrieval"""

    @patch("src.database.engine.settings")
    @patch("src.database.engine.get_engine_for_dataset")
    def test_get_active_engine(self, mock_get_engine, mock_settings):
        """Test getting engine for active dataset"""
        mock_settings.active_dataset = "snap"
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        result = get_active_engine()

        mock_get_engine.assert_called_once_with("snap")
        assert result is mock_engine


class TestGetSessionForDataset:
    """Test dataset session factory"""

    @patch("src.database.engine.get_engine_for_dataset")
    def test_get_session_for_dataset(self, mock_get_engine):
        """Test getting session factory for dataset"""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        session_factory = get_session_for_dataset("test_dataset")

        mock_get_engine.assert_called_once_with("test_dataset")
        assert session_factory is not None


class TestGetDb:
    """Test get_db dependency"""

    def test_get_db_generator(self):
        """Test get_db yields and closes session"""
        sessions = list(get_db())

        # Should yield exactly one session
        assert len(sessions) == 1
        assert isinstance(sessions[0], Session)

        # Session should be closed after generator exits
        # (We can't easily test this without mocking SessionLocal)

    @patch("src.database.engine.SessionLocal")
    def test_get_db_closes_on_exit(self, mock_session_local):
        """Test get_db closes session on exit"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Consume generator
        for _ in get_db():
            pass

        # Verify session was closed
        mock_session.close.assert_called_once()


class TestGetDbContext:
    """Test get_db_context context manager"""

    @patch("src.database.engine.SessionLocal")
    def test_get_db_context_success(self, mock_session_local):
        """Test successful database operation"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        with get_db_context() as db:
            assert db is mock_session

        # Should commit and close
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("src.database.engine.SessionLocal")
    def test_get_db_context_exception(self, mock_session_local):
        """Test database operation with exception"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        with pytest.raises(ValueError), get_db_context() as db:
            raise ValueError("Test error")

        # Should rollback and close
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.commit.assert_not_called()


class TestDatabaseInitialization:
    """Test database initialization functions"""

    @patch("src.database.engine.Base")
    @patch("src.database.engine.engine")
    def test_init_db(self, mock_engine, mock_base):
        """Test database initialization"""
        from src.database.engine import init_db

        init_db()

        # Should create all tables
        mock_base.metadata.create_all.assert_called_once_with(bind=mock_engine)

    @patch("src.database.engine.Base")
    @patch("src.database.engine.engine")
    def test_drop_all_tables(self, mock_engine, mock_base):
        """Test dropping all tables"""
        from src.database.engine import drop_all_tables

        drop_all_tables()

        # Should drop all tables
        mock_base.metadata.drop_all.assert_called_once_with(bind=mock_engine)


class TestEngineCaching:
    """Test engine caching behavior"""

    def test_multiple_datasets_cached_separately(self):
        """Test different datasets get separate cached engines"""
        from src.database.engine import _dataset_engines

        # Clear cache
        _dataset_engines.clear()

        # Get engines for different datasets
        engine1 = get_engine_for_dataset("dataset1")
        engine2 = get_engine_for_dataset("dataset2")
        engine3 = get_engine_for_dataset("dataset1")  # Should use cache

        # Different datasets should have different engines
        assert engine1 is not engine2

        # Same dataset should return cached engine
        assert engine1 is engine3

        # Both should be in cache
        assert "dataset1" in _dataset_engines
        assert "dataset2" in _dataset_engines

    def test_get_engine_for_dataset_import_error(self):
        """Test get_engine_for_dataset handles ImportError gracefully"""
        import sys

        from src.database.engine import _dataset_engines

        # Clear cache
        _dataset_engines.clear()

        # Temporarily hide the datasets module
        datasets_module = sys.modules.get("datasets")
        if "datasets" in sys.modules:
            del sys.modules["datasets"]

        try:
            # Should fall back to public schema when datasets module not available
            engine = get_engine_for_dataset("test_dataset_no_datasets_module")

            assert engine is not None
            assert "test_dataset_no_datasets_module" in _dataset_engines
        finally:
            # Restore datasets module if it was there
            if datasets_module is not None:
                sys.modules["datasets"] = datasets_module
