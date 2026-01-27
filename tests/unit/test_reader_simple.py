"""
Simplified unit tests for CSVReader - no database required
"""
from pathlib import Path

import polars as pl
import pytest

from src.etl.reader import CSVReader


class TestCSVReaderBasic:
    """Basic test suite for CSVReader class"""

    def test_init_with_valid_file(self, test_csv_path: Path):
        """Test CSVReader initialization with valid file"""
        reader = CSVReader(str(test_csv_path))

        assert reader.file_path == test_csv_path
        assert reader.file_size_bytes > 0

    def test_init_with_invalid_file(self):
        """Test CSVReader initialization with non-existent file"""
        from src.core.exceptions import FileNotFoundError as SnapFileNotFoundError
        with pytest.raises(SnapFileNotFoundError):
            CSVReader("/nonexistent/file.csv")

    def test_read_csv_basic(self, test_csv_path: Path):
        """Test basic CSV reading"""
        reader = CSVReader(str(test_csv_path))
        df = reader.read_csv(n_rows=10)

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 10
        assert len(df.columns) > 0

    def test_read_csv_with_limit(self, test_csv_path: Path):
        """Test reading limited number of rows"""
        reader = CSVReader(str(test_csv_path))
        df = reader.read_csv(n_rows=5)

        assert len(df) == 5

    def test_get_row_count(self, test_csv_path: Path):
        """Test getting row count"""
        reader = CSVReader(str(test_csv_path))
        row_count = reader.get_row_count()

        assert row_count > 0
        assert isinstance(row_count, int)
        # We know the test CSV has 43,777 rows
        assert row_count == 43776  # Excluding header

    def test_get_column_names(self, test_csv_path: Path):
        """Test getting column names"""
        reader = CSVReader(str(test_csv_path))
        columns = reader.get_column_names()

        assert isinstance(columns, list)
        assert len(columns) > 0
        # Check for expected columns
        assert "CASE" in columns
        assert "STATE" in columns
        assert "FSBEN" in columns

    def test_file_size_tracking(self, test_csv_path: Path):
        """Test file size is tracked correctly"""
        reader = CSVReader(str(test_csv_path))

        assert reader.file_size_bytes > 0
        # Test CSV should be several MB
        assert reader.file_size_bytes > 1_000_000  # > 1MB
