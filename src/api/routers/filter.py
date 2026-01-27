"""
Filter API Router

Provides endpoints to manage application-level data filters.
Filters apply globally to all queries and exports.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.core.filter_manager import get_filter_manager
from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class FilterResponse(BaseModel):
    """Response model for filter operations."""
    status: str
    message: str
    filter: dict


class FilterSetRequest(BaseModel):
    """Request to set filter."""
    state: str | None = Field(None, description="State name (e.g., 'Connecticut')")
    fiscal_year: int | None = Field(None, description="Fiscal year (e.g., 2023)")


class AvailableOptionsResponse(BaseModel):
    """Available filter options."""
    states: list[str]
    fiscal_years: list[int]


@router.get("/", summary="Get current filter")
async def get_filter() -> dict:
    """
    Get current application-level filter.

    Returns:
        Current filter settings

    Example:
        ```bash
        curl http://localhost:8000/api/v1/filter/
        ```
    """
    manager = get_filter_manager()
    current_filter = manager.get_filter()

    return {
        "filter": current_filter.to_dict(),
        "description": current_filter.get_description(),
        "is_active": current_filter.is_active,
        "sql_conditions": current_filter.get_sql_conditions(),
    }


@router.post("/set", response_model=FilterResponse, summary="Set filter")
async def set_filter(request: FilterSetRequest):
    """
    Set application-level filter.

    Args:
        request: Filter settings (state and/or fiscal_year)

    Returns:
        Updated filter settings

    Examples:
        ```bash
        # Set state filter
        curl -X POST http://localhost:8000/api/v1/filter/set \\
             -H "Content-Type: application/json" \\
             -d '{"state": "Connecticut"}'

        # Set year filter
        curl -X POST http://localhost:8000/api/v1/filter/set \\
             -H "Content-Type: application/json" \\
             -d '{"fiscal_year": 2023}'

        # Set both
        curl -X POST http://localhost:8000/api/v1/filter/set \\
             -H "Content-Type: application/json" \\
             -d '{"state": "Connecticut", "fiscal_year": 2023}'
        ```
    """
    try:
        manager = get_filter_manager()
        updated_filter = manager.set_filter(
            state=request.state,
            fiscal_year=request.fiscal_year
        )

        return FilterResponse(
            status="success",
            message=f"Filter set: {updated_filter.get_description()}",
            filter=updated_filter.to_dict()
        )

    except Exception as e:
        logger.error(f"Error setting filter: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set filter: {str(e)}")


@router.post("/clear", response_model=FilterResponse, summary="Clear filter")
async def clear_filter():
    """
    Clear all filters (reset to showing all data).

    Returns:
        Cleared filter settings

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/filter/clear
        ```
    """
    try:
        manager = get_filter_manager()
        cleared_filter = manager.clear()

        return FilterResponse(
            status="success",
            message="Filter cleared - showing all data",
            filter=cleared_filter.to_dict()
        )

    except Exception as e:
        logger.error(f"Error clearing filter: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear filter: {str(e)}")


@router.get("/options", response_model=AvailableOptionsResponse, summary="Get available filter options")
async def get_filter_options():
    """
    Get available states and fiscal years for filtering.

    Returns:
        Lists of available states and fiscal years from database

    Example:
        ```bash
        curl http://localhost:8000/api/v1/filter/options
        ```
    """
    try:
        from sqlalchemy import distinct

        from src.database.engine import SessionLocal
        from src.database.models import Household

        session = SessionLocal()

        try:
            # Get distinct states (ordered alphabetically)
            states_query = session.query(distinct(Household.state_name)).filter(
                Household.state_name.isnot(None)
            ).order_by(Household.state_name)

            states = [s[0] for s in states_query.all()]

            # Get distinct fiscal years (ordered)
            years_query = session.query(distinct(Household.fiscal_year)).filter(
                Household.fiscal_year.isnot(None)
            ).order_by(Household.fiscal_year)

            fiscal_years = [y[0] for y in years_query.all()]

            return AvailableOptionsResponse(
                states=states,
                fiscal_years=fiscal_years
            )

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error getting filter options: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get options: {str(e)}")


@router.get("/test-sql", summary="Test SQL filter application")
async def test_sql_filter(
    sql: str = Query(..., description="SQL query to test filter on")
) -> dict:
    """
    Test how filter would be applied to a SQL query.

    Useful for debugging and verifying filter behavior.

    Args:
        sql: SQL query to test

    Returns:
        Original and filtered SQL

    Example:
        ```bash
        curl "http://localhost:8000/api/v1/filter/test-sql?sql=SELECT * FROM households"
        ```
    """
    manager = get_filter_manager()
    current_filter = manager.get_filter()
    filtered_sql = manager.apply_to_sql(sql)

    return {
        "original_sql": sql,
        "filtered_sql": filtered_sql,
        "filter": current_filter.to_dict(),
        "filter_applied": sql != filtered_sql,
        "conditions_added": current_filter.get_sql_conditions(),
    }
