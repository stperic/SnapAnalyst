"""
SnapAnalyst CSV Reader

Reads SNAP QC CSV files using Polars for performance.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from src.core.exceptions import DataFileNotFoundError as SnapFileNotFoundError
from src.core.exceptions import ValidationError
from src.core.logging import get_logger
from src.utils.column_mapping import get_required_household_columns

logger = get_logger(__name__)


class CSVReader:
    """Reads and validates SNAP QC CSV files"""

    def __init__(self, file_path: str):
        """
        Initialize CSV reader.

        Args:
            file_path: Path to CSV file

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise SnapFileNotFoundError(f"CSV file not found: {file_path}")

        self.file_size_bytes = self.file_path.stat().st_size
        logger.info(f"CSV Reader initialized for: {self.file_path.name} ({self.file_size_bytes:,} bytes)")

    def read_csv(
        self,
        _batch_size: int | None = None,
        skip_rows: int = 0,
        n_rows: int | None = None,
    ) -> pl.DataFrame:
        """
        Read CSV file into Polars DataFrame.

        Args:
            _batch_size: Unused, kept for API compatibility
            skip_rows: Number of rows to skip
            n_rows: Number of rows to read (None = all)

        Returns:
            Polars DataFrame

        Raises:
            ValidationError: If CSV structure is invalid
        """
        try:
            logger.info(f"Reading CSV: {self.file_path.name} (skip={skip_rows}, n_rows={n_rows})")

            df = pl.read_csv(
                self.file_path,
                skip_rows=skip_rows,
                n_rows=n_rows,
                null_values=["", "NA", "N/A", "NULL"],  # Treat these as null
                try_parse_dates=True,
                infer_schema_length=50000,  # Scan up to 50K rows to handle type variations (more than our 43K total)
            )

            logger.info(f"CSV loaded: {len(df)} rows, {len(df.columns)} columns")

            # Validate structure
            self._validate_structure(df)

            return df

        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            raise ValidationError(f"Failed to read CSV: {e}")

    def get_row_count(self) -> int:
        """
        Get total number of rows in CSV (excluding header).

        Returns:
            Number of data rows
        """
        try:
            # Fast row count using Polars lazy loading
            row_count = pl.scan_csv(self.file_path).select(pl.len()).collect().item()
            logger.info(f"CSV has {row_count:,} rows")
            return row_count
        except Exception as e:
            logger.error(f"Error counting rows: {e}")
            return 0

    def get_column_names(self) -> list[str]:
        """
        Get list of all column names in CSV.

        Returns:
            List of column names
        """
        try:
            df = pl.read_csv(self.file_path, n_rows=0)
            return df.columns
        except Exception as e:
            logger.error(f"Error reading column names: {e}")
            raise ValidationError(f"Failed to read column names: {e}")

    def _validate_structure(self, df: pl.DataFrame) -> None:
        """
        Validate CSV structure has required columns.

        Args:
            df: DataFrame to validate

        Raises:
            ValidationError: If required columns are missing
        """
        required_columns = get_required_household_columns()
        missing_columns = [col for col in required_columns if col not in df.columns]

        # Debug logging
        logger.info(f"DataFrame has {len(df.columns)} columns")
        logger.info(f"First 20 columns: {df.columns[:20]}")
        logger.info(f"Required columns: {required_columns}")
        logger.info(f"Missing columns: {missing_columns}")

        if missing_columns:
            raise ValidationError(f"Missing required columns: {', '.join(missing_columns)}")

        logger.debug(f"CSV structure validated: {len(df.columns)} columns")

    def read_in_chunks(self, chunk_size: int = 1000):
        """
        Generator to read CSV in chunks for memory efficiency.

        Args:
            chunk_size: Number of rows per chunk

        Yields:
            Polars DataFrame chunks

        Note:
            We read all columns as strings first to avoid schema inference issues,
            then let the transformer handle type conversions.
        """
        total_rows = self.get_row_count()

        if total_rows == 0:
            return

        # Get column names from first row
        first_row = pl.read_csv(self.file_path, n_rows=1)
        column_names = first_row.columns

        logger.info(f"Reading CSV in chunks with {len(column_names)} columns")

        # Read all chunks with string dtypes to avoid schema inference issues
        for offset in range(0, total_rows, chunk_size):
            n_rows = min(chunk_size, total_rows - offset)
            logger.debug(f"Reading chunk: offset={offset}, n_rows={n_rows}")

            if offset == 0:
                # First chunk - read normally with header
                df_chunk = pl.read_csv(
                    self.file_path,
                    skip_rows=0,
                    n_rows=n_rows,
                    null_values=["", "NA", "N/A", "NULL"],
                    try_parse_dates=False,  # Don't parse dates to avoid type issues
                    infer_schema_length=0,  # Read everything as strings
                )
            else:
                # Subsequent chunks - read as strings to avoid schema mismatches
                df_chunk = pl.read_csv(
                    self.file_path,
                    skip_rows=offset + 1,  # +1 to skip the header row
                    n_rows=n_rows,
                    has_header=False,  # Don't treat first row as header
                    new_columns=column_names,  # Use the column names
                    null_values=["", "NA", "N/A", "NULL"],
                    try_parse_dates=False,  # Don't parse dates
                    infer_schema_length=0,  # Read everything as strings
                )

            logger.info(f"Chunk loaded: {len(df_chunk)} rows, {len(df_chunk.columns)} columns")
            yield df_chunk
