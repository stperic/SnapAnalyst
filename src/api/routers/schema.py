"""
Schema Router - Exposes database schema and data mapping information

Provides endpoints to access:
- Complete data mapping schema (dynamically generated from database)
- Schema documentation
- Table structures
- Code lookups (element codes, nature codes, etc.)
- Table relationships

Note: Export endpoints (CSV, PDF, Markdown) are in schema_exports.py
"""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from src.api.utils.schema_introspection import SchemaIntrospector
from src.core.logging import get_logger
from src.database.engine import engine

logger = get_logger(__name__)
router = APIRouter()

# Paths to schema files (now in datasets/snap/)
WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
DATA_MAPPING_PATH = WORKSPACE_ROOT / "datasets" / "snap" / "data_mapping.json"
SCHEMA_DOCS_PATH = WORKSPACE_ROOT / "schema_documentation.json"


def get_introspector() -> SchemaIntrospector:
    """Get a fresh schema introspector instance for each request."""
    return SchemaIntrospector(engine)


def load_json_file(file_path: Path) -> dict[str, Any]:
    """Load and parse a JSON file."""
    try:
        with open(file_path, encoding="utf-8") as f:
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
async def schema_root() -> dict[str, Any]:
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
async def get_data_mapping() -> dict[str, Any]:
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
async def get_schema_documentation() -> dict[str, Any]:
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
async def get_tables() -> dict[str, Any]:
    """
    Get all table structures (dynamically from database).

    Returns:
    - households: Core household case data
    - household_members: Individual member data
    - qc_errors: Quality control errors/variances

    Each table includes:
    - Actual columns from database
    - Data types
    - Primary keys and foreign keys
    - Row counts (live from database)
    - Indexes
    """
    logger.info("Fetching table structures from database")

    # Get dynamic schema from database
    introspector = get_introspector()
    tables = introspector.get_all_tables()

    # Get static metadata for enrichment
    try:
        static_metadata = load_json_file(DATA_MAPPING_PATH)

        # Enrich with descriptions from static file
        for table_name, table_info in tables.items():
            static_table = static_metadata.get("tables", {}).get(table_name, {})
            table_info["description"] = static_table.get("description", "")

            # Enrich columns with descriptions
            static_columns = static_table.get("columns", {})
            for col_name, col_info in table_info.get("columns", {}).items():
                if col_name in static_columns:
                    static_col = static_columns[col_name]
                    col_info["description"] = static_col.get("description", "")
                    col_info["range"] = static_col.get("range", "")
                    col_info["example"] = static_col.get("example", "")
    except Exception as e:
        logger.warning(f"Could not load static metadata: {e}")

    return {
        "tables": tables,
        "relationships": introspector.get_table_relationships(),
        "source": "database (live introspection)"
    }


@router.get("/tables/{table_name}", summary="Get specific table structure")
async def get_table(table_name: str) -> dict[str, Any]:
    """
    Get structure for a specific table (dynamically from database).

    Available tables:
    - `households`: Core household case data
    - `household_members`: Individual household member data
    - `qc_errors`: Quality control errors and variances

    Returns detailed information about the table including all columns,
    data types, primary keys, foreign keys, and row counts from the live database.
    """
    logger.info(f"Fetching table structure for: {table_name} from database")

    # Get table structure from database
    introspector = get_introspector()
    try:
        table_info = introspector.get_table_structure(table_name)
    except Exception as e:
        logger.error(f"Error introspecting table {table_name}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not found in database"
        )

    # Enrich with static metadata
    try:
        static_metadata = load_json_file(DATA_MAPPING_PATH)
        static_table = static_metadata.get("tables", {}).get(table_name, {})

        table_info["description"] = static_table.get("description", "")
        table_info["common_queries"] = static_table.get("common_queries", [])

        # Enrich columns
        static_columns = static_table.get("columns", {})
        for col_name, col_info in table_info.get("columns", {}).items():
            if col_name in static_columns:
                static_col = static_columns[col_name]
                col_info["description"] = static_col.get("description", "")
                col_info["range"] = static_col.get("range", "")
                col_info["example"] = static_col.get("example", "")
    except Exception as e:
        logger.warning(f"Could not load static metadata: {e}")

    return {
        "table_name": table_name,
        **table_info,
        "source": "database (live introspection)"
    }


@router.get("/code-lookups", summary="Get all code lookup tables")
async def get_code_lookups() -> dict[str, Any]:
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
async def get_code_lookup(lookup_name: str) -> dict[str, Any]:
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
async def get_relationships() -> dict[str, Any]:
    """
    Get table relationships (dynamically from database foreign keys).

    Returns information about how tables are related:
    - households_to_members: One household has 1-17 members
    - households_to_errors: One household has 0-9 QC errors

    Includes join conditions discovered from database foreign key constraints.
    """
    logger.info("Fetching table relationships from database")

    # Get relationships from database
    introspector = get_introspector()
    relationships = introspector.get_table_relationships()

    # Enrich with static metadata if available
    try:
        static_metadata = load_json_file(DATA_MAPPING_PATH)
        static_relationships = static_metadata.get("relationships", {})

        # Add descriptions and examples from static metadata
        for rel_name, rel_info in relationships.items():
            if rel_name in static_relationships:
                static_rel = static_relationships[rel_name]
                rel_info["description"] = static_rel.get("description", "")
                rel_info["example_query"] = static_rel.get("example_query", "")
    except Exception as e:
        logger.warning(f"Could not load static metadata: {e}")

    return {
        "relationships": relationships,
        "description": "How tables are connected via foreign keys",
        "source": "database (live introspection)"
    }


@router.get("/database-info", summary="Get database metadata")
async def get_database_info() -> dict[str, Any]:
    """
    Get high-level database information (dynamically from database).

    Returns:
    - Database name and connection info
    - PostgreSQL version
    - Table count and total rows
    - Live statistics from the database
    """
    logger.info("Fetching database metadata from database")

    # Get dynamic database info
    introspector = get_introspector()
    db_info = introspector.get_database_info()

    # Enrich with static metadata
    try:
        static_metadata = load_json_file(DATA_MAPPING_PATH)
        static_db = static_metadata.get("database", {})

        db_info["description"] = static_db.get("description", "")
        db_info["purpose"] = static_db.get("purpose", "")
        db_info["data_source"] = static_db.get("data_source", "")
        db_info["fiscal_years_available"] = static_db.get("fiscal_years_available", [])
    except Exception as e:
        logger.warning(f"Could not load static metadata: {e}")

    return {
        "database": db_info,
        "source": "database (live introspection)"
    }


@router.get("/query-tips", summary="Get query writing tips")
async def get_query_tips() -> dict[str, Any]:
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
