"""
Unit tests for Logging Configuration

Tests logging setup, file rotation, and logger configuration.
"""
import logging
from unittest.mock import Mock, patch

from src.core.logging import (
    create_rotating_file_handler,
    get_llm_logger,
    get_logger,
    setup_api_logging,
    setup_llm_logging,
    setup_logging,
)


class TestCreateRotatingFileHandler:
    """Test create_rotating_file_handler function"""

    @patch('src.core.logging.RotatingFileHandler')
    @patch('src.core.logging.Path')
    def test_create_rotating_file_handler_defaults(self, mock_path, mock_handler_cls):
        """Test creating handler with default settings"""
        mock_path.return_value.parent.mkdir = Mock()
        mock_handler = Mock()
        mock_handler_cls.return_value = mock_handler

        handler = create_rotating_file_handler("./logs/test.log")

        assert handler == mock_handler
        mock_handler.setFormatter.assert_called_once()
        mock_handler.setLevel.assert_called_once_with(logging.DEBUG)

    @patch('src.core.logging.RotatingFileHandler')
    @patch('src.core.logging.Path')
    def test_create_rotating_file_handler_custom_size(self, mock_path, mock_handler_cls):
        """Test creating handler with custom size"""
        mock_path.return_value.parent.mkdir = Mock()
        mock_handler = Mock()
        mock_handler_cls.return_value = mock_handler

        handler = create_rotating_file_handler(
            "./logs/test.log",
            max_bytes=5000000,
            backup_count=3
        )

        assert handler == mock_handler
        # Verify RotatingFileHandler was called with custom values
        call_kwargs = mock_handler_cls.call_args[1]
        assert call_kwargs['maxBytes'] == 5000000
        assert call_kwargs['backupCount'] == 3

    @patch('src.core.logging.RotatingFileHandler')
    @patch('src.core.logging.Path')
    def test_create_rotating_file_handler_creates_directory(self, mock_path, mock_handler_cls):
        """Test that handler creates log directory if missing"""
        mock_log_file = Mock()
        mock_parent = Mock()
        mock_log_file.parent = mock_parent
        mock_path.return_value = mock_log_file

        mock_handler = Mock()
        mock_handler_cls.return_value = mock_handler

        create_rotating_file_handler("./logs/subdir/test.log")

        # Should create parent directory
        mock_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch('src.core.logging.RotatingFileHandler')
    @patch('src.core.logging.Path')
    def test_create_rotating_file_handler_custom_level(self, mock_path, mock_handler_cls):
        """Test creating handler with custom log level"""
        mock_path.return_value.parent.mkdir = Mock()
        mock_handler = Mock()
        mock_handler_cls.return_value = mock_handler

        create_rotating_file_handler("./logs/test.log", level=logging.WARNING)

        mock_handler.setLevel.assert_called_once_with(logging.WARNING)


class TestSetupLogging:
    """Test setup_logging function"""

    @patch('logging.basicConfig')
    @patch('logging.getLogger')
    def test_setup_logging_basic(self, mock_get_logger, mock_basic_config):
        """Test basic logging setup without file output"""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.log_level = "INFO"
            mock_settings.log_to_file = False

            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Should configure basicConfig
            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs['level'] == logging.INFO

    @patch('logging.basicConfig')
    @patch('logging.getLogger')
    @patch('src.core.logging.create_rotating_file_handler')
    def test_setup_logging_with_file(self, mock_create_handler, mock_get_logger, mock_basic_config):
        """Test logging setup with file output"""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.log_level = "DEBUG"
            mock_settings.log_to_file = True
            mock_settings.log_file_path = "./logs/app.log"
            mock_settings.log_max_bytes = 10000000
            mock_settings.log_backup_count = 5

            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            mock_file_handler = Mock()
            mock_create_handler.return_value = mock_file_handler

            setup_logging()

            # Should create and add file handler
            mock_create_handler.assert_called_once()
            mock_logger.addHandler.assert_called_once_with(mock_file_handler)

    @patch('logging.basicConfig')
    @patch('logging.getLogger')
    def test_setup_logging_custom_level(self, mock_get_logger, mock_basic_config):
        """Test logging setup with custom log level"""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.log_to_file = False
            mock_settings.log_level = "INFO"

            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            setup_logging(log_level="ERROR")

            # Should use custom level, not settings level
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs['level'] == logging.ERROR

    @patch('logging.basicConfig')
    @patch('logging.getLogger')
    def test_setup_logging_suppresses_noisy_loggers(self, mock_get_logger, mock_basic_config):
        """Test that setup_logging suppresses noisy library loggers"""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.log_level = "DEBUG"
            mock_settings.log_to_file = False
            mock_settings.log_max_bytes = 10000000
            mock_settings.log_backup_count = 5

            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Should have called getLogger for noisy libraries
            assert mock_get_logger.call_count >= 10  # Many noisy loggers


class TestSetupAPILogging:
    """Test setup_api_logging function"""

    @patch('logging.getLogger')
    @patch('src.core.logging.create_rotating_file_handler')
    def test_setup_api_logging(self, mock_create_handler, mock_get_logger):
        """Test setting up API logger"""
        mock_logger = Mock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger

        mock_handler = Mock()
        mock_create_handler.return_value = mock_handler

        logger = setup_api_logging("./logs/custom_api.log")

        assert logger == mock_logger
        mock_logger.setLevel.assert_called_once_with(logging.INFO)
        mock_logger.addHandler.assert_called_once_with(mock_handler)
        mock_create_handler.assert_called_once_with("./logs/custom_api.log")

    @patch('logging.getLogger')
    @patch('src.core.logging.create_rotating_file_handler')
    def test_setup_api_logging_avoids_duplicate_handlers(self, mock_create_handler, mock_get_logger):
        """Test that setup_api_logging doesn't add duplicate handlers"""
        from logging.handlers import RotatingFileHandler

        mock_logger = Mock()
        # Create actual RotatingFileHandler instance for isinstance check
        mock_existing_handler = Mock(spec=RotatingFileHandler)
        mock_logger.handlers = [mock_existing_handler]
        mock_get_logger.return_value = mock_logger

        logger = setup_api_logging()

        # Should not add another handler or call create_rotating_file_handler
        mock_logger.addHandler.assert_not_called()
        mock_create_handler.assert_not_called()

    @patch('logging.getLogger')
    @patch('src.core.logging.create_rotating_file_handler')
    def test_setup_api_logging_default_path(self, mock_create_handler, mock_get_logger):
        """Test API logging with default path"""
        mock_logger = Mock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger

        mock_handler = Mock()
        mock_create_handler.return_value = mock_handler

        setup_api_logging()

        # Should use default path
        mock_create_handler.assert_called_once_with("./logs/api.log")


class TestSetupLLMLogging:
    """Test setup_llm_logging function"""

    @patch('logging.getLogger')
    @patch('src.core.logging.create_rotating_file_handler')
    def test_setup_llm_logging(self, mock_create_handler, mock_get_logger):
        """Test setting up LLM logger"""
        mock_logger = Mock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger

        mock_handler = Mock()
        mock_create_handler.return_value = mock_handler

        logger = setup_llm_logging("./logs/custom_llm.log")

        assert logger == mock_logger
        mock_logger.setLevel.assert_called_once_with(logging.INFO)
        mock_logger.addHandler.assert_called_once_with(mock_handler)
        mock_create_handler.assert_called_once()

    @patch('logging.getLogger')
    def test_setup_llm_logging_avoids_duplicate_handlers(self, mock_get_logger):
        """Test that setup_llm_logging doesn't add duplicate handlers"""
        from logging.handlers import RotatingFileHandler

        mock_logger = Mock()
        # Add actual RotatingFileHandler instance
        mock_existing_handler = Mock(spec=RotatingFileHandler)
        mock_logger.handlers = [mock_existing_handler]
        mock_get_logger.return_value = mock_logger

        logger = setup_llm_logging()

        # Should not add another handler
        mock_logger.addHandler.assert_not_called()

    @patch('logging.getLogger')
    @patch('src.core.logging.create_rotating_file_handler')
    def test_setup_llm_logging_default_path(self, mock_create_handler, mock_get_logger):
        """Test LLM logging with default path"""
        mock_logger = Mock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger

        mock_handler = Mock()
        mock_create_handler.return_value = mock_handler

        setup_llm_logging()

        # Should use default path
        mock_create_handler.assert_called_once_with("./logs/llm.log", level=logging.INFO)


class TestGetLLMLogger:
    """Test get_llm_logger function"""

    @patch('logging.getLogger')
    @patch('src.core.logging.setup_llm_logging')
    def test_get_llm_logger_initializes_if_no_handlers(self, mock_setup, mock_get_logger):
        """Test get_llm_logger initializes logger if no handlers"""
        mock_logger = Mock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger

        logger = get_llm_logger()

        # Should call setup_llm_logging to initialize
        mock_setup.assert_called_once()
        assert logger == mock_logger

    @patch('logging.getLogger')
    def test_get_llm_logger_skips_init_if_handlers_exist(self, mock_get_logger):
        """Test get_llm_logger doesn't reinitialize if handlers exist"""
        mock_logger = Mock()
        mock_logger.handlers = [Mock()]  # Has existing handler
        mock_get_logger.return_value = mock_logger

        with patch('src.core.logging.setup_llm_logging') as mock_setup:
            logger = get_llm_logger()

            # Should NOT call setup_llm_logging
            mock_setup.assert_not_called()
            assert logger == mock_logger


class TestGetLogger:
    """Test get_logger function"""

    @patch('logging.getLogger')
    def test_get_logger(self, mock_get_logger):
        """Test get_logger returns logger for module"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        logger = get_logger("test_module")

        mock_get_logger.assert_called_once_with("test_module")
        assert logger == mock_logger

    @patch('logging.getLogger')
    def test_get_logger_with_package_name(self, mock_get_logger):
        """Test get_logger with package name"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        logger = get_logger("src.core.config")

        mock_get_logger.assert_called_once_with("src.core.config")
        assert logger == mock_logger
