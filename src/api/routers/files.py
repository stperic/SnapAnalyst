"""
SnapAnalyst Files API Router

Endpoints for discovering and managing CSV files.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import re

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["files"])


class FileInfo(BaseModel):
    """Information about a CSV file"""
    filename: str
    fiscal_year: Optional[int]
    size_mb: float
    size_bytes: int
    last_modified: str
    loaded: bool = False
    loaded_at: Optional[str] = None
    row_count: Optional[int] = None


class FilesResponse(BaseModel):
    """Response with file list"""
    files: List[FileInfo]
    snapdata_path: str
    total_files: int


def _extract_fiscal_year(filename: str) -> Optional[int]:
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
        r'fy(\d{4})',  # fy2023
        r'fy(\d{2})',  # fy23
        r'20(\d{2})',  # 2023
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            year = match.group(1)
            # Convert 2-digit to 4-digit
            if len(year) == 2:
                year = '20' + year
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
        snapdata_path = Path(settings.snapdata_path)
        
        if not snapdata_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Snapdata directory not found: {snapdata_path}"
            )
        
        # Find all CSV files
        csv_files = list(snapdata_path.glob("*.csv"))
        
        # Get loaded fiscal years from database
        from src.database.engine import get_db_context
        from sqlalchemy import select
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
        file_path = Path(settings.SNAPDATA_PATH) / filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {filename}"
            )
        
        if not file_path.suffix.lower() == '.csv':
            raise HTTPException(
                status_code=400,
                detail=f"Not a CSV file: {filename}"
            )
        
        file_stat = file_path.stat()
        fiscal_year = _extract_fiscal_year(filename)
        
        # Try to quickly count rows (first 10MB only for speed)
        try:
            with open(file_path, 'r') as f:
                # Read first 10MB
                chunk = f.read(10 * 1024 * 1024)
                lines_in_chunk = chunk.count('\n')
                
                # Extrapolate total (rough estimate)
                if len(chunk) == 10 * 1024 * 1024:
                    estimated_rows = int(lines_in_chunk * (file_stat.st_size / len(chunk)))
                else:
                    estimated_rows = lines_in_chunk
        except:
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
