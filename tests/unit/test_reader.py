"""
Unit tests for CSVReader

Tests error handling, validation, and chunk reading functionality.
"""
from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest

from src.core.exceptions import ValidationError
from src.etl.reader import CSVReader


class TestCSVReaderErrors:
    """Test error handling in CSVReader"""

    @patch('polars.read_csv')
    def test_read_csv_error_handling(self, mock_read_csv, test_csv_path: Path):
        """Test read_csv handles exceptions gracefully"""
        reader = CSVReader(str(test_csv_path))

        # Simulate polars raising an exception
        mock_read_csv.side_effect = Exception("CSV read error")

        with pytest.raises(ValidationError, match="Failed to read CSV"):
            reader.read_csv()

    @patch('polars.scan_csv')
    def test_get_row_count_error_handling(self, mock_scan_csv, test_csv_path: Path):
        """Test get_row_count handles exceptions gracefully"""
        reader = CSVReader(str(test_csv_path))

        # Simulate polars raising an exception
        mock_scan_csv.side_effect = Exception("Cannot count rows")

        # Should return 0 on error instead of crashing
        result = reader.get_row_count()
        assert result == 0

    @patch('polars.read_csv')
    def test_get_column_names_error_handling(self, mock_read_csv, test_csv_path: Path):
        """Test get_column_names handles exceptions gracefully"""
        reader = CSVReader(str(test_csv_path))

        # Simulate polars raising an exception
        mock_read_csv.side_effect = Exception("Cannot read columns")

        with pytest.raises(ValidationError, match="Failed to read column names"):
            reader.get_column_names()


class TestCSVReaderValidation:
    """Test CSV validation logic"""

    def test_missing_required_columns(self, test_csv_path: Path, tmp_path: Path):
        """Test validation fails when required columns are missing"""
        # Create a CSV with incomplete columns
        incomplete_csv = tmp_path / "incomplete.csv"
        df = pl.DataFrame({
            "STATE": ["CA"],
            "OTHER": ["value"],
        })
        df.write_csv(incomplete_csv)

        reader = CSVReader(str(incomplete_csv))

        # Should raise ValidationError for missing HHLDNO, YRMONTH, FSBEN
        with pytest.raises(ValidationError, match="Missing required columns"):
            reader.read_csv()

    def test_valid_structure_passes(self, test_csv_path: Path):
        """Test validation passes with all required columns"""
        reader = CSVReader(str(test_csv_path))

        # Should not raise - test CSV has all required columns
        df = reader.read_csv(n_rows=10)
        assert len(df) == 10


class TestCSVReaderChunks:
    """Test read_in_chunks functionality"""

    def test_read_in_chunks_basic(self, test_csv_path: Path):
        """Test reading CSV in chunks"""
        reader = CSVReader(str(test_csv_path))

        chunk_size = 500
        chunks = list(reader.read_in_chunks(chunk_size=chunk_size))

        # Should have multiple chunks
        assert len(chunks) > 1

        # First chunk should have chunk_size rows
        assert len(chunks[0]) == chunk_size

        # All chunks should have same columns
        first_columns = chunks[0].columns
        for chunk in chunks[1:]:
            assert chunk.columns == first_columns

    def test_read_in_chunks_small_file(self, test_csv_path: Path, tmp_path: Path):
        """Test read_in_chunks with small file"""
        # Create a small CSV file
        small_csv = tmp_path / "small.csv"
        df = pl.DataFrame({
            "HHLDNO": ["1", "2", "3"],
            "STATE": ["CA", "TX", "NY"],
            "YRMONTH": ["202301", "202301", "202301"],
            "FSBEN": [100.0, 200.0, 300.0],
        })
        df.write_csv(small_csv)

        reader = CSVReader(str(small_csv))

        # Read with large chunk size
        chunks = list(reader.read_in_chunks(chunk_size=10))

        # Should have just 1 chunk with all rows
        assert len(chunks) == 1
        assert len(chunks[0]) == 3

    def test_read_in_chunks_empty_file(self, tmp_path: Path):
        """Test read_in_chunks with empty file (no data rows)"""
        empty_csv = tmp_path / "empty.csv"
        # Create file with just headers
        df = pl.DataFrame({
            "HHLDNO": [],
            "STATE": [],
            "YRMONTH": [],
            "FSBEN": [],
        })
        df.write_csv(empty_csv)

        reader = CSVReader(str(empty_csv))

        # Should return no chunks
        chunks = list(reader.read_in_chunks(chunk_size=1000))
        assert len(chunks) == 0

    def test_read_in_chunks_multiple_chunks(self, tmp_path: Path):
        """Test read_in_chunks creates multiple chunks correctly"""
        # Create CSV with 25 rows
        large_csv = tmp_path / "large.csv"
        df = pl.DataFrame({
            "HHLDNO": [str(i) for i in range(1, 26)],
            "STATE": ["CA"] * 25,
            "YRMONTH": ["202301"] * 25,
            "FSBEN": [float(i * 100) for i in range(1, 26)],
        })
        df.write_csv(large_csv)

        reader = CSVReader(str(large_csv))

        # Read in chunks of 10
        chunks = list(reader.read_in_chunks(chunk_size=10))

        # Should have 3 chunks: 10, 10, 5
        assert len(chunks) == 3
        assert len(chunks[0]) == 10
        assert len(chunks[1]) == 10
        assert len(chunks[2]) == 5

        # Verify all rows are accounted for
        total_rows = sum(len(chunk) for chunk in chunks)
        assert total_rows == 25

    def test_read_in_chunks_preserves_columns(self, tmp_path: Path):
        """Test read_in_chunks preserves all columns across chunks"""
        # Create CSV with many columns
        multi_col_csv = tmp_path / "multi_col.csv"
        df = pl.DataFrame({
            "HHLDNO": ["1", "2", "3", "4", "5"],
            "STATE": ["CA", "TX", "NY", "FL", "WA"],
            "YRMONTH": ["202301"] * 5,
            "FSBEN": [100.0, 200.0, 300.0, 400.0, 500.0],
            "CERTHHSZ": [1, 2, 3, 4, 5],
            "RAWGROSS": [1000.0, 2000.0, 3000.0, 4000.0, 5000.0],
        })
        df.write_csv(multi_col_csv)

        reader = CSVReader(str(multi_col_csv))

        # Read in chunks of 2
        chunks = list(reader.read_in_chunks(chunk_size=2))

        expected_columns = ["HHLDNO", "STATE", "YRMONTH", "FSBEN", "CERTHHSZ", "RAWGROSS"]

        # All chunks should have same columns
        for chunk in chunks:
            assert chunk.columns == expected_columns


