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
        updated_filter = manager.set_filter(state=request.state, fiscal_year=request.fiscal_year)

        return FilterResponse(
            status="success", message=f"Filter set: {updated_filter.get_description()}", filter=updated_filter.to_dict()
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
            status="success", message="Filter cleared - showing all data", filter=cleared_filter.to_dict()
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
        from sqlalchemy import text

        from datasets import get_active_dataset
        from src.database.engine import SessionLocal

        ds = get_active_dataset()
        dimensions = ds.get_filter_dimensions() if ds else []

        session = SessionLocal()

        try:
            states = []
            fiscal_years = []

            for dim in dimensions:
                col = dim["column"]
                table = dim.get("table", "")
                if table == "*":
                    # Use first main table for universal columns
                    table = ds.get_main_table_names()[0] if ds else "households"

                # Validate identifiers to prevent SQL injection (defense-in-depth)
                import re

                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
                    raise HTTPException(status_code=400, detail=f"Invalid column name: {col}")
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table):
                    raise HTTPException(status_code=400, detail=f"Invalid table name: {table}")

                result = session.execute(
                    text(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL ORDER BY {col}")
                )
                values = [row[0] for row in result]

                if dim["name"] == "state":
                    states = values
                elif dim["name"] == "fiscal_year":
                    fiscal_years = values

            return AvailableOptionsResponse(states=states, fiscal_years=fiscal_years)

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error getting filter options: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get options: {str(e)}")


@router.get("/test-sql", summary="Test SQL filter application")
async def test_sql_filter(sql: str = Query(..., description="SQL query to test filter on")) -> dict:
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
