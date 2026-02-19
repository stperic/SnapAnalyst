"""
SnapAnalyst Management API Router

Endpoints for database management (reset, health check, etc.)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError

from src.core.config import settings
from src.core.logging import get_logger
from src.database.engine import SessionLocal
from src.database.models import Household, HouseholdMember, QCError

logger = get_logger(__name__)

router = APIRouter(tags=["management"])


class ResetRequest(BaseModel):
    """Request to reset database"""
    confirm: bool = Field(..., description="Must be true to confirm reset")
    fiscal_years: list[int] | None = Field(None, description="Specific years to reset (None = all)")
    backup: bool = Field(False, description="Create backup before reset (not implemented)")


class ResetResponse(BaseModel):
    """Response from reset operation"""
    status: str
    message: str
    deleted: dict


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    application: str
    version: str
    database: dict
    tables: dict


@router.post("/reset", response_model=ResetResponse)
async def reset_database(request: ResetRequest):
    """
    Reset database (delete all data).

    WARNING: This is a destructive operation!

    Args:
        request: Reset request with confirmation

    Returns:
        Reset statistics
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Must confirm reset by setting confirm=true"
        )

    try:
        session = SessionLocal()

        deleted = {
            "households": 0,
            "household_members": 0,
            "qc_errors": 0,
        }

        try:
            # Count records before deletion
            if request.fiscal_years:
                # Delete specific fiscal years
                logger.info(f"Deleting data for fiscal years: {request.fiscal_years}")

                households_query = session.query(Household).filter(
                    Household.fiscal_year.in_(request.fiscal_years)
                )
                deleted["households"] = households_query.count()

                # Get household keys for counting related records
                household_keys = [(h.case_id, h.fiscal_year) for h in households_query.all()]
                case_ids = [k[0] for k in household_keys]
                fy_list = request.fiscal_years

                deleted["household_members"] = session.query(HouseholdMember).filter(
                    HouseholdMember.case_id.in_(case_ids),
                    HouseholdMember.fiscal_year.in_(fy_list)
                ).count()

                deleted["qc_errors"] = session.query(QCError).filter(
                    QCError.case_id.in_(case_ids),
                    QCError.fiscal_year.in_(fy_list)
                ).count()

                # Delete (cascade will handle children)
                households_query.delete(synchronize_session=False)

            else:
                # Delete all data
                logger.info("Deleting ALL data from database")

                deleted["households"] = session.query(Household).count()
                deleted["household_members"] = session.query(HouseholdMember).count()
                deleted["qc_errors"] = session.query(QCError).count()

                # Delete all (cascade will handle children)
                session.query(Household).delete()

            session.commit()

            logger.info(f"Database reset complete: {deleted}")

            return ResetResponse(
                status="success",
                message="Database reset completed" if not request.fiscal_years
                        else f"Data deleted for fiscal years: {request.fiscal_years}",
                deleted=deleted
            )

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reset failed: {e}")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Database health check.

    Returns:
        Health status including database connection and table statistics
    """
    try:
        session = SessionLocal()

        try:
            # Test database connection
            session.execute(text("SELECT 1"))

            # Get table statistics
            households_count = session.query(Household).count()
            members_count = session.query(HouseholdMember).count()
            errors_count = session.query(QCError).count()

            # Get database size (PostgreSQL specific)
            try:
                result = session.execute(
                    text("SELECT pg_database_size(current_database())")
                ).scalar()
                db_size_mb = result / (1024 * 1024) if result else 0
            except Exception:
                db_size_mb = 0

            # Get PostgreSQL version
            try:
                pg_version = session.execute(text("SELECT version()")).scalar()
                pg_version = pg_version.split(',')[0] if pg_version else "Unknown"
            except Exception:
                pg_version = "Unknown"

            return HealthResponse(
                status="healthy",
                application="SnapAnalyst",
                version=settings.app_version,
                database={
                    "connected": True,
                    "version": pg_version,
                    "size_mb": round(db_size_mb, 2),
                },
                tables={
                    "households": {
                        "row_count": households_count,
                    },
                    "household_members": {
                        "row_count": members_count,
                    },
                    "qc_errors": {
                        "row_count": errors_count,
                    },
                }
            )

        finally:
            session.close()

    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "application": "SnapAnalyst",
                "version": settings.app_version,
                "database": {
                    "connected": False,
                    "error": str(e),
                },
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")


@router.get("/stats")
async def get_statistics():
    """
    Get database statistics with clarified metrics.

    Returns:
        Summary statistics across all data with proper context
    """
    try:
        session = SessionLocal()

        try:
            # Get fiscal years present (fast query)
            fiscal_years_query = session.query(Household.fiscal_year).distinct()
            fiscal_years = sorted([fy[0] for fy in fiscal_years_query.all() if fy[0]])

            # Overall counts - use func.count() for speed (only counts, doesn't load data)
            total_households = session.query(func.count()).select_from(Household).scalar()
            total_members = session.query(func.count()).select_from(HouseholdMember).scalar()
            total_error_records = session.query(func.count()).select_from(QCError).scalar()

            # QC Error breakdown - optimized
            households_with_errors = session.query(
                func.count(func.distinct(QCError.case_id))
            ).scalar() or 0

            households_without_errors = total_households - households_with_errors

            # By fiscal year - optimized with func.count()
            by_year = []
            for fy in fiscal_years:
                households = session.query(func.count()).select_from(Household).filter(
                    Household.fiscal_year == fy
                ).scalar()

                by_year.append({
                    "fiscal_year": fy,
                    "households": households,
                })

            # Count discovered tables and views (same config-driven logic as DDL training)
            table_counts = {}
            try:
                from src.database.ddl_extractor import discover_tables_and_views
                tables, views = discover_tables_and_views()
                core_snap_tables = {"households", "household_members", "qc_errors"}
                ref_tables = [t for t in tables if t.startswith('ref_')]
                core_tables = [t for t in tables if t in core_snap_tables]
                custom_tables = [t for t in tables if t not in core_snap_tables and not t.startswith('ref_')]
                table_counts = {
                    "total_tables": len(tables),
                    "core_tables": len(core_tables),
                    "reference_tables": len(ref_tables),
                    "custom_tables": len(custom_tables),
                    "custom_table_names": sorted(custom_tables),
                    "views": len(views),
                }
            except Exception as e:
                logger.warning(f"Could not count tables: {e}")

            return {
                "summary": {
                    "total_households": total_households,
                    "total_members": total_members,
                    "total_qc_errors": total_error_records,
                    "households_with_errors": households_with_errors,
                    "households_without_errors": households_without_errors,
                    "fiscal_years": fiscal_years,
                    **table_counts,
                },
                "by_fiscal_year": by_year,
                "last_load": None,  # TODO: Track last load timestamp
            }

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {e}")
