"""
Schema Export Router

Endpoints for exporting schema documentation to various formats:
- CSV
- PDF
- Markdown

Separated from main schema.py for cleaner organization.
"""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from src.api.utils.schema_export import SchemaExporter
from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["schema-export"])

WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent


def _get_data_mapping_path() -> Path:
    """Get data_mapping.json path from active dataset."""
    from datasets import get_active_dataset

    ds = get_active_dataset()
    if ds:
        return ds.get_data_mapping_path()
    return WORKSPACE_ROOT / "datasets" / "snap" / "data_mapping.json"


def _get_export_prefix() -> str:
    """Get export filename prefix from active dataset."""
    from datasets import get_active_dataset

    ds = get_active_dataset()
    return ds.get_export_prefix() if ds else "snapanalyst"


def load_json_file(file_path: Path) -> dict[str, Any]:
    """Load and parse a JSON file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Schema file not found: {file_path}")
        raise HTTPException(status_code=404, detail=f"Schema file not found: {file_path.name}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in schema file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON in schema file: {file_path.name}")


# ============================================================================
# TABLE EXPORTS
# ============================================================================


@router.get("/tables/csv", summary="Export all tables to CSV")
async def export_tables_csv():
    """
    Export all table structures to CSV format.

    Returns a CSV file with columns:
    - Table Name
    - Column Name
    - Type
    - Description
    - Nullable
    - Range
    - Example

    **Usage:**
    ```bash
    curl http://localhost:8000/api/v1/schema/export/tables/csv -o tables.csv
    ```
    """
    logger.info("Exporting tables to CSV")
    try:
        data_mapping = load_json_file(_get_data_mapping_path())
        buffer = SchemaExporter.to_csv_buffer(data_mapping, "tables")

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={_get_export_prefix()}_tables.csv"},
        )
    except Exception as e:
        logger.error(f"Error exporting tables to CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/pdf", summary="Export all tables to PDF")
async def export_tables_pdf():
    """
    Export all table structures to PDF format.

    Returns a formatted PDF document with:
    - Table descriptions
    - Column definitions
    - Metadata

    **Usage:**
    ```bash
    curl http://localhost:8000/api/v1/schema/export/tables/pdf -o tables.pdf
    ```
    """
    logger.info("Exporting tables to PDF")
    try:
        data_mapping = load_json_file(_get_data_mapping_path())
        buffer = SchemaExporter.to_pdf_buffer(data_mapping, "tables")

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={_get_export_prefix()}_tables.pdf"},
        )
    except Exception as e:
        logger.error(f"Error exporting tables to PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/markdown", summary="Export all tables to Markdown")
async def export_tables_markdown():
    """
    Export all table structures to Markdown format.

    Returns a Markdown document with:
    - Table descriptions
    - Column tables
    - Formatted for GitHub/GitLab

    **Usage:**
    ```bash
    curl http://localhost:8000/api/v1/schema/export/tables/markdown -o tables.md
    ```
    """
    logger.info("Exporting tables to Markdown")
    try:
        data_mapping = load_json_file(_get_data_mapping_path())
        markdown = SchemaExporter.to_markdown(data_mapping, "tables")

        return Response(
            content=markdown,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={_get_export_prefix()}_tables.md"},
        )
    except Exception as e:
        logger.error(f"Error exporting tables to Markdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CODE LOOKUP EXPORTS
# ============================================================================


@router.get("/code-lookups/csv", summary="Export code lookups to CSV")
async def export_code_lookups_csv():
    """
    Export all code lookup tables to CSV format.

    Returns a CSV file with columns:
    - Lookup Name
    - Code
    - Description

    **Usage:**
    ```bash
    curl http://localhost:8000/api/v1/schema/export/code-lookups/csv -o code_lookups.csv
    ```
    """
    logger.info("Exporting code lookups to CSV")
    try:
        data_mapping = load_json_file(_get_data_mapping_path())
        buffer = SchemaExporter.to_csv_buffer(data_mapping, "code_lookups")

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={_get_export_prefix()}_code_lookups.csv"},
        )
    except Exception as e:
        logger.error(f"Error exporting code lookups to CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/code-lookups/pdf", summary="Export code lookups to PDF")
async def export_code_lookups_pdf():
    """
    Export all code lookup tables to PDF format.

    Returns a formatted PDF document with:
    - Lookup descriptions
    - Code-to-description mappings
    - Source field information

    **Usage:**
    ```bash
    curl http://localhost:8000/api/v1/schema/export/code-lookups/pdf -o code_lookups.pdf
    ```
    """
    logger.info("Exporting code lookups to PDF")
    try:
        data_mapping = load_json_file(_get_data_mapping_path())
        buffer = SchemaExporter.to_pdf_buffer(data_mapping, "code_lookups")

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={_get_export_prefix()}_code_lookups.pdf"},
        )
    except Exception as e:
        logger.error(f"Error exporting code lookups to PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/code-lookups/markdown", summary="Export code lookups to Markdown")
async def export_code_lookups_markdown():
    """
    Export all code lookup tables to Markdown format.

    Returns a Markdown document with:
    - Lookup descriptions
    - Code tables
    - Formatted for GitHub/GitLab

    **Usage:**
    ```bash
    curl http://localhost:8000/api/v1/schema/export/code-lookups/markdown -o code_lookups.md
    ```
    """
    logger.info("Exporting code lookups to Markdown")
    try:
        data_mapping = load_json_file(_get_data_mapping_path())
        markdown = SchemaExporter.to_markdown(data_mapping, "code_lookups")

        return Response(
            content=markdown,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={_get_export_prefix()}_code_lookups.md"},
        )
    except Exception as e:
        logger.error(f"Error exporting code lookups to Markdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# OTHER EXPORTS
# ============================================================================


@router.get("/database-info/pdf", summary="Export database info to PDF")
async def export_database_info_pdf():
    """
    Export database information to PDF format.

    Returns a formatted PDF document with:
    - Database name and version
    - Description and purpose
    - Available fiscal years
    - Data source information

    **Usage:**
    ```bash
    curl http://localhost:8000/api/v1/schema/export/database-info/pdf -o database_info.pdf
    ```
    """
    logger.info("Exporting database info to PDF")
    try:
        data_mapping = load_json_file(_get_data_mapping_path())
        buffer = SchemaExporter.to_pdf_buffer(data_mapping, "database_info")

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={_get_export_prefix()}_database_info.pdf"},
        )
    except Exception as e:
        logger.error(f"Error exporting database info to PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relationships/csv", summary="Export relationships to CSV")
async def export_relationships_csv():
    """
    Export table relationships to CSV format.

    Returns a CSV file with columns:
    - Relationship
    - Type
    - Description
    - Join Condition

    **Usage:**
    ```bash
    curl http://localhost:8000/api/v1/schema/export/relationships/csv -o relationships.csv
    ```
    """
    logger.info("Exporting relationships to CSV")
    try:
        data_mapping = load_json_file(_get_data_mapping_path())
        buffer = SchemaExporter.to_csv_buffer(data_mapping, "relationships")

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={_get_export_prefix()}_relationships.csv"},
        )
    except Exception as e:
        logger.error(f"Error exporting relationships to CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))
