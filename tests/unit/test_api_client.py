"""
Unit tests for API Client

Tests HTTP client functions for backend communication.
"""
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from src.clients.api_client import (
    APIError,
    call_api,
    check_api_health,
    check_database_health,
    check_llm_health,
    get_api_prefix,
    stream_from_api,
    upload_file,
)


class TestAPIError:
    """Test APIError exception class"""

    def test_init_with_defaults(self):
        """Test APIError initialization with defaults"""
        error = APIError("Something went wrong")

        assert error.message == "Something went wrong"
        assert error.status_code == 400
        assert str(error) == "Something went wrong"

    def test_init_with_custom_status(self):
        """Test APIError initialization with custom status code"""
        error = APIError("Not found", 404)

        assert error.message == "Not found"
        assert error.status_code == 404

    def test_is_exception_subclass(self):
        """Test that APIError is an Exception subclass"""
        error = APIError("Test")
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test that APIError can be raised and caught"""
        with pytest.raises(APIError) as exc_info:
            raise APIError("Test error", 500)

        assert exc_info.value.message == "Test error"
        assert exc_info.value.status_code == 500


class TestGetAPIHelpers:
    """Test API helper functions"""

    @patch.dict('os.environ', {'API_BASE_URL': 'http://custom:9000'})
    def test_get_api_base_url_custom(self):
        """Test getting custom API base URL from environment"""
        # Need to reload module to pick up env var change
        from importlib import reload

        import src.clients.api_client as client_module
        reload(client_module)

        assert client_module.get_api_base_url() == "http://custom:9000"

    def test_get_api_prefix(self):
        """Test getting API prefix"""
        result = get_api_prefix()
        assert result == "/api/v1"

    @patch.dict('os.environ', {'API_EXTERNAL_URL': 'https://example.com'})
    def test_get_api_external_url_custom(self):
        """Test getting custom external URL"""
        from importlib import reload

        import src.clients.api_client as client_module
        reload(client_module)

        result = client_module.get_api_external_url()
        assert result == "https://example.com"

    @patch.dict('os.environ', {'API_EXTERNAL_URL': 'relative'})
    def test_get_api_external_url_relative(self):
        """Test getting relative external URL"""
        from importlib import reload

        import src.clients.api_client as client_module
        reload(client_module)

        result = client_module.get_api_external_url()
        assert result == ""

    @patch.dict('os.environ', {'API_EXTERNAL_URL': ''})
    def test_get_api_external_url_empty(self):
        """Test getting empty external URL"""
        from importlib import reload

        import src.clients.api_client as client_module
        reload(client_module)

        result = client_module.get_api_external_url()
        assert result == ""


class TestCallAPI:
    """Test call_api function"""

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_call_api_get_success(self, mock_client_cls):
        """Test successful GET request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await call_api("/test/endpoint", method="GET")

        assert result == {"result": "success"}
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_call_api_post_success(self, mock_client_cls):
        """Test successful POST request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"created": True}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await call_api(
            "/test/endpoint",
            method="POST",
            data={"name": "test"}
        )

        assert result == {"created": True}
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_call_api_delete_success(self, mock_client_cls):
        """Test successful DELETE request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"deleted": True}

        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await call_api("/test/endpoint", method="DELETE")

        assert result == {"deleted": True}
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_api_unsupported_method(self):
        """Test unsupported HTTP method raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            await call_api("/test", method="PATCH")

        assert "Unsupported method" in str(exc_info.value)


    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_call_api_custom_timeout(self, mock_client_cls):
        """Test call_api with custom timeout"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        await call_api("/test", timeout=60.0)

        # Verify client was created with custom timeout
        mock_client_cls.assert_called_once_with(timeout=60.0)


class TestCheckAPIHealth:
    """Test check_api_health function"""

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_api_health_success(self, mock_client_cls):
        """Test successful API health check"""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "healthy", "version": "0.1.0"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_healthy, version = await check_api_health()

        assert is_healthy is True
        assert version == "0.1.0"

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_api_health_no_version(self, mock_client_cls):
        """Test health check without version in response"""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "healthy"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_healthy, version = await check_api_health()

        assert is_healthy is True
        assert version == "unknown"

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_api_health_connection_error(self, mock_client_cls):
        """Test health check with connection error"""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_healthy, version = await check_api_health()

        assert is_healthy is False
        assert version == "unknown"


class TestCheckDatabaseHealth:
    """Test check_database_health function"""

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_database_health_connected(self, mock_client_cls):
        """Test database health check when connected"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "database": {"connected": True, "name": "test_db"}
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_connected, db_name = await check_database_health()

        assert is_connected is True
        assert db_name == "test_db"

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_database_health_disconnected(self, mock_client_cls):
        """Test database health check when disconnected"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "database": {"connected": False}
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_connected, db_name = await check_database_health()

        assert is_connected is False
        assert db_name == "unknown"

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_database_health_default_name(self, mock_client_cls):
        """Test database health check with missing name"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "database": {"connected": True}
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_connected, db_name = await check_database_health()

        assert is_connected is True
        assert db_name == "snapanalyst_db"

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_database_health_error(self, mock_client_cls):
        """Test database health check with error"""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Network error")
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_connected, db_name = await check_database_health()

        assert is_connected is False
        assert db_name == "unknown"


class TestCheckLLMHealth:
    """Test check_llm_health function"""

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_llm_health_healthy(self, mock_client_cls):
        """Test LLM health check when healthy"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "healthy": True,
            "provider": "OpenAI",
            "status": "ok"
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_healthy, provider = await check_llm_health()

        assert is_healthy is True
        assert provider == "OpenAI"

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_llm_health_not_configured(self, mock_client_cls):
        """Test LLM health check when not configured"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "healthy": False,
            "provider": "OpenAI",
            "status": "not_configured"
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_healthy, provider = await check_llm_health()

        assert is_healthy is False
        assert "not configured" in provider

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_llm_health_not_reachable(self, mock_client_cls):
        """Test LLM health check when not reachable"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "healthy": False,
            "provider": "Ollama",
            "status": "not_reachable"
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_healthy, provider = await check_llm_health()

        assert is_healthy is False
        assert "not reachable" in provider

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_llm_health_model_not_found(self, mock_client_cls):
        """Test LLM health check when model not found"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "healthy": False,
            "provider": "Ollama",
            "status": "model_not_found"
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_healthy, provider = await check_llm_health()

        assert is_healthy is False
        assert "model not found" in provider

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_llm_health_connection_failed(self, mock_client_cls):
        """Test LLM health check with connection failure"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "healthy": False,
            "provider": "Anthropic",
            "status": "connection_failed"
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_healthy, provider = await check_llm_health()

        assert is_healthy is False
        assert "connection failed" in provider

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_llm_health_unknown_status(self, mock_client_cls):
        """Test LLM health check with unknown status"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "healthy": False,
            "provider": "TestProvider",
            "status": "weird_error"
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_healthy, provider = await check_llm_health()

        assert is_healthy is False
        assert "weird_error" in provider

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_llm_health_network_error(self, mock_client_cls):
        """Test LLM health check with network error"""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Network down")
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        is_healthy, provider = await check_llm_health()

        assert is_healthy is False
        assert "API error" in provider


class TestUploadFile:
    """Test upload_file function"""

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    @patch('builtins.open', create=True)
    async def test_upload_file_success(self, mock_open, mock_client_cls):
        """Test successful file upload"""
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        mock_response = Mock()
        mock_response.json.return_value = {"file_id": "123", "status": "uploaded"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await upload_file("/path/to/file.csv", "test.csv")

        assert result == {"file_id": "123", "status": "uploaded"}
        mock_open.assert_called_once_with("/path/to/file.csv", 'rb')
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    @patch('builtins.open', create=True)
    async def test_upload_file_http_error(self, mock_open, mock_client_cls):
        """Test file upload with HTTP error"""
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Upload failed", request=Mock(), response=Mock()
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await upload_file("/path/to/file.csv", "test.csv")


class TestStreamFromAPI:
    """Test stream_from_api function"""

    @pytest.mark.asyncio
    @patch('src.clients.api_client.httpx.AsyncClient')
    async def test_stream_from_api_success(self, mock_client_cls):
        """Test successful SSE streaming"""
        lines = [
            "event: start",
            "data: {\"message\": \"Starting\"}",
            "",
            "event: progress",
            "data: {\"percent\": 50}",
            "",
            "data: {\"done\": true}",
            ""
        ]

        async def mock_aiter_lines():
            for line in lines:
                yield line

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        # Create async context manager for stream
        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.stream = Mock(return_value=mock_stream)  # Regular Mock to avoid coroutine
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        events = []
        async for event in stream_from_api("/test/stream", data={"query": "test"}):
            events.append(event)

        assert len(events) == 3
        assert events[0]["event"] == "start"
        assert events[0]["data"]["message"] == "Starting"
        assert events[1]["event"] == "progress"
        assert events[1]["data"]["percent"] == 50
        assert events[2]["event"] == "message"  # Default event type
        assert events[2]["data"]["done"] is True

    @pytest.mark.asyncio
    @patch('src.clients.api_client.httpx.AsyncClient')
    async def test_stream_from_api_with_comments(self, mock_client_cls):
        """Test SSE streaming with comment lines"""
        lines = [
            ": keepalive",
            "data: {\"test\": \"value\"}",
            "",
            ": another comment",
            ""
        ]

        async def mock_aiter_lines():
            for line in lines:
                yield line

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        # Create async context manager for stream
        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.stream = Mock(return_value=mock_stream)  # Regular Mock to avoid coroutine
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        events = []
        async for event in stream_from_api("/test/stream"):
            events.append(event)

        # Comments should be ignored
        assert len(events) == 1
        assert events[0]["data"]["test"] == "value"

    @pytest.mark.asyncio
    @patch('src.clients.api_client.httpx.AsyncClient')
    async def test_stream_from_api_malformed_json(self, mock_client_cls):
        """Test SSE streaming with malformed JSON"""
        lines = [
            "data: not valid json",
            ""
        ]

        async def mock_aiter_lines():
            for line in lines:
                yield line

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        # Create async context manager for stream
        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.stream = Mock(return_value=mock_stream)  # Regular Mock to avoid coroutine
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        events = []
        async for event in stream_from_api("/test/stream"):
            events.append(event)

        # Should return raw data when JSON parsing fails
        assert len(events) == 1
        assert events[0]["data"]["raw"] == "not valid json"

