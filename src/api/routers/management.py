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

logger = get_logger(__name__)

router = APIRouter(tags=["management"])


def _get_dataset_models() -> tuple:
    """Get active dataset info and model classes.

    Returns:
        (display_name, main_table_names, model_classes_dict)
    """
    from datasets import get_active_dataset

    ds = get_active_dataset()
    if ds:
        return ds.display_name, ds.get_main_table_names(), ds.get_model_classes()
    # Fallback
    from src.database.models import Household, HouseholdMember, QCError

    return "SnapAnalyst", ["households", "household_members", "qc_errors"], {
        "households": Household, "household_members": HouseholdMember, "qc_errors": QCError,
    }


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
        raise HTTPException(status_code=400, detail="Must confirm reset by setting confirm=true")

    try:
        _, table_names, model_classes = _get_dataset_models()
        session = SessionLocal()

        deleted = dict.fromkeys(table_names, 0)

        try:
            # The first table is the parent (cascade deletes children)
            parent_table = table_names[0] if table_names else None
            ParentModel = model_classes.get(parent_table) if parent_table else None

            if request.fiscal_years and ParentModel and hasattr(ParentModel, "fiscal_year"):
                # Delete specific fiscal years
                logger.info(f"Deleting data for fiscal years: {request.fiscal_years}")

                parent_query = session.query(ParentModel).filter(ParentModel.fiscal_year.in_(request.fiscal_years))
                deleted[parent_table] = parent_query.count()

                # Get parent keys for counting related records
                parent_keys = [(h.case_id, h.fiscal_year) for h in parent_query.all()]
                case_ids = [k[0] for k in parent_keys]
                fy_list = request.fiscal_years

                for name in table_names[1:]:
                    Model = model_classes.get(name)
                    if Model and hasattr(Model, "case_id") and hasattr(Model, "fiscal_year"):
                        deleted[name] = (
                            session.query(Model)
                            .filter(Model.case_id.in_(case_ids), Model.fiscal_year.in_(fy_list))
                            .count()
                        )

                # Delete (cascade will handle children)
                parent_query.delete(synchronize_session=False)

            else:
                # Delete all data
                logger.info("Deleting ALL data from database")

                for name in table_names:
                    Model = model_classes.get(name)
                    if Model:
                        deleted[name] = session.query(Model).count()

                # Delete parent (cascade will handle children)
                if ParentModel:
                    session.query(ParentModel).delete()

            session.commit()

            logger.info(f"Database reset complete: {deleted}")

            return ResetResponse(
                status="success",
                message="Database reset completed"
                if not request.fiscal_years
                else f"Data deleted for fiscal years: {request.fiscal_years}",
                deleted=deleted,
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
    ds_name, table_names, model_classes = _get_dataset_models()

    try:
        session = SessionLocal()

        try:
            # Test database connection
            session.execute(text("SELECT 1"))

            # Get table statistics dynamically
            tables_info = {}
            for name in table_names:
                Model = model_classes.get(name)
                if Model:
                    tables_info[name] = {"row_count": session.query(Model).count()}

            # Get database size (PostgreSQL specific)
            try:
                result = session.execute(text("SELECT pg_database_size(current_database())")).scalar()
                db_size_mb = result / (1024 * 1024) if result else 0
            except Exception:
                db_size_mb = 0

            # Get PostgreSQL version
            try:
                pg_version = session.execute(text("SELECT version()")).scalar()
                pg_version = pg_version.split(",")[0] if pg_version else "Unknown"
            except Exception:
                pg_version = "Unknown"

            return HealthResponse(
                status="healthy",
                application=ds_name,
                version=settings.app_version,
                database={
                    "connected": True,
                    "version": pg_version,
                    "size_mb": round(db_size_mb, 2),
                },
                tables=tables_info,
            )

        finally:
            session.close()

    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "application": ds_name,
                "version": settings.app_version,
                "database": {
                    "connected": False,
                    "error": str(e),
                },
            },
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
    _, table_names, model_classes = _get_dataset_models()

    try:
        session = SessionLocal()

        try:
            # Use the first model (parent table) for fiscal year and per-year breakdown
            ParentModel = model_classes.get(table_names[0]) if table_names else None

            # Get fiscal years present (fast query)
            fiscal_years = []
            if ParentModel and hasattr(ParentModel, "fiscal_year"):
                fiscal_years_query = session.query(ParentModel.fiscal_year).distinct()
                fiscal_years = sorted([fy[0] for fy in fiscal_years_query.all() if fy[0]])

            # Overall counts for each table
            totals = {}
            for name in table_names:
                Model = model_classes.get(name)
                if Model:
                    totals[name] = session.query(func.count()).select_from(Model).scalar()

            # Error breakdown (if error table exists)
            ErrorModel = model_classes.get(table_names[2]) if len(table_names) > 2 else None
            parent_total = totals.get(table_names[0], 0) if table_names else 0
            households_with_errors = 0
            if ErrorModel and hasattr(ErrorModel, "case_id"):
                households_with_errors = session.query(func.count(func.distinct(ErrorModel.case_id))).scalar() or 0

            # By fiscal year
            by_year = []
            if ParentModel and hasattr(ParentModel, "fiscal_year"):
                for fy in fiscal_years:
                    count = (
                        session.query(func.count())
                        .select_from(ParentModel)
                        .filter(ParentModel.fiscal_year == fy)
                        .scalar()
                    )
                    by_year.append({"fiscal_year": fy, table_names[0]: count})

            # Count discovered tables and views
            core_table_set = set(table_names)
            table_counts = {}
            try:
                from src.database.ddl_extractor import discover_tables_and_views

                tables, views = discover_tables_and_views()
                ref_tables = [t for t in tables if t.startswith("ref_")]
                core_tables = [t for t in tables if t in core_table_set]
                # Built-in tables that ship with the schema but aren't in the core 3
                builtin_extras = {"fns_error_rates_historical"}
                custom_tables = [
                    t for t in tables
                    if t not in core_table_set and not t.startswith("ref_") and t not in builtin_extras
                ]
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

            # Build summary with dynamic table total keys
            summary = {f"total_{name}": totals.get(name, 0) for name in table_names}
            summary["households_with_errors"] = households_with_errors
            summary["households_without_errors"] = parent_total - households_with_errors
            summary["fiscal_years"] = fiscal_years
            summary.update(table_counts)

            return {
                "summary": summary,
                "by_fiscal_year": by_year,
                "last_load": None,
            }

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {e}")
