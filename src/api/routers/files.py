"""
SnapAnalyst Files API Router

Endpoints for discovering and managing CSV files.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["files"])


class FileInfo(BaseModel):
    """Information about a CSV file"""

    filename: str
    fiscal_year: int | None
    size_mb: float
    size_bytes: int
    last_modified: str
    loaded: bool = False
    loaded_at: str | None = None
    row_count: int | None = None


class FilesResponse(BaseModel):
    """Response with file list"""

    files: list[FileInfo]
    snapdata_path: str
    total_files: int


def _extract_fiscal_year(filename: str) -> int | None:
    """
    Extract fiscal year from filename.

    Expects pattern like: qc_pub_fy2023.csv

    Args:
        filename: Name of file

    Returns:
        Fiscal year or None if not found
    """
    # Try pattern: fy2023, FY2023, fy23, FY23
    patterns = [
        r"fy(\d{4})",  # fy2023
        r"fy(\d{2})",  # fy23
        r"20(\d{2})",  # 2023
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            year = match.group(1)
            # Convert 2-digit to 4-digit
            if len(year) == 2:
                year = "20" + year
            return int(year)

    return None


@router.get("/files", response_model=FilesResponse)
async def list_files():
    """
    List available CSV files in snapdata folder.

    Returns:
        List of CSV files with metadata
    """
    try:
        snapdata_path = Path(settings.resolved_data_path)

        if not snapdata_path.exists():
            raise HTTPException(status_code=404, detail=f"Snapdata directory not found: {snapdata_path}")

        # Find all CSV files
        csv_files = list(snapdata_path.glob("*.csv"))

        # Get loaded fiscal years from database
        from sqlalchemy import select

        from src.database.engine import get_db_context
        from src.database.models import Household

        loaded_years = set()
        try:
            with get_db_context() as db:
                result = db.execute(select(Household.fiscal_year).distinct()).fetchall()
                loaded_years = {row[0] for row in result if row[0]}
        except Exception as e:
            logger.warning(f"Could not check database for loaded years: {e}")

        files_info = []
        for csv_file in csv_files:
            file_stat = csv_file.stat()

            fiscal_year = _extract_fiscal_year(csv_file.name)
            is_loaded = fiscal_year in loaded_years if fiscal_year else False

            file_info = FileInfo(
                filename=csv_file.name,
                fiscal_year=fiscal_year,
                size_mb=round(file_stat.st_size / (1024 * 1024), 2),
                size_bytes=file_stat.st_size,
                last_modified=datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                loaded=is_loaded,
                loaded_at=None,
                row_count=None,
            )

            files_info.append(file_info)

        # Sort by fiscal year (descending) then by filename
        files_info.sort(key=lambda f: (f.fiscal_year or 0, f.filename), reverse=True)

        logger.info(f"Found {len(files_info)} CSV files in {snapdata_path}")

        return FilesResponse(
            files=files_info,
            snapdata_path=str(snapdata_path),
            total_files=len(files_info),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {e}")


@router.get("/files/{filename}")
async def get_file_info(filename: str):
    """
    Get information about a specific CSV file.

    Args:
        filename: Name of CSV file

    Returns:
        File information
    """
    try:
        file_path = Path(settings.resolved_data_path) / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")

        if not file_path.suffix.lower() == ".csv":
            raise HTTPException(status_code=400, detail=f"Not a CSV file: {filename}")

        file_stat = file_path.stat()
        fiscal_year = _extract_fiscal_year(filename)

        # Try to quickly count rows (first 10MB only for speed)
        try:
            with open(file_path) as f:
                # Read first 10MB
                chunk = f.read(10 * 1024 * 1024)
                lines_in_chunk = chunk.count("\n")

                # Extrapolate total (rough estimate)
                if len(chunk) == 10 * 1024 * 1024:
                    estimated_rows = int(lines_in_chunk * (file_stat.st_size / len(chunk)))
                else:
                    estimated_rows = lines_in_chunk
        except Exception:
            estimated_rows = None

        return FileInfo(
            filename=filename,
            fiscal_year=fiscal_year,
            size_mb=round(file_stat.st_size / (1024 * 1024), 2),
            size_bytes=file_stat.st_size,
            last_modified=datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            loaded=False,  # TODO: Check database
            loaded_at=None,
            row_count=estimated_rows,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {e}")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a CSV file to the snapdata directory.

    Args:
        file: The CSV file to upload

    Returns:
        File information and status
    """
    try:
        # Validate file type
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are accepted")

        # Sanitize filename - extract only the basename to prevent path traversal
        safe_filename = Path(file.filename).name
        if not safe_filename or safe_filename.startswith("."):
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Save to snapdata directory
        snapdata_path = Path(settings.resolved_data_path)
        snapdata_path.mkdir(parents=True, exist_ok=True)

        file_path = (snapdata_path / safe_filename).resolve()
        # Verify the resolved path is still within snapdata_path
        if not str(file_path).startswith(str(snapdata_path.resolve())):
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Check if file already exists
        if file_path.exists():
            # Add timestamp to make it unique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name_parts = safe_filename.rsplit(".", 1)
            safe_filename = f"{name_parts[0]}_{timestamp}.csv"
            file_path = snapdata_path / safe_filename

        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Get file info
        file_stat = file_path.stat()
        fiscal_year = _extract_fiscal_year(safe_filename)

        logger.info(f"Uploaded file: {safe_filename} ({file_stat.st_size} bytes)")

        return {
            "status": "success",
            "message": f"File uploaded successfully: {safe_filename}",
            "file": FileInfo(
                filename=safe_filename,
                fiscal_year=fiscal_year,
                size_mb=round(file_stat.st_size / (1024 * 1024), 2),
                size_bytes=file_stat.st_size,
                last_modified=datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                loaded=False,
                loaded_at=None,
                row_count=None,
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {e}")
