"""
Unit tests for Vanna 0.x LLM providers

Tests:
- PostgreSQL connection pooling
- Shared connection pool singleton
- initialize_vanna() initialization function
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from src.services.llm_providers import (
    PostgresConnectionPool,
    get_shared_db_pool,
    shutdown_db_pool,
)

# =============================================================================
# PostgreSQL Connection Pool Tests
# =============================================================================


class TestPostgresConnectionPool:
    """Test PostgreSQL connection pool functionality."""

    @patch("src.services.llm_providers.pool.ThreadedConnectionPool")
    def test_init_creates_pool(self, mock_pool_class):
        """Test pool initialization with correct parameters."""
        PostgresConnectionPool(
            host="localhost",
            dbname="testdb",
            user="testuser",
            password="testpass",
            port=5432,
            minconn=2,
            maxconn=20,
        )

        # Verify pool created with correct args
        mock_pool_class.assert_called_once_with(
            2,
            20,
            host="localhost",
            dbname="testdb",
            user="testuser",
            password="testpass",
            port=5432,
            connect_timeout=10,
        )

    @patch("src.services.llm_providers.pool.ThreadedConnectionPool")
    def test_get_connection_context_manager(self, mock_pool_class):
        """Test connection context manager returns and releases connection."""
        # Setup mock pool
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool

        pool = PostgresConnectionPool(
            host="localhost",
            dbname="testdb",
            user="testuser",
            password="testpass",
        )

        # Use context manager
        with pool.get_connection() as conn:
            assert conn == mock_conn

        # Verify connection was returned to pool
        mock_pool.getconn.assert_called_once()
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("src.services.llm_providers.pool.ThreadedConnectionPool")
    def test_get_connection_releases_on_error(self, mock_pool_class):
        """Test connection is released even if error occurs."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool

        pool = PostgresConnectionPool(
            host="localhost",
            dbname="testdb",
            user="testuser",
            password="testpass",
        )

        # Simulate error in context
        with pytest.raises(ValueError), pool.get_connection():
            raise ValueError("Test error")

        # Connection still returned to pool
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("src.services.llm_providers.pool.ThreadedConnectionPool")
    def test_close_all(self, mock_pool_class):
        """Test closing all connections."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        pool = PostgresConnectionPool(
            host="localhost",
            dbname="testdb",
            user="testuser",
            password="testpass",
        )

        pool.close_all()

        mock_pool.closeall.assert_called_once()

    @patch("src.services.llm_providers.pool.ThreadedConnectionPool")
    def test_health_check_healthy(self, mock_pool_class):
        """Test health check returns healthy when connection works."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_pool.getconn.return_value = mock_conn
        mock_pool.minconn = 2
        mock_pool.maxconn = 20
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool_class.return_value = mock_pool

        pool = PostgresConnectionPool(
            host="localhost",
            dbname="testdb",
            user="testuser",
            password="testpass",
        )

        health = pool.health_check()

        assert health["healthy"] is True
        assert health["connections"]["min"] == 2
        assert health["connections"]["max"] == 20
        # SELECT 1 called twice: once by pre-ping in get_connection(), once by health_check()
        assert mock_cursor.execute.call_count == 2
        mock_cursor.execute.assert_called_with("SELECT 1")

    @patch("src.services.llm_providers.pool.ThreadedConnectionPool")
    def test_health_check_unhealthy(self, mock_pool_class):
        """Test health check returns unhealthy when connection fails."""
        mock_pool = MagicMock()
        mock_pool.getconn.side_effect = psycopg2.OperationalError("Connection failed")
        mock_pool_class.return_value = mock_pool

        pool = PostgresConnectionPool(
            host="localhost",
            dbname="testdb",
            user="testuser",
            password="testpass",
        )

        health = pool.health_check()

        assert health["healthy"] is False
        assert "error" in health


# =============================================================================
# Shared Connection Pool Tests
# =============================================================================


class TestSharedConnectionPool:
    """Test shared connection pool singleton."""

    def teardown_method(self):
        """Clean up shared pool after each test."""
        import src.services.llm_providers

        src.services.llm_providers._db_pool = None

    @patch("src.services.llm_providers.PostgresConnectionPool")
    @patch("src.services.llm_providers.settings")
    def test_get_shared_pool_creates_once(self, mock_settings, mock_pool_class):
        """Test shared pool is created only once (singleton)."""
        # Configure mock settings
        mock_settings.database_url = "postgresql://user:pass@localhost:5432/testdb"

        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        # Get pool twice
        pool1 = get_shared_db_pool()
        pool2 = get_shared_db_pool()

        # Should be same instance
        assert pool1 is pool2

        # Pool created only once
        assert mock_pool_class.call_count == 1

    @patch("src.services.llm_providers.PostgresConnectionPool")
    @patch("src.services.llm_providers.settings")
    def test_get_shared_pool_parses_url(self, mock_settings, mock_pool_class):
        """Test database URL is correctly parsed."""
        mock_settings.database_url = "postgresql://myuser:mypass@dbhost:5555/mydb"

        get_shared_db_pool()

        # Verify PostgresConnectionPool called with parsed values
        call_args = mock_pool_class.call_args
        assert call_args[1]["host"] == "dbhost"
        assert call_args[1]["dbname"] == "mydb"
        assert call_args[1]["user"] == "myuser"
        assert call_args[1]["password"] == "mypass"
        assert call_args[1]["port"] == 5555
        assert call_args[1]["minconn"] == 2
        assert call_args[1]["maxconn"] == 20

    @patch("src.services.llm_providers.PostgresConnectionPool")
    def test_shutdown_closes_pool(self, mock_pool_class):
        """Test shutdown_db_pool closes connections."""
        import src.services.llm_providers

        mock_pool = MagicMock()
        src.services.llm_providers._db_pool = mock_pool

        shutdown_db_pool()

        mock_pool.close_all.assert_called_once()
        assert src.services.llm_providers._db_pool is None


# =============================================================================
# initialize_vanna Tests
# =============================================================================


class TestInitializeVanna:
    """Test the initialize_vanna() function."""

    @patch("src.services.llm_providers.train_vanna_with_ddl")
    @patch("src.services.llm_providers._get_vanna_instance")
    def test_initialize_vanna_calls_instance_and_train(self, mock_get_instance, mock_train):
        """Test that initialize_vanna creates instance and trains."""
        from src.services.llm_providers import initialize_vanna

        mock_vn = MagicMock()
        mock_get_instance.return_value = mock_vn

        result = initialize_vanna()

        mock_get_instance.assert_called_once()
        mock_train.assert_called_once()
        assert result == mock_vn
