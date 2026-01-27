"""
Unit tests for Vanna 2.x LLM providers

Tests:
- PostgreSQL connection pooling
- SQL runner functionality
- Multi-provider LLM service creation
- Agent creation and configuration
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from src.services.llm_providers import (
    PostgresConnectionPool,
    PostgresRunner,
    SnapAnalystUserResolver,
    _create_llm_service,
    get_shared_db_pool,
    shutdown_db_pool,
)

# =============================================================================
# PostgreSQL Connection Pool Tests
# =============================================================================


class TestPostgresConnectionPool:
    """Test PostgreSQL connection pool functionality."""

    @patch('src.services.llm_providers.pool.ThreadedConnectionPool')
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
            2, 20,
            host="localhost",
            dbname="testdb",
            user="testuser",
            password="testpass",
            port=5432,
            connect_timeout=10,
        )

    @patch('src.services.llm_providers.pool.ThreadedConnectionPool')
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

    @patch('src.services.llm_providers.pool.ThreadedConnectionPool')
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

    @patch('src.services.llm_providers.pool.ThreadedConnectionPool')
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

    @patch('src.services.llm_providers.pool.ThreadedConnectionPool')
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
        mock_cursor.execute.assert_called_once_with("SELECT 1")

    @patch('src.services.llm_providers.pool.ThreadedConnectionPool')
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
# PostgreSQL Runner Tests
# =============================================================================


class TestPostgresRunner:
    """Test PostgreSQL SQL runner."""

    def test_init(self):
        """Test runner initialization with pool."""
        mock_pool = MagicMock()
        runner = PostgresRunner(pool=mock_pool)

        assert runner.pool == mock_pool



# =============================================================================
# Shared Connection Pool Tests
# =============================================================================


class TestSharedConnectionPool:
    """Test shared connection pool singleton."""

    def teardown_method(self):
        """Clean up shared pool after each test."""
        import src.services.llm_providers
        src.services.llm_providers._db_pool = None

    @patch('src.services.llm_providers.PostgresConnectionPool')
    @patch('src.services.llm_providers.settings')
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

    @patch('src.services.llm_providers.PostgresConnectionPool')
    @patch('src.services.llm_providers.settings')
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

    @patch('src.services.llm_providers.PostgresConnectionPool')
    def test_shutdown_closes_pool(self, mock_pool_class):
        """Test shutdown_db_pool closes connections."""
        import src.services.llm_providers

        mock_pool = MagicMock()
        src.services.llm_providers._db_pool = mock_pool

        shutdown_db_pool()

        mock_pool.close_all.assert_called_once()
        assert src.services.llm_providers._db_pool is None


# =============================================================================
# User Resolver Tests
# =============================================================================


class TestSnapAnalystUserResolver:
    """Test user resolver functionality."""

    @pytest.mark.anyio
    async def test_resolve_user_with_header(self):
        """Test user resolution from request header."""
        resolver = SnapAnalystUserResolver()

        # Mock request context
        mock_context = MagicMock()
        mock_context.get_header.return_value = "john_doe"

        user = await resolver.resolve_user(mock_context)

        assert user.id == "john_doe"
        assert user.username == "john_doe"
        assert user.email == "john_doe@snapanalyst.local"
        assert "user" in user.group_memberships
        assert user.metadata["source"] == "snapanalyst"

    @pytest.mark.anyio
    async def test_resolve_user_default_guest(self):
        """Test default guest user when no header."""
        resolver = SnapAnalystUserResolver()

        mock_context = MagicMock()
        mock_context.get_header.return_value = None

        user = await resolver.resolve_user(mock_context)

        assert user.id == "guest"
        assert user.username == "guest"


# =============================================================================
# LLM Service Creation Tests
# =============================================================================


class TestCreateLLMService:
    """Test LLM service creation for different providers."""

    @patch('src.services.llm_providers.settings')
    def test_create_anthropic_service(self, mock_settings):
        """Test Anthropic LLM service creation."""
        mock_settings.anthropic_api_key = "sk-ant-test123"

        with patch('src.services.llm_providers.AnthropicLlmService') as mock_anthropic:
            mock_service = MagicMock()
            mock_anthropic.return_value = mock_service

            service = _create_llm_service("anthropic", "claude-sonnet-4-5")

            mock_anthropic.assert_called_once_with(
                model="claude-sonnet-4-5",
                api_key="sk-ant-test123"
            )
            assert service == mock_service

    @patch('src.services.llm_providers.settings')
    def test_create_openai_missing_key(self, mock_settings):
        """Test OpenAI raises error when API key missing."""
        mock_settings.openai_api_key = None

        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            _create_llm_service("openai", "gpt-4")

    @patch('src.services.llm_providers.settings')
    def test_create_anthropic_missing_key(self, mock_settings):
        """Test Anthropic raises error when API key missing."""
        mock_settings.anthropic_api_key = None

        with pytest.raises(ValueError, match="Anthropic API key not configured"):
            _create_llm_service("anthropic", "claude-sonnet-4-5")

    def test_create_unsupported_provider(self):
        """Test unsupported provider raises error."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            _create_llm_service("invalid_provider", "model")


# =============================================================================
# Agent Creation Tests
# =============================================================================


class TestCreateAgent:
    """Test Vanna agent creation."""

    @patch('src.services.llm_providers.settings')
    def test_create_agent_missing_api_key(self, mock_settings):
        """Test agent creation fails without API key."""
        mock_settings.llm_provider = "anthropic"
        mock_settings.sql_model = "claude-sonnet-4-5"
        mock_settings.anthropic_api_key = None

        with pytest.raises(ValueError, match="Anthropic API key not configured"):
            _create_llm_service("anthropic", "claude-sonnet-4-5")
