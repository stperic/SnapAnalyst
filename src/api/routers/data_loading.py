"""
SnapAnalyst Data Loading API Router

Endpoints for loading SNAP QC CSV files into the database.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logging import get_logger
from src.etl.loader import ETLJobManager, ETLLoader

logger = get_logger(__name__)

router = APIRouter(tags=["data"])

# Global job manager (in production, use Redis or database)
job_manager = ETLJobManager()


class LoadRequest(BaseModel):
    """Request to load CSV data"""

    fiscal_year: int = Field(..., ge=2000, le=2030, description="Fiscal year to load")
    filename: str | None = Field(None, description="CSV filename (if not provided, uses default pattern)")
    batch_size: int = Field(1000, ge=100, le=10000, description="Batch size for processing")
    strict_validation: bool = Field(False, description="Fail on any validation error")
    skip_validation: bool = Field(False, description="Skip validation step (not recommended)")


class LoadMultipleRequest(BaseModel):
    """Request to load multiple fiscal years"""

    fiscal_years: list[int] = Field(..., description="List of fiscal years to load")
    batch_size: int = Field(1000, ge=100, le=10000)
    strict_validation: bool = Field(False)
    skip_validation: bool = Field(False)


class LoadResponse(BaseModel):
    """Response from load request"""

    status: str
    job_id: str
    message: str
    fiscal_year: int
    estimated_time_seconds: int | None = None
    progress_url: str


class JobStatusResponse(BaseModel):
    """Response with job status"""

    job_id: str
    status: str
    started_at: str | None
    completed_at: str | None
    error_message: str | None
    progress: dict
    validation: dict


def _background_load_task(
    file_path: str,
    fiscal_year: int,
    job_id: str,
    batch_size: int,
    strict_validation: bool,
    skip_validation: bool,
):
    """Background task to load data"""
    try:
        logger.info(f"Starting background load task {job_id}")

        # Get the status object from job manager so we can update it in real-time
        status = job_manager.get_job(job_id)

        loader = ETLLoader(
            fiscal_year=fiscal_year,
            batch_size=batch_size,
            strict_validation=strict_validation,
            skip_validation=skip_validation,
        )

        # Pass the status object so loader can update it during processing
        final_status = loader.load_from_file(file_path, job_id=job_id, status=status)

        # Update job manager with final status (should already be updated, but make sure)
        job_manager.jobs[job_id] = final_status

        logger.info(f"Background load task {job_id} completed")

    except Exception as e:
        logger.error(f"Background load task {job_id} failed: {e}")
        # Update job status
        if job_id in job_manager.jobs:
            job_manager.jobs[job_id].status = "failed"
            job_manager.jobs[job_id].error_message = str(e)
            job_manager.jobs[job_id].completed_at = datetime.now()


@router.post("/load", response_model=LoadResponse, status_code=202)
async def load_data(request: LoadRequest, background_tasks: BackgroundTasks):
    """
    Load SNAP QC CSV file into database.

    This endpoint initiates a background job to load data.
    Use the progress_url to check status.

    Returns:
        202 Accepted with job information
    """
    try:
        # Determine file path
        if request.filename:
            file_path = Path(settings.resolved_data_path) / request.filename
        else:
            # Use default filename pattern
            file_path = Path(settings.resolved_data_path) / f"qc_pub_fy{request.fiscal_year}.csv"

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"CSV file not found: {file_path.name}")

        # Create job
        job_id = f"load_{request.fiscal_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        job_manager.create_job(job_id)

        # Estimate time (rough estimate: 300 rows/second)
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        estimated_rows = int(file_size_mb * 700)  # Rough estimate
        estimated_time = int(estimated_rows / 300)  # 300 rows/sec

        # Add background task
        background_tasks.add_task(
            _background_load_task,
            str(file_path),
            request.fiscal_year,
            job_id,
            request.batch_size,
            request.strict_validation,
            request.skip_validation,
        )

        logger.info(f"Created load job {job_id} for {file_path.name}")

        return LoadResponse(
            status="accepted",
            job_id=job_id,
            message=f"Data loading initiated for FY{request.fiscal_year}",
            fiscal_year=request.fiscal_year,
            estimated_time_seconds=estimated_time,
            progress_url=f"/api/v1/data/load/status/{job_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate load: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate load: {e}")


@router.post("/load-multiple", status_code=202)
async def load_multiple_years(request: LoadMultipleRequest, background_tasks: BackgroundTasks):
    """
    Load multiple fiscal years.

    Initiates separate background jobs for each fiscal year.

    Returns:
        202 Accepted with list of job IDs
    """
    try:
        job_ids = []

        for fiscal_year in request.fiscal_years:
            # Determine file path
            file_path = Path(settings.resolved_data_path) / f"qc_pub_fy{fiscal_year}.csv"

            if not file_path.exists():
                logger.warning(f"Skipping FY{fiscal_year} - file not found: {file_path.name}")
                continue

            # Create job
            job_id = f"load_{fiscal_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            job_manager.create_job(job_id)
            job_ids.append(job_id)

            # Add background task
            background_tasks.add_task(
                _background_load_task,
                str(file_path),
                fiscal_year,
                job_id,
                request.batch_size,
                request.strict_validation,
                request.skip_validation,
            )

            logger.info(f"Created load job {job_id} for FY{fiscal_year}")

        return {
            "status": "accepted",
            "job_ids": job_ids,
            "message": f"Data loading initiated for {len(job_ids)} fiscal years",
            "fiscal_years": request.fiscal_years,
        }

    except Exception as e:
        logger.error(f"Failed to initiate multiple loads: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate loads: {e}")


@router.get("/load/status/{job_id}", response_model=JobStatusResponse)
async def get_load_status(job_id: str):
    """
    Check status of a load job.

    Args:
        job_id: Job identifier

    Returns:
        Job status with progress information
    """
    try:
        job_status = job_manager.get_job(job_id)

        if not job_status:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return JobStatusResponse(**job_status.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")


@router.get("/load/jobs")
async def list_jobs(active_only: bool = False):
    """
    List all load jobs.

    Args:
        active_only: If True, only return jobs that are in progress

    Returns:
        List of all job statuses
    """
    try:
        all_jobs = job_manager.list_jobs()

        if active_only:
            # Filter for jobs that are in progress
            active_jobs = [job for job in all_jobs if job.get("status") in ["in_progress", "processing", "accepted"]]
            return {"jobs": active_jobs, "total": len(active_jobs)}

        return {"jobs": all_jobs, "total": len(all_jobs)}
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {e}")
