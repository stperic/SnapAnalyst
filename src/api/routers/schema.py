"""
Schema Router - Exposes database schema and data mapping information

Provides endpoints to access:
- Complete data mapping schema
- Schema documentation  
- Table structures
- Code lookups (element codes, nature codes, etc.)
- Table relationships

Note: Export endpoints (CSV, PDF, Markdown) are in schema_exports.py
"""

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Paths to schema files (now in datasets/snap/)
WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
DATA_MAPPING_PATH = WORKSPACE_ROOT / "datasets" / "snap" / "data_mapping.json"
SCHEMA_DOCS_PATH = WORKSPACE_ROOT / "schema_documentation.json"


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Schema file not found: {file_path}")
        raise HTTPException(
            status_code=404,
            detail=f"Schema file not found: {file_path.name}"
        )
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in schema file {file_path}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON in schema file: {file_path.name}"
        )


# ============================================================================
# SCHEMA QUERY ENDPOINTS
# ============================================================================

@router.get("/", summary="Schema API information")
async def schema_root() -> Dict[str, Any]:
    """
    Get information about the Schema API.
    
    Returns a list of available endpoints and their purposes.
    """
    return {
        "name": "SnapAnalyst Schema API",
        "description": "Access database schema, data mappings, and code lookups",
        "endpoints": {
            "/data-mapping": "Complete data mapping schema with all tables, columns, and codes",
            "/documentation": "Schema documentation",
            "/tables": "All table structures",
            "/tables/{table_name}": "Specific table structure (households, household_members, qc_errors)",
            "/code-lookups": "All code lookup tables",
            "/code-lookups/{lookup_name}": "Specific code lookup table",
            "/relationships": "Table relationships and join conditions",
            "/database-info": "High-level database metadata",
            "/query-tips": "Tips for writing SQL queries",
        },
        "export_endpoints": {
            "/export/tables/csv": "Export all tables to CSV",
            "/export/tables/pdf": "Export all tables to PDF",
            "/export/tables/markdown": "Export all tables to Markdown",
            "/export/code-lookups/csv": "Export code lookups to CSV",
            "/export/code-lookups/pdf": "Export code lookups to PDF",
            "/export/code-lookups/markdown": "Export code lookups to Markdown",
            "/export/database-info/pdf": "Export database info to PDF"
        },
        "available_tables": ["households", "household_members", "qc_errors"],
        "available_code_lookups": [
            "case_classification_codes",
            "status_codes",
            "expedited_service_codes",
            "categorical_eligibility_codes",
            "error_finding_codes",
            "sex_codes",
            "snap_affiliation_codes",
            "element_codes",
            "nature_codes",
            "agency_responsibility_codes",
            "discovery_method_codes"
        ]
    }


@router.get("/data-mapping", summary="Get complete data mapping schema")
async def get_data_mapping() -> Dict[str, Any]:
    """
    Get the complete data mapping schema.
    
    Returns comprehensive information about:
    - Database structure and purpose
    - All tables (households, household_members, qc_errors)
    - Column definitions with types, ranges, examples, and source fields
    - Code lookup tables (status codes, error codes, etc.)
    - Table relationships
    - Common query examples
    - Tips for writing queries
    
    **Use this endpoint to understand:**
    - What data is available
    - How tables are structured
    - What each field means
    - Valid code values and their meanings
    """
    logger.info("Fetching complete data mapping schema")
    return load_json_file(DATA_MAPPING_PATH)


@router.get("/documentation", summary="Get schema documentation")
async def get_schema_documentation() -> Dict[str, Any]:
    """
    Get the schema documentation.
    
    Returns detailed documentation about the database schema including:
    - Table descriptions
    - Column definitions
    - Code lookups
    - Usage examples
    
    This is a more narrative-focused version of the schema information.
    """
    logger.info("Fetching schema documentation")
    return load_json_file(SCHEMA_DOCS_PATH)


@router.get("/tables", summary="Get table structures")
async def get_tables() -> Dict[str, Any]:
    """
    Get all table structures.
    
    Returns:
    - households: Core household case data
    - household_members: Individual member data
    - qc_errors: Quality control errors/variances
    
    Each table includes:
    - Description and purpose
    - Row counts
    - Primary keys and foreign keys
    - All columns with types, descriptions, ranges, and examples
    - Common query examples
    """
    logger.info("Fetching table structures")
    data_mapping = load_json_file(DATA_MAPPING_PATH)
    
    return {
        "tables": data_mapping.get("tables", {}),
        "relationships": data_mapping.get("relationships", {})
    }


@router.get("/tables/{table_name}", summary="Get specific table structure")
async def get_table(table_name: str) -> Dict[str, Any]:
    """
    Get structure for a specific table.
    
    Available tables:
    - `households`: Core household case data
    - `household_members`: Individual household member data
    - `qc_errors`: Quality control errors and variances
    
    Returns detailed information about the table including all columns,
    data types, value ranges, and example queries.
    """
    logger.info(f"Fetching table structure for: {table_name}")
    data_mapping = load_json_file(DATA_MAPPING_PATH)
    
    tables = data_mapping.get("tables", {})
    if table_name not in tables:
        available = ", ".join(tables.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not found. Available tables: {available}"
        )
    
    return {
        "table_name": table_name,
        **tables[table_name]
    }


@router.get("/code-lookups", summary="Get all code lookup tables")
async def get_code_lookups() -> Dict[str, Any]:
    """
    Get all code lookup tables.
    
    Returns mappings for coded fields including:
    - case_classification_codes: Case classification for error rates
    - status_codes: Case error status (correct, overissuance, underissuance)
    - expedited_service_codes: Expedited service indicators
    - categorical_eligibility_codes: Categorical eligibility status
    - error_finding_codes: Impact of variance on benefits
    - sex_codes: Sex of household member
    - snap_affiliation_codes: SNAP participation status
    - element_codes: Type of variance/error (what area had the problem)
    - nature_codes: Nature of variance (what went wrong)
    - agency_responsibility_codes: Who caused the error (agency vs client)
    - discovery_method_codes: How variance was discovered
    
    **Example**: To understand what status code 2 means, look up status_codes["2"]
    which returns "Overissuance".
    """
    logger.info("Fetching code lookup tables")
    data_mapping = load_json_file(DATA_MAPPING_PATH)
    
    return {
        "code_lookups": data_mapping.get("code_lookups", {}),
        "description": "Code lookup tables for interpreting coded values in the database"
    }


@router.get("/code-lookups/{lookup_name}", summary="Get specific code lookup table")
async def get_code_lookup(lookup_name: str) -> Dict[str, Any]:
    """
    Get a specific code lookup table.
    
    Available lookups:
    - `case_classification_codes`: Case classification values (1-3)
    - `status_codes`: Status values (1=correct, 2=overissuance, 3=underissuance)
    - `expedited_service_codes`: Expedited service status (1-3)
    - `categorical_eligibility_codes`: Categorical eligibility (0-2)
    - `error_finding_codes`: Error impact (2-4)
    - `sex_codes`: Sex values (1-3)
    - `snap_affiliation_codes`: SNAP participation status (1-99)
    - `element_codes`: Error type/area codes (111-820)
    - `nature_codes`: Error nature codes (6-309)
    - `agency_responsibility_codes`: Responsibility codes (1-99)
    - `discovery_method_codes`: Discovery method codes (1-9)
    
    Returns the specific lookup table with code-to-description mappings.
    """
    logger.info(f"Fetching code lookup: {lookup_name}")
    data_mapping = load_json_file(DATA_MAPPING_PATH)
    
    code_lookups = data_mapping.get("code_lookups", {})
    if lookup_name not in code_lookups:
        available = ", ".join(code_lookups.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Code lookup '{lookup_name}' not found. Available lookups: {available}"
        )
    
    return {
        "lookup_name": lookup_name,
        **code_lookups[lookup_name]
    }


@router.get("/relationships", summary="Get table relationships")
async def get_relationships() -> Dict[str, Any]:
    """
    Get table relationships.
    
    Returns information about how tables are related:
    - households_to_members: One household has 1-17 members
    - households_to_errors: One household has 0-9 QC errors
    
    Includes join conditions and example queries.
    """
    logger.info("Fetching table relationships")
    data_mapping = load_json_file(DATA_MAPPING_PATH)
    
    return {
        "relationships": data_mapping.get("relationships", {}),
        "description": "How tables are connected via foreign keys"
    }


@router.get("/database-info", summary="Get database metadata")
async def get_database_info() -> Dict[str, Any]:
    """
    Get high-level database information.
    
    Returns:
    - Database name and description
    - Version
    - Available fiscal years
    - Total record counts
    - Purpose and data source
    """
    logger.info("Fetching database metadata")
    data_mapping = load_json_file(DATA_MAPPING_PATH)
    
    return {
        "database": data_mapping.get("database", {}),
        "tips_for_queries": data_mapping.get("tips_for_queries", [])
    }


@router.get("/query-tips", summary="Get query writing tips")
async def get_query_tips() -> Dict[str, Any]:
    """
    Get tips for writing SQL queries against the database.
    
    Returns best practices and common patterns for:
    - Filtering by fiscal year
    - Using status codes
    - Joining tables
    - Interpreting coded values
    - Calculating benefits and errors
    - Working with weighted data
    """
    logger.info("Fetching query tips")
    data_mapping = load_json_file(DATA_MAPPING_PATH)
    
    return {
        "tips": data_mapping.get("tips_for_queries", []),
        "common_queries": {
            "households": data_mapping.get("tables", {}).get("households", {}).get("common_queries", []),
            "household_members": data_mapping.get("tables", {}).get("household_members", {}).get("common_queries", []),
            "qc_errors": data_mapping.get("tables", {}).get("qc_errors", {}).get("common_queries", [])
        }
    }
