"""
Data Export Router - Export database data to Excel

Provides endpoints to export actual database data (not just schema):
- Complete data export with README
- Filtered by fiscal year
- With row limits for testing
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.utils.data_export import DataExporter
from src.core.logging import get_logger
from src.database.ddl_extractor import discover_tables_and_views
from src.database.engine import get_db

logger = get_logger(__name__)
router = APIRouter()

# Path to data mapping (now in datasets/snap/)
WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
DATA_MAPPING_PATH = WORKSPACE_ROOT / "datasets" / "snap" / "data_mapping.json"

# Default tables to export (backward compatibility)
DEFAULT_TABLES = ["households", "household_members", "qc_errors"]


def _validate_and_parse_tables(tables_param: str | None) -> list[str]:
    """
    Validate and parse tables parameter.

    Args:
        tables_param: Comma-separated table names (e.g., "households,snap_my_table")

    Returns:
        List of valid table names to export

    Raises:
        HTTPException: If any table name is invalid
    """
    # Use default tables if no parameter provided (backward compatibility)
    if not tables_param:
        return DEFAULT_TABLES

    # Parse comma-separated list
    requested_tables = [t.strip() for t in tables_param.split(",") if t.strip()]

    if not requested_tables:
        return DEFAULT_TABLES

    # Discover all valid tables (exclude views - only base tables for export)
    try:
        all_tables, _ = discover_tables_and_views()
    except Exception as e:
        logger.warning(f"Could not discover tables: {e}")
        # Fallback to allowing any table (trust user input)
        return requested_tables

    # Validate each requested table
    invalid_tables = [t for t in requested_tables if t not in all_tables]

    if invalid_tables:
        available_tables_str = ", ".join(sorted(all_tables))
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid table names: {', '.join(invalid_tables)}. "
                f"Available tables: {available_tables_str}"
            )
        )

    return requested_tables


@router.get("/export/excel", summary="Export all data to Excel with README")
async def export_data_to_excel(
    fiscal_year: int | None = Query(None, description="Filter by fiscal year (e.g., 2023)"),
    tables: str | None = Query(None, description="Comma-separated table names (default: households,household_members,qc_errors)"),
    limit: int | None = Query(None, description="Limit rows per table (for testing)"),
    db: Session = Depends(get_db),
):
    """
    Export complete database to Excel format.

    Creates an Excel file with:
    - **README sheet**: Complete documentation, column definitions, code lookups
    - **Data sheets**: Household, member, error data, or custom tables

    **Parameters:**
    - `fiscal_year`: Optional filter (2021, 2022, or 2023)
    - `tables`: Comma-separated table names to export (default: households,household_members,qc_errors)
    - `limit`: Optional row limit per table (useful for testing with small samples)

    **Examples:**
    ```bash
    # Export default tables (backward compatible)
    curl http://localhost:8000/api/v1/data/export/excel -o snapanalyst_data.xlsx

    # Export FY2023 only
    curl "http://localhost:8000/api/v1/data/export/excel?fiscal_year=2023" -o fy2023_data.xlsx

    # Export custom tables
    curl "http://localhost:8000/api/v1/data/export/excel?tables=households,snap_my_table" -o custom_data.xlsx

    # Export first 1000 rows (testing)
    curl "http://localhost:8000/api/v1/data/export/excel?limit=1000" -o sample_data.xlsx
    ```

    **File Structure:**
    - README (opens first) - Complete documentation
    - Data sheets (based on tables parameter)

    **Note:** Large exports may take 10-30 seconds. Consider using `limit` for testing.
    """
    logger.info(f"Exporting data to Excel (fiscal_year={fiscal_year}, tables={tables}, limit={limit})")

    try:
        # Validate and parse tables parameter
        tables_list = _validate_and_parse_tables(tables)
        logger.info(f"Exporting tables: {tables_list}")

        # Check global filter if no explicit parameters provided
        from src.core.filter_manager import get_filter_manager
        filter_manager = get_filter_manager()
        current_filter = filter_manager.get_filter()

        # Use global filter if no explicit parameters
        if fiscal_year is None and current_filter.fiscal_year:
            fiscal_year = current_filter.fiscal_year
            logger.info(f"Applying global fiscal year filter: {fiscal_year}")

        # Note: State filter is applied at SQL level, not at export parameter level
        # The DataExporter queries will automatically include state filter via SQL

        # Create exporter
        exporter = DataExporter(db, DATA_MAPPING_PATH)

        # Generate Excel file with specified tables
        buffer = exporter.create_excel_export(
            tables=tables_list,
            fiscal_year=fiscal_year,
            limit=limit
        )

        # Generate filename
        filename_parts = ["snapanalyst_data"]
        if current_filter.state:
            # Add state to filename if filtered
            state_short = current_filter.state.replace(" ", "_")[:10]
            filename_parts.append(state_short.lower())
        if fiscal_year:
            filename_parts.append(f"fy{fiscal_year}")
        if limit:
            filename_parts.append(f"sample{limit}")
        filename = "_".join(filename_parts) + ".xlsx"

        logger.info(f"Excel export complete: {filename}")

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        logger.error(f"Error exporting data to Excel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/", summary="Data export API information")
async def data_export_root():
    """
    Get information about the Data Export API.

    Returns available endpoints and usage examples.
    """
    return {
        "name": "SnapAnalyst Data Export API",
        "description": "Export database data to Excel with comprehensive README",
        "endpoints": {
            "/export/excel": "Export complete data to Excel with README"
        },
        "features": [
            "README sheet with complete documentation",
            "Data sheets (households, members, errors)",
            "Column definitions and descriptions",
            "Code lookup tables",
            "Professional formatting",
            "Optional fiscal year filtering",
            "Optional row limits for testing"
        ],
        "examples": {
            "all_data": "GET /export/excel",
            "fiscal_year_2023": "GET /export/excel?fiscal_year=2023",
            "sample_1000": "GET /export/excel?limit=1000",
            "fy2023_sample": "GET /export/excel?fiscal_year=2023&limit=1000"
        },
        "note": "Large exports may take 10-30 seconds. Use 'limit' parameter for testing."
    }
