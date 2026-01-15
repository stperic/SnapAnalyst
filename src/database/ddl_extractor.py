"""
DDL Extractor - Query PostgreSQL Schema for Vanna Training

This module extracts the actual DDL from the PostgreSQL database,
making the database itself the single source of truth for schema.

ARCHITECTURE:
- Database schema is the source of truth for table structure
- data_mapping.json is the source of truth for column display formats
- DDL extraction combines both for complete Vanna training

MULTI-DATASET SUPPORT:
- Can extract DDL for specific datasets using their schema
- Dataset configuration provides table lists
- Backward compatible with existing SNAP-specific code

Usage:
    from src.database.ddl_extractor import get_all_ddl_statements
    
    # Default (SNAP dataset)
    ddl_statements = get_all_ddl_statements()
    
    # Specific dataset
    ddl_statements = get_all_ddl_statements(dataset_name='state_private')
    
    for ddl in ddl_statements:
        vanna.train(ddl=ddl)
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.database.engine import engine, get_engine_for_dataset
from src.core.logging import get_logger

logger = get_logger(__name__)

# Path to data mapping configuration (source of truth for column formats)
DATA_MAPPING_PATH = Path(__file__).parent.parent.parent / "datasets" / "snap" / "data_mapping.json"

# Tables to include in DDL extraction (order matters for FK references)
# Reference tables first, then main tables
REFERENCE_TABLES = [
    # Core error analysis tables
    "ref_status",
    "ref_element",
    "ref_nature",
    "ref_agency_responsibility",
    "ref_error_finding",
    "ref_discovery",
    # Geographic
    "ref_state",
    # Demographics
    "ref_sex",
    "ref_snap_affiliation",
    "ref_categorical_eligibility",
    "ref_expedited_service",
    "ref_case_classification",
    # New tables for complete Vanna coverage
    "ref_abawd_status",
    "ref_citizenship_status",
    "ref_race_ethnicity",
    "ref_relationship",
    "ref_work_registration",
    "ref_education_level",
    "ref_employment_status_type",
    "ref_disability",
    "ref_working_indicator",
    "ref_homelessness",
    "ref_reporting_system",
    "ref_action_type",
    "ref_allotment_adjustment",
]

MAIN_TABLES = [
    "households",
    "household_members",
    "qc_errors",
]

# Tables to exclude from training (internal/metadata tables)
EXCLUDED_TABLES = [
    "data_load_history",
    "alembic_version",
]


def get_table_ddl(table_name: str, db_engine: Engine = None) -> Optional[str]:
    """
    Extract DDL for a single table from PostgreSQL.
    
    Uses information_schema to build CREATE TABLE statement with:
    - Column definitions (name, type, nullable)
    - Primary key constraints
    - Foreign key constraints
    - Comments
    
    Args:
        table_name: Name of the table
        db_engine: SQLAlchemy engine (defaults to main engine)
        
    Returns:
        DDL statement as string, or None if table doesn't exist
    """
    if db_engine is None:
        db_engine = engine
    
    with db_engine.connect() as conn:
        # Check if table exists
        check_query = text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = :table_name
            )
        """)
        result = conn.execute(check_query, {"table_name": table_name})
        if not result.scalar():
            logger.warning(f"Table {table_name} does not exist")
            return None
        
        # Get column definitions
        columns_query = text("""
            SELECT 
                c.column_name,
                c.data_type,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                c.is_nullable,
                c.column_default,
                pgd.description as column_comment
            FROM information_schema.columns c
            LEFT JOIN pg_catalog.pg_statio_all_tables st 
                ON c.table_schema = st.schemaname AND c.table_name = st.relname
            LEFT JOIN pg_catalog.pg_description pgd
                ON pgd.objoid = st.relid AND pgd.objsubid = c.ordinal_position
            WHERE c.table_schema = 'public' AND c.table_name = :table_name
            ORDER BY c.ordinal_position
        """)
        columns = conn.execute(columns_query, {"table_name": table_name}).fetchall()
        
        # Get primary key columns
        pk_query = text("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = 'public'
                AND tc.table_name = :table_name
            ORDER BY kcu.ordinal_position
        """)
        pk_columns = [row[0] for row in conn.execute(pk_query, {"table_name": table_name})]
        
        # Get foreign key constraints
        fk_query = text("""
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public'
                AND tc.table_name = :table_name
        """)
        foreign_keys = conn.execute(fk_query, {"table_name": table_name}).fetchall()
        
        # Build DDL
        ddl_lines = [f"CREATE TABLE {table_name} ("]
        
        column_defs = []
        for col in columns:
            col_name = col[0]
            data_type = col[1]
            char_length = col[2]
            num_precision = col[3]
            num_scale = col[4]
            is_nullable = col[5]
            column_comment = col[7]
            
            # Build type string
            if data_type == "character varying":
                type_str = f"VARCHAR({char_length})" if char_length else "VARCHAR"
            elif data_type == "numeric":
                if num_precision and num_scale:
                    type_str = f"DECIMAL({num_precision},{num_scale})"
                else:
                    type_str = "DECIMAL"
            elif data_type == "integer":
                type_str = "INTEGER"
            elif data_type == "boolean":
                type_str = "BOOLEAN"
            elif data_type == "text":
                type_str = "TEXT"
            elif data_type == "timestamp without time zone":
                type_str = "TIMESTAMP"
            elif data_type == "date":
                type_str = "DATE"
            else:
                type_str = data_type.upper()
            
            # Build column definition
            col_def = f"    {col_name} {type_str}"
            
            # Add NOT NULL if applicable
            if is_nullable == "NO" and col_name not in pk_columns:
                col_def += " NOT NULL"
            
            # Add comment if present
            if column_comment:
                col_def += f"  -- {column_comment}"
            
            column_defs.append(col_def)
        
        ddl_lines.append(",\n".join(column_defs))
        
        # Add primary key constraint
        if pk_columns:
            pk_str = f"    PRIMARY KEY ({', '.join(pk_columns)})"
            ddl_lines.append(f",\n{pk_str}")
        
        # Add foreign key constraints
        fk_by_constraint = {}
        for fk in foreign_keys:
            col_name, fk_table, fk_column, constraint_name = fk
            if constraint_name not in fk_by_constraint:
                fk_by_constraint[constraint_name] = {
                    "columns": [],
                    "ref_table": fk_table,
                    "ref_columns": []
                }
            fk_by_constraint[constraint_name]["columns"].append(col_name)
            fk_by_constraint[constraint_name]["ref_columns"].append(fk_column)
        
        for constraint_name, fk_info in fk_by_constraint.items():
            cols = ", ".join(fk_info["columns"])
            ref_table = fk_info["ref_table"]
            ref_cols = ", ".join(fk_info["ref_columns"])
            fk_str = f"    FOREIGN KEY ({cols}) REFERENCES {ref_table}({ref_cols})"
            ddl_lines.append(f",\n{fk_str}")
        
        ddl_lines.append("\n);")
        
        ddl = "\n".join(ddl_lines)
        
        # Add table comment if exists
        table_comment_query = text("""
            SELECT obj_description(oid) 
            FROM pg_class 
            WHERE relname = :table_name AND relkind = 'r'
        """)
        table_comment = conn.execute(table_comment_query, {"table_name": table_name}).scalar()
        if table_comment:
            ddl += f"\n-- {table_comment}"
        
        return ddl


def get_reference_table_ddl_with_sample_data(table_name: str, db_engine: Engine = None) -> Optional[str]:
    """
    Extract DDL for reference table and include sample data as comments.
    
    This helps Vanna understand what values are available in lookup tables.
    
    Args:
        table_name: Name of the reference table
        db_engine: SQLAlchemy engine
        
    Returns:
        DDL with sample data comments
    """
    ddl = get_table_ddl(table_name, db_engine)
    if not ddl:
        return None
    
    if db_engine is None:
        db_engine = engine
    
    # Get sample data (first 10 rows)
    with db_engine.connect() as conn:
        # Check if table has description column
        has_description = False
        check_query = text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = :table_name AND column_name = 'description'
            )
        """)
        has_description = conn.execute(check_query, {"table_name": table_name}).scalar()
        
        if has_description:
            # Get primary key column name
            pk_query = text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_name = :table_name
                LIMIT 1
            """)
            pk_col = conn.execute(pk_query, {"table_name": table_name}).scalar() or "code"
            
            # Get sample data
            sample_query = text(f"""
                SELECT {pk_col}, description 
                FROM {table_name} 
                ORDER BY {pk_col} 
                LIMIT 15
            """)
            try:
                samples = conn.execute(sample_query).fetchall()
                if samples:
                    ddl += "\n-- Sample values:"
                    for code, desc in samples:
                        ddl += f"\n--   {code} = '{desc}'"
            except Exception as e:
                logger.warning(f"Could not get sample data for {table_name}: {e}")
    
    return ddl


def get_all_ddl_statements(
    include_samples: bool = True,
    include_format_docs: bool = True,
    dataset_name: Optional[str] = None
) -> List[str]:
    """
    Get DDL statements for all tables in the correct order.
    
    Reference tables are listed first (for FK dependencies).
    Includes sample data from lookup tables to help Vanna understand values.
    Includes column format documentation from data_mapping.json.
    
    MULTI-DATASET SUPPORT:
    - If dataset_name is provided, uses that dataset's config for table lists
    - Otherwise uses the hardcoded SNAP tables (backward compatible)
    
    Args:
        include_samples: Include sample data from reference tables
        include_format_docs: Include column format documentation
        dataset_name: Optional dataset name for multi-dataset support
        
    Returns:
        List of DDL statements ready for Vanna training
    """
    ddl_statements = []
    
    # Determine which engine and table lists to use
    db_engine = engine  # Default
    reference_tables = REFERENCE_TABLES
    main_tables = MAIN_TABLES
    
    if dataset_name:
        try:
            from datasets import get_dataset
            dataset_config = get_dataset(dataset_name)
            if dataset_config:
                db_engine = get_engine_for_dataset(dataset_name)
                reference_tables = dataset_config.get_reference_table_names()
                main_tables = dataset_config.get_main_table_names()
                logger.info(f"Using dataset config for '{dataset_name}'")
        except ImportError:
            logger.debug("datasets module not available, using defaults")
    
    # First, get reference tables with sample data
    logger.info("Extracting DDL for reference tables...")
    for table_name in reference_tables:
        if include_samples:
            ddl = get_reference_table_ddl_with_sample_data(table_name, db_engine)
        else:
            ddl = get_table_ddl(table_name, db_engine)
        
        if ddl:
            ddl_statements.append(ddl)
            logger.debug(f"Extracted DDL for {table_name}")
        else:
            logger.warning(f"Could not extract DDL for {table_name}")
    
    # Then, get main tables
    logger.info("Extracting DDL for main tables...")
    for table_name in main_tables:
        ddl = get_table_ddl(table_name, db_engine)
        if ddl:
            ddl_statements.append(ddl)
            logger.debug(f"Extracted DDL for {table_name}")
        else:
            logger.warning(f"Could not extract DDL for {table_name}")
    
    # Add column format documentation (sourced from data_mapping.json)
    if include_format_docs:
        format_doc = get_column_format_documentation()
        if format_doc:
            ddl_statements.append(format_doc)
            logger.info("Added column format documentation from data_mapping.json")
    
    logger.info(f"Extracted DDL for {len(ddl_statements)} tables")
    return ddl_statements


def get_ddl_for_dataset(dataset_name: str, include_samples: bool = True) -> List[str]:
    """
    Convenience function to get DDL for a specific dataset.
    
    Args:
        dataset_name: Name of the dataset (e.g., 'snap', 'state_private')
        include_samples: Include sample data from reference tables
        
    Returns:
        List of DDL statements for the dataset
    """
    return get_all_ddl_statements(
        include_samples=include_samples,
        dataset_name=dataset_name
    )


def get_ddl_as_single_string() -> str:
    """
    Get all DDL as a single formatted string.
    
    Useful for debugging or displaying the full schema.
    
    Returns:
        All DDL statements concatenated with separators
    """
    ddl_statements = get_all_ddl_statements()
    return "\n\n-- ----------------------------------------\n\n".join(ddl_statements)


def verify_database_schema() -> Dict[str, bool]:
    """
    Verify that all expected tables exist in the database.
    
    Returns:
        Dict mapping table names to existence status
    """
    status = {}
    all_tables = REFERENCE_TABLES + MAIN_TABLES
    
    with engine.connect() as conn:
        for table_name in all_tables:
            check_query = text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = :table_name
                )
            """)
            exists = conn.execute(check_query, {"table_name": table_name}).scalar()
            status[table_name] = exists
    
    return status


def get_foreign_key_summary() -> List[Dict]:
    """
    Get a summary of all foreign key relationships.
    
    Useful for understanding and documenting relationships.
    
    Returns:
        List of FK relationship dictionaries
    """
    fk_summary = []
    
    with engine.connect() as conn:
        query = text("""
            SELECT
                tc.table_name as from_table,
                kcu.column_name as from_column,
                ccu.table_name AS to_table,
                ccu.column_name AS to_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public'
            ORDER BY tc.table_name, kcu.column_name
        """)
        results = conn.execute(query).fetchall()
        
        for row in results:
            fk_summary.append({
                "from_table": row[0],
                "from_column": row[1],
                "to_table": row[2],
                "to_column": row[3]
            })
    
    return fk_summary


def get_column_format_documentation() -> Optional[str]:
    """
    Generate column format documentation from data_mapping.json.
    
    This documents which columns are integers, currency, weights, etc.
    Sourced from data_mapping.json (single source of truth for formats).
    
    Returns:
        SQL comment block documenting column formats, or None if unavailable
    """
    try:
        if not DATA_MAPPING_PATH.exists():
            logger.warning(f"Data mapping file not found: {DATA_MAPPING_PATH}")
            return None
        
        with open(DATA_MAPPING_PATH, 'r') as f:
            data = json.load(f)
        
        display_formats = data.get("column_display_formats", {})
        if not display_formats:
            logger.debug("No column_display_formats in data mapping")
            return None
        
        lines = [
            "-- =====================================================",
            "-- COLUMN DISPLAY FORMATS (from data_mapping.json)",
            "-- =====================================================",
            "--",
            "-- These formats indicate how columns should be displayed in UI",
            "-- and help understand the semantic meaning of each column.",
            "--",
        ]
        
        for format_type, config in display_formats.items():
            if format_type.startswith("_"):
                continue  # Skip description fields
            if not isinstance(config, dict) or "columns" not in config:
                continue
            
            description = config.get("_description", "")
            columns = config.get("columns", [])
            
            if columns:
                lines.append(f"-- {format_type.upper()} columns ({description}):")
                # Group columns into lines of ~80 chars
                col_line = "--   "
                for col in columns:
                    if len(col_line) + len(col) + 2 > 80:
                        lines.append(col_line.rstrip(", "))
                        col_line = f"--   {col}, "
                    else:
                        col_line += f"{col}, "
                if col_line.strip("-- ,"):
                    lines.append(col_line.rstrip(", "))
                lines.append("--")
        
        lines.extend([
            "-- IMPORTANT NOTES:",
            "-- - case_id is stored as VARCHAR (string), not numeric",
            "-- - Currency columns represent dollar amounts (2 decimal places)",
            "-- - Weight columns are statistical weights (high precision)",
            "-- - Integer columns should display without decimal places",
            "-- ====================================================="
        ])
        
        doc = "\n".join(lines)
        logger.debug("Generated column format documentation from data_mapping.json")
        return doc
        
    except Exception as e:
        logger.error(f"Failed to generate column format documentation: {e}")
        return None


# For backwards compatibility and easy access
DDL_STATEMENTS = None  # Will be populated on first access


def get_cached_ddl_statements() -> List[str]:
    """
    Get DDL statements with caching for performance.
    
    First call queries the database, subsequent calls return cached results.
    """
    global DDL_STATEMENTS
    if DDL_STATEMENTS is None:
        DDL_STATEMENTS = get_all_ddl_statements()
    return DDL_STATEMENTS


def refresh_ddl_cache() -> List[str]:
    """
    Refresh the DDL cache from the database.
    
    Call this after schema changes.
    """
    global DDL_STATEMENTS
    DDL_STATEMENTS = get_all_ddl_statements()
    return DDL_STATEMENTS
