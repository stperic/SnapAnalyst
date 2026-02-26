"""
Unit tests for ETL Loader

Tests ETL orchestration and status tracking.
"""

from unittest.mock import Mock, patch

import pytest

from src.etl.loader import ETLStatus, check_references_ready


class TestCheckReferencesReady:
    """Test check_references_ready function"""

    @patch("src.database.init_database.check_references_populated")
    def test_references_ready(self, mock_check):
        """Test when references are populated"""
        mock_check.return_value = (True, [])

        ready, empty = check_references_ready()

        assert ready is True
        assert empty == []

    @patch("src.database.init_database.check_references_populated")
    def test_references_not_ready(self, mock_check):
        """Test when references are not populated"""
        mock_check.return_value = (False, ["ref_status", "ref_element"])

        ready, empty = check_references_ready()

        assert ready is False
        assert len(empty) == 2
        assert "ref_status" in empty
        assert "ref_element" in empty

    @patch("src.database.init_database.check_references_populated")
    def test_check_fails_gracefully(self, mock_check):
        """Test graceful failure when check raises exception"""
        mock_check.side_effect = Exception("Database error")

        ready, empty = check_references_ready()

        # Should assume OK if check fails
        assert ready is True
        assert empty == []


class TestETLStatus:
    """Test ETLStatus class"""

    def test_init(self):
        """Test ETLStatus initialization"""
        status = ETLStatus(job_id="test-job-123")

        assert status.job_id == "test-job-123"
        assert status.status == "pending"
        assert status.started_at is None
        assert status.completed_at is None
        assert status.error_message is None
        assert status.total_rows == 0
        assert status.rows_processed == 0
        assert status.rows_skipped == 0
        assert status.households_created == 0
        assert status.members_created == 0
        assert status.errors_created == 0
        assert status.validation_errors == []
        assert status.validation_warnings == []

    def test_to_dict_pending(self):
        """Test to_dict with pending status"""
        status = ETLStatus(job_id="test-123")

        result = status.to_dict()

        assert result["job_id"] == "test-123"
        assert result["status"] == "pending"
        assert result["started_at"] is None
        assert result["completed_at"] is None
        assert result["progress"]["total_rows"] == 0
        assert result["progress"]["rows_processed"] == 0
        assert result["progress"]["rows_skipped"] == 0
        assert result["progress"]["rows_successful"] == 0
        assert result["progress"]["percent_complete"] == 0
        assert result["validation"]["errors_count"] == 0
        assert result["validation"]["warnings_count"] == 0

    def test_to_dict_with_progress(self):
        """Test to_dict with progress"""
        from datetime import datetime

        status = ETLStatus(job_id="test-123")
        status.status = "in_progress"
        status.started_at = datetime(2023, 1, 1, 12, 0, 0)
        status.total_rows = 1000
        status.rows_processed = 500
        status.rows_skipped = 50
        status.households_created = 400
        status.members_created = 1200
        status.errors_created = 150

        result = status.to_dict()

        assert result["status"] == "in_progress"
        assert result["started_at"] == "2023-01-01T12:00:00"
        assert result["progress"]["total_rows"] == 1000
        assert result["progress"]["rows_processed"] == 500
        assert result["progress"]["rows_skipped"] == 50
        assert result["progress"]["rows_successful"] == 450  # 500 - 50
        assert result["progress"]["percent_complete"] == 50  # 500/1000 * 100
        assert result["progress"]["households_created"] == 400
        assert result["progress"]["members_created"] == 1200
        assert result["progress"]["errors_created"] == 150

    def test_to_dict_completed(self):
        """Test to_dict with completed status"""
        from datetime import datetime

        status = ETLStatus(job_id="test-123")
        status.status = "completed"
        status.started_at = datetime(2023, 1, 1, 12, 0, 0)
        status.completed_at = datetime(2023, 1, 1, 12, 30, 0)
        status.total_rows = 100
        status.rows_processed = 100

        result = status.to_dict()

        assert result["status"] == "completed"
        assert result["completed_at"] == "2023-01-01T12:30:00"
        assert result["progress"]["percent_complete"] == 100

    def test_to_dict_with_error(self):
        """Test to_dict with error status"""
        status = ETLStatus(job_id="test-123")
        status.status = "failed"
        status.error_message = "Database connection lost"

        result = status.to_dict()

        assert result["status"] == "failed"
        assert result["error_message"] == "Database connection lost"

    def test_to_dict_with_validation_issues(self):
        """Test to_dict with validation errors and warnings"""
        status = ETLStatus(job_id="test-123")
        status.validation_errors = ["Error 1", "Error 2", "Error 3"]
        status.validation_warnings = ["Warning 1"]

        result = status.to_dict()

        assert result["validation"]["errors_count"] == 3
        assert result["validation"]["warnings_count"] == 1

    def test_percent_complete_zero_total(self):
        """Test percent complete when total_rows is 0"""
        status = ETLStatus(job_id="test-123")
        status.total_rows = 0
        status.rows_processed = 0

        result = status.to_dict()

        # Should not divide by zero
        assert result["progress"]["percent_complete"] == 0

    def test_rows_successful_calculation(self):
        """Test rows_successful calculated field"""
        status = ETLStatus(job_id="test-123")
        status.rows_processed = 100
        status.rows_skipped = 25

        result = status.to_dict()

        assert result["progress"]["rows_successful"] == 75

    def test_all_status_values(self):
        """Test all possible status values"""
        for status_value in ["pending", "in_progress", "completed", "failed"]:
            status = ETLStatus(job_id="test")
            status.status = status_value

            result = status.to_dict()
            assert result["status"] == status_value

    def test_progress_tracking_fields(self):
        """Test all progress tracking fields"""
        status = ETLStatus(job_id="test")
        status.total_rows = 1000
        status.rows_processed = 800
        status.rows_skipped = 50
        status.households_created = 700
        status.members_created = 2100
        status.errors_created = 350

        result = status.to_dict()
        progress = result["progress"]

        assert progress["total_rows"] == 1000
        assert progress["rows_processed"] == 800
        assert progress["rows_skipped"] == 50
        assert progress["rows_successful"] == 750
        assert progress["households_created"] == 700
        assert progress["members_created"] == 2100
        assert progress["errors_created"] == 350
        assert progress["percent_complete"] == 80

    def test_validation_counts_empty(self):
        """Test validation counts when lists are empty"""
        status = ETLStatus(job_id="test")

        result = status.to_dict()

        assert result["validation"]["errors_count"] == 0
        assert result["validation"]["warnings_count"] == 0

    def test_validation_counts_with_items(self):
        """Test validation counts with multiple items"""
        status = ETLStatus(job_id="test")
        status.validation_errors = ["E1", "E2", "E3", "E4", "E5"]
        status.validation_warnings = ["W1", "W2"]

        result = status.to_dict()

        assert result["validation"]["errors_count"] == 5
        assert result["validation"]["warnings_count"] == 2


class TestETLLoaderInit:
    """Test ETLLoader initialization"""

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_init_basic(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test basic initialization"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2023)

        assert loader.fiscal_year == 2023
        assert loader.batch_size == 10000
        assert loader.strict_validation is False
        assert loader.skip_validation is False

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_init_custom_params(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test initialization with custom parameters"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2022, batch_size=5000, strict_validation=True, skip_validation=True)

        assert loader.fiscal_year == 2022
        assert loader.batch_size == 5000
        assert loader.strict_validation is True
        assert loader.skip_validation is True

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_has_required_attributes(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test that ETLLoader has required attributes"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2023)

        # Should have all required attributes
        assert hasattr(loader, "fiscal_year")
        assert hasattr(loader, "batch_size")
        assert hasattr(loader, "strict_validation")
        assert hasattr(loader, "skip_validation")


class TestETLLoaderValidation:
    """Test ETLLoader validation configuration"""

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_validation_enabled_by_default(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test validation is enabled by default"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2023)

        assert loader.skip_validation is False

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_can_skip_validation(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test can skip validation"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2023, skip_validation=True)

        assert loader.skip_validation is True

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_strict_validation_disabled_by_default(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test strict validation is disabled by default"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2023)

        assert loader.strict_validation is False

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_can_enable_strict_validation(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test can enable strict validation"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2023, strict_validation=True)

        assert loader.strict_validation is True


class TestETLLoaderBatching:
    """Test ETLLoader batch configuration"""

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_default_batch_size(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test default batch size"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2023)

        assert loader.batch_size == 10000

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_custom_batch_size(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test custom batch size"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2023, batch_size=1000)

        assert loader.batch_size == 1000

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_large_batch_size(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test large batch size"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2023, batch_size=50000)

        assert loader.batch_size == 50000

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_small_batch_size(self, mock_reader, mock_transformer, mock_validator, mock_writer):
        """Test small batch size"""
        from src.etl.loader import ETLLoader

        loader = ETLLoader(fiscal_year=2023, batch_size=100)

        assert loader.batch_size == 100


class TestETLLoaderErrorHandling:
    """Test ETLLoader error handling"""

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_load_validation_error(self, mock_reader_cls, mock_transformer, mock_validator, mock_writer):
        """Test load handles ValidationError"""
        from src.core.exceptions import ValidationError
        from src.etl.loader import ETLLoader

        # Mock reader
        mock_reader = Mock()
        mock_reader.get_row_count.return_value = 50
        mock_reader_cls.return_value = mock_reader
        mock_reader.read_csv.side_effect = ValidationError("Invalid CSV format")

        loader = ETLLoader(fiscal_year=2023)

        with pytest.raises(ValidationError):
            loader.load_from_file("/fake/path.csv")

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_load_database_error(self, mock_reader_cls, mock_transformer, mock_validator, mock_writer):
        """Test load handles DatabaseError"""
        from src.core.exceptions import DatabaseError
        from src.etl.loader import ETLLoader

        # Mock reader
        mock_reader = Mock()
        mock_reader.get_row_count.return_value = 50
        mock_reader.read_csv.return_value = Mock(spec=["__len__"], __len__=Mock(return_value=50))
        mock_reader_cls.return_value = mock_reader

        # Mock transformer
        mock_transformer_inst = Mock()
        mock_transformer_inst.transform.side_effect = DatabaseError("Connection lost")
        mock_transformer.return_value = mock_transformer_inst

        loader = ETLLoader(fiscal_year=2023)

        with pytest.raises(DatabaseError):
            loader.load_from_file("/fake/path.csv")

    @patch("src.etl.loader.DatabaseWriter")
    @patch("src.etl.loader.DataValidator")
    @patch("src.etl.loader.DataTransformer")
    @patch("src.etl.loader.CSVReader")
    def test_load_unexpected_error(self, mock_reader_cls, mock_transformer, mock_validator, mock_writer):
        """Test load handles unexpected exceptions"""
        from src.etl.loader import ETLLoader

        # Mock reader
        mock_reader = Mock()
        mock_reader.get_row_count.return_value = 50
        mock_reader.read_csv.side_effect = RuntimeError("Unexpected error")
        mock_reader_cls.return_value = mock_reader

        loader = ETLLoader(fiscal_year=2023)

        with pytest.raises(RuntimeError):
            loader.load_from_file("/fake/path.csv")
