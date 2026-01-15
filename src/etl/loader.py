"""
SnapAnalyst ETL Orchestrator

Coordinates the complete ETL pipeline: Read → Transform → Validate → Write
"""
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

import polars as pl

from src.core.logging import get_logger
from src.core.exceptions import ValidationError, DatabaseError
from src.etl.reader import CSVReader
from src.etl.transformer import DataTransformer
from src.etl.validator import DataValidator
from src.etl.writer import DatabaseWriter

logger = get_logger(__name__)


def check_references_ready() -> tuple[bool, list[str]]:
    """
    Check if reference tables are populated.
    
    CRITICAL: Main tables have FK constraints to reference tables.
    Loading data will fail if reference tables are empty.
    
    Returns:
        Tuple of (ready: bool, empty_tables: list[str])
    """
    try:
        from src.database.init_database import check_references_populated
        return check_references_populated()
    except Exception as e:
        logger.warning(f"Could not check reference tables: {e}")
        return True, []  # Assume OK if check fails


class ETLStatus:
    """Track ETL job status"""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = "pending"  # pending, in_progress, completed, failed
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        
        # Progress tracking
        self.total_rows = 0
        self.rows_processed = 0
        self.rows_skipped = 0  # New: track skipped rows
        self.households_created = 0
        self.members_created = 0
        self.errors_created = 0
        
        # Validation tracking
        self.validation_errors = []
        self.validation_warnings = []
    
    def to_dict(self) -> dict:
        """Convert status to dictionary"""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "progress": {
                "total_rows": self.total_rows,
                "rows_processed": self.rows_processed,
                "rows_skipped": self.rows_skipped,  # New field
                "rows_successful": self.rows_processed - self.rows_skipped,  # Calculated
                "households_created": self.households_created,
                "members_created": self.members_created,
                "errors_created": self.errors_created,
                "percent_complete": int((self.rows_processed / self.total_rows * 100)) if self.total_rows > 0 else 0,
            },
            "validation": {
                "errors_count": len(self.validation_errors),
                "warnings_count": len(self.validation_warnings),
            }
        }


class ETLLoader:
    """Main ETL orchestrator"""
    
    def __init__(
        self,
        fiscal_year: int,
        batch_size: int = 1000,
        strict_validation: bool = False,
        skip_validation: bool = False,
    ):
        """
        Initialize ETL loader.
        
        Args:
            fiscal_year: Fiscal year for the data
            batch_size: Number of records to process per batch
            strict_validation: If True, fail on any validation error
            skip_validation: If True, skip validation step
        """
        self.fiscal_year = fiscal_year
        self.batch_size = batch_size
        self.strict_validation = strict_validation
        self.skip_validation = skip_validation
        
        self.reader: Optional[CSVReader] = None
        self.transformer = DataTransformer(fiscal_year)
        self.validator = DataValidator(strict=strict_validation)
        
        logger.info(
            f"ETL Loader initialized (fiscal_year={fiscal_year}, "
            f"batch_size={batch_size}, strict={strict_validation})"
        )
    
    def load_from_file(
        self,
        file_path: str,
        job_id: Optional[str] = None,
        status: Optional[ETLStatus] = None,
    ) -> ETLStatus:
        """
        Load data from CSV file through complete ETL pipeline.
        
        Args:
            file_path: Path to CSV file
            job_id: Optional job identifier
            status: Optional existing ETLStatus object to update (for real-time tracking)
            
        Returns:
            ETLStatus object with results
            
        Raises:
            ValidationError: If validation fails in strict mode
            DatabaseError: If database write fails
        """
        # Initialize status tracking (or use provided status)
        if status is None:
            if job_id is None:
                job_id = f"load_{self.fiscal_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            status = ETLStatus(job_id)
        elif job_id is not None:
            status.job_id = job_id
            
        status.status = "in_progress"
        status.started_at = datetime.now()
        
        # Check reference tables are populated (FK constraints require this)
        refs_ready, empty_tables = check_references_ready()
        if not refs_ready:
            logger.warning(
                f"Reference tables not populated: {', '.join(empty_tables)}. "
                "Some inserts may fail due to FK constraints. "
                "Run: python -m src.database.init_database"
            )
        
        try:
            logger.info(f"Starting ETL job {job_id} for file: {file_path}")
            
            # Step 1: Initialize reader
            self.reader = CSVReader(file_path)
            status.total_rows = self.reader.get_row_count()
            logger.info(f"Total rows to process: {status.total_rows:,}")
            
            # Step 2: Process file (all at once or in chunks)
            if status.total_rows <= 100000:  # Files under 100K rows - read all at once to avoid schema issues
                # Small/medium file - process all at once
                result = self._process_batch(
                    self.reader.read_csv(),
                    status
                )
            else:
                # Large file - process in chunks
                result = self._process_in_chunks(status)
            
            # Check if _process_batch returned early due to critical error
            if isinstance(result, ETLStatus):
                # Critical error occurred (e.g., FK violation) - status already set
                logger.error(f"ETL job {job_id} failed: {result.error_message}")
                return result
            
            # Update final status
            status.households_created = result["households_written"]
            status.members_created = result["members_written"]
            status.errors_created = result["errors_written"]
            status.rows_processed = status.total_rows
            # rows_skipped is already updated during processing
            status.status = "completed"
            status.completed_at = datetime.now()
            
            duration = (status.completed_at - status.started_at).total_seconds()
            logger.info(
                f"ETL job {job_id} completed successfully in {duration:.2f}s: "
                f"{status.households_created} households, "
                f"{status.members_created} members, "
                f"{status.errors_created} QC errors, "
                f"{status.rows_skipped} rows skipped"
            )
            
            return status
            
        except ValidationError as e:
            logger.error(f"Validation error in job {job_id}: {e}")
            status.status = "failed"
            status.error_message = f"Validation error: {e}"
            status.completed_at = datetime.now()
            raise
            
        except DatabaseError as e:
            logger.error(f"Database error in job {job_id}: {e}")
            status.status = "failed"
            status.error_message = f"Database error: {e}"
            status.completed_at = datetime.now()
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error in job {job_id}: {e}")
            status.status = "failed"
            status.error_message = f"Unexpected error: {e}"
            status.completed_at = datetime.now()
            raise
    
    def _process_batch(
        self,
        df: pl.DataFrame,
        status: ETLStatus
    ) -> Dict:
        """
        Process a single batch of data row by row with incremental database writes.
        
        Args:
            df: Polars DataFrame with raw CSV data
            status: Status tracker
            
        Returns:
            Dictionary with write statistics
        """
        logger.info(f"Processing batch of {len(df)} rows with incremental writes")
        
        total_rows = len(df)
        successful_rows = 0
        failed_rows = 0
        failed_row_indices = []
        
        # Accumulate data for mini-batches
        batch_households = []
        batch_members = []
        batch_errors = []
        
        # Cumulative write statistics
        total_households_written = 0
        total_members_written = 0
        total_errors_written = 0
        
        # Write to database every N rows for incremental loading
        WRITE_BATCH_SIZE = 100
        
        # Update status
        status.status = "in_progress"
        status.rows_processed = 0
        status.rows_skipped = 0
        
        # Process row by row
        for row_idx in range(total_rows):
            try:
                # Extract single row
                row_df = df[row_idx:row_idx+1]
                
                # Transform this row
                households_df, members_df, errors_df = self.transformer.transform(row_df)
                
                # Convert to dictionaries and accumulate
                batch_households.extend(households_df.to_dicts())
                batch_members.extend(members_df.to_dicts())
                batch_errors.extend(errors_df.to_dicts())
                
                successful_rows += 1
                
            except Exception as e:
                failed_rows += 1
                failed_row_indices.append(row_idx)
                logger.warning(f"Row {row_idx} failed to process: {str(e)[:200]}")
                # Continue to next row instead of failing
            
            # Update progress tracking
            status.rows_processed = row_idx + 1
            status.rows_skipped = failed_rows
            
            # Write to database every WRITE_BATCH_SIZE rows
            should_write = (row_idx + 1) % WRITE_BATCH_SIZE == 0
            is_last_row = (row_idx + 1) == total_rows
            
            if (should_write or is_last_row) and len(batch_households) > 0:
                try:
                    # Convert accumulated data to DataFrames
                    import polars as pl
                    households_df = pl.DataFrame(batch_households)
                    members_df = pl.DataFrame(batch_members)
                    errors_df = pl.DataFrame(batch_errors)
                    
                    # Write to database
                    with DatabaseWriter(batch_size=self.batch_size) as writer:
                        write_stats = writer.write_all(
                            households_df,
                            members_df,
                            errors_df,
                            self.fiscal_year
                        )
                    
                    # Update cumulative statistics
                    total_households_written += write_stats["households_written"]
                    total_members_written += write_stats["members_written"]
                    total_errors_written += write_stats["errors_written"]
                    
                    # Update status with current counts
                    status.households_created = total_households_written
                    status.members_created = total_members_written
                    status.errors_created = total_errors_written
                    
                    logger.info(
                        f"Batch write complete at row {row_idx + 1}: "
                        f"+{write_stats['households_written']} households "
                        f"(total: {total_households_written})"
                    )
                    
                    # Clear batch accumulators
                    batch_households = []
                    batch_members = []
                    batch_errors = []
                    
                except Exception as e:
                    error_str = str(e)
                    logger.error(f"Failed to write batch at row {row_idx}: {e}")
                    
                    # Check if this is a critical error that should stop the load
                    is_fk_violation = "ForeignKeyViolation" in error_str or "violates foreign key constraint" in error_str
                    is_integrity_error = "IntegrityError" in error_str or "UniqueViolation" in error_str
                    
                    if is_fk_violation:
                        # FK violation = missing reference data = cannot continue
                        status.status = "failed"
                        status.error_message = f"Foreign key constraint error - missing reference data: {error_str[:500]}"
                        status.completed_at = datetime.now()
                        logger.error(f"CRITICAL: Stopping load due to foreign key violation. Check reference tables.")
                        return status
                    
                    # For other errors, count the failed rows and clear the batch
                    batch_row_count = len(batch_households)
                    failed_rows += batch_row_count
                    status.rows_skipped = failed_rows
                    logger.warning(f"Batch of {batch_row_count} rows failed, continuing with next batch")
                    
                    # Clear failed batch to prevent cascading errors
                    batch_households = []
                    batch_members = []
                    batch_errors = []
            
            # Log progress every 1000 rows
            if (row_idx + 1) % 1000 == 0:
                logger.info(
                    f"Progress: {row_idx + 1}/{total_rows} rows processed "
                    f"({successful_rows} successful, {failed_rows} failed) - "
                    f"{total_households_written} households in database"
                )
        
        logger.info(
            f"Row processing complete: {successful_rows} successful, {failed_rows} failed out of {total_rows} total"
        )
        
        if failed_rows > 0:
            logger.warning(f"Failed row indices: {failed_row_indices[:20]}{'...' if len(failed_row_indices) > 20 else ''}")
        
        logger.info(
            f"Final counts: {total_households_written} households, "
            f"{total_members_written} members, {total_errors_written} QC errors"
        )
        
        return {
            "households_written": total_households_written,
            "members_written": total_members_written,
            "errors_written": total_errors_written,
            "total_records": total_households_written + total_members_written + total_errors_written,
            "rows_skipped": failed_rows,
        }
    
    def _process_in_chunks(self, status: ETLStatus) -> Dict:
        """
        Process large file in chunks.
        
        Args:
            status: Status tracker
            
        Returns:
            Dictionary with cumulative write statistics
        """
        logger.info(f"Processing file in chunks of {self.batch_size} rows")
        
        total_stats = {
            "households_written": 0,
            "members_written": 0,
            "errors_written": 0,
            "total_records": 0,
        }
        
        chunk_num = 0
        for chunk_df in self.reader.read_in_chunks(self.batch_size):
            chunk_num += 1
            logger.info(f"Processing chunk {chunk_num} ({len(chunk_df)} rows)")
            
            # Process chunk
            chunk_stats = self._process_batch(chunk_df, status)
            
            # Update cumulative stats
            total_stats["households_written"] += chunk_stats["households_written"]
            total_stats["members_written"] += chunk_stats["members_written"]
            total_stats["errors_written"] += chunk_stats["errors_written"]
            total_stats["total_records"] += chunk_stats["total_records"]
            
            # Update progress
            status.rows_processed += len(chunk_df)
            
            logger.info(
                f"Progress: {status.rows_processed:,}/{status.total_rows:,} rows "
                f"({status.rows_processed/status.total_rows*100:.1f}%)"
            )
        
        return total_stats
    
    @staticmethod
    def estimate_load_time(row_count: int, rows_per_second: int = 300) -> float:
        """
        Estimate load time in seconds.
        
        Args:
            row_count: Number of rows to load
            rows_per_second: Expected processing rate
            
        Returns:
            Estimated time in seconds
        """
        return row_count / rows_per_second


class ETLJobManager:
    """Manage multiple ETL jobs"""
    
    def __init__(self):
        self.jobs: Dict[str, ETLStatus] = {}
        logger.info("ETL Job Manager initialized")
    
    def create_job(self, job_id: str) -> ETLStatus:
        """
        Create a new job.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            ETLStatus object
        """
        status = ETLStatus(job_id)
        self.jobs[job_id] = status
        logger.info(f"Created job {job_id}")
        return status
    
    def get_job(self, job_id: str) -> Optional[ETLStatus]:
        """
        Get job status.
        
        Args:
            job_id: Job identifier
            
        Returns:
            ETLStatus or None if not found
        """
        return self.jobs.get(job_id)
    
    def list_jobs(self) -> list:
        """
        List all jobs.
        
        Returns:
            List of job status dictionaries
        """
        return [status.to_dict() for status in self.jobs.values()]
    
    def clear_completed_jobs(self, max_age_seconds: int = 3600):
        """
        Clear old completed jobs.
        
        Args:
            max_age_seconds: Maximum age of completed jobs to keep
        """
        now = datetime.now()
        to_remove = []
        
        for job_id, status in self.jobs.items():
            if status.status in ("completed", "failed") and status.completed_at:
                age = (now - status.completed_at).total_seconds()
                if age > max_age_seconds:
                    to_remove.append(job_id)
        
        for job_id in to_remove:
            del self.jobs[job_id]
            logger.info(f"Cleared old job {job_id}")
