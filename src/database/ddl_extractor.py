"""
DDL Extractor - Query PostgreSQL Schema for Vanna Training

This module extracts the actual DDL from the PostgreSQL database,
making the database itself the single source of truth for schema.

SCHEMA ORGANIZATION:
- public: SNAP QC domain data (households, members, errors, reference tables)
- app: Application/system data (user prompts, load history) - NOT trained
- Custom schemas: User-created datasets (e.g., state_ca, custom_data)

MULTI-DATASET SUPPORT:
- Automatically discovers all user schemas (excludes system schemas)
- Extracts DDL per schema/dataset
- Stores each dataset separately in ChromaDB with metadata
- SNAP QC (public schema) = default dataset

Usage:
    from src.database.ddl_extractor import get_ddl_for_all_datasets

    # Get DDL for all datasets (public + custom schemas)
    datasets = get_ddl_for_all_datasets()
    # Returns: {'snap_qc': [...ddl...], 'state_ca': [...ddl...]}

    # Train Vanna on each dataset
    for dataset_name, ddl_statements in datasets.items():
        for ddl in ddl_statements:
            vanna.train(ddl=ddl, metadata={"dataset": dataset_name})
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.core.logging import get_logger
from src.database.engine import engine

logger = get_logger(__name__)

# Path to data mapping configuration (source of truth for column formats)
DATA_MAPPING_PATH = Path(__file__).parent.parent.parent / "datasets" / "snap" / "data_mapping.json"

# =============================================================================
# NAMING CONVENTIONS FOR CUSTOM DATA
# =============================================================================
# Users can extend SnapAnalyst by following these naming conventions:
#
# Tables:
#   ref_*  - Reference/lookup tables (e.g., ref_state, ref_status)
#   snap_* - Custom SNAP-related tables (e.g., snap_my_analysis)
#   Core tables (households, household_members, qc_errors) - backwards compatibility
#
# Views:
#   v_*      - System and custom views (e.g., v_households_enriched)
#   snap_v_* - Alternative custom view prefix (e.g., snap_v_summary)
#
# Tables/views following these conventions are automatically discovered and
# included in Vanna AI training.
# =============================================================================

# Core SNAP QC tables (for backwards compatibility)
CORE_SNAP_TABLES = [
    "households",
    "household_members",
    "qc_errors",
]

# Tables to exclude from training (internal/metadata tables)
EXCLUDED_TABLES = [
    "data_load_history",  # App metadata
    "alembic_version",    # Migration history
]

# Table name prefixes to exclude (system tables)
EXCLUDED_TABLE_PREFIXES = [
    "pg_",           # PostgreSQL system tables
    "sql_",          # SQL standard tables
    "information_",  # Information schema tables
]


# System schemas to exclude from dataset discovery
SYSTEM_SCHEMAS = [
    'app',                  # SnapAnalyst system data
    'public',              # Reserved for SNAP QC (handled separately)
    'pg_catalog',          # PostgreSQL system catalog
    'information_schema',  # SQL standard system views
    'pg_toast',           # PostgreSQL TOAST storage
    'pg_temp',            # PostgreSQL temp schemas
]


def discover_tables_and_views(schema_name: str = 'public', db_engine: Engine = None) -> tuple[list[str], list[str]]:
    """
    Dynamically discover all user tables and views following naming conventions.

    Discovery Rules:
    - Tables: Include tables matching ref_*, snap_*, or core tables (households, etc.)
    - Views: Include views matching v_* or snap_v_*
    - Exclude: Tables in EXCLUDED_TABLES list or matching EXCLUDED_TABLE_PREFIXES

    Args:
        schema_name: PostgreSQL schema name (default: 'public')
        db_engine: SQLAlchemy engine (defaults to main engine)

    Returns:
        Tuple of (table_names, view_names) sorted with ref_* tables first
    """
    if db_engine is None:
        db_engine = engine

    with db_engine.connect() as conn:
        # Discover tables following naming conventions
        tables_query = text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_type = 'BASE TABLE'
              AND (
                  table_name LIKE 'ref_%'         -- Reference tables
                  OR table_name LIKE 'snap_%'     -- Custom SNAP tables
                  OR table_name IN :core_tables   -- Core tables (backwards compat)
              )
              AND table_name NOT IN :excluded_tables
            ORDER BY
                CASE
                    WHEN table_name LIKE 'ref_%' THEN 1  -- Reference tables first
                    ELSE 2                               -- Then others
                END,
                table_name
        """)

        result = conn.execute(tables_query, {
            "schema": schema_name,
            "core_tables": tuple(CORE_SNAP_TABLES),
            "excluded_tables": tuple(EXCLUDED_TABLES)
        })
        tables = [row[0] for row in result]

        # Filter out tables with excluded prefixes
        tables = [t for t in tables
                  if not any(t.startswith(prefix) for prefix in EXCLUDED_TABLE_PREFIXES)]

        # Discover views following naming conventions
        views_query = text("""
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = :schema
              AND (
                  table_name LIKE 'v_%'        -- Standard view prefix
                  OR table_name LIKE 'snap_v_%' -- Custom SNAP view prefix
              )
            ORDER BY table_name
        """)

        result = conn.execute(views_query, {"schema": schema_name})
        views = [row[0] for row in result]

    logger.info(f"Discovered in schema '{schema_name}': {len(tables)} tables, {len(views)} views")
    logger.debug(f"  Tables: {tables[:5]}{'...' if len(tables) > 5 else ''}")
    logger.debug(f"  Views: {views}")

    return tables, views


def discover_user_schemas(db_engine: Engine = None) -> list[str]:
    """
    Discover all user-created schemas (potential custom datasets).

    Excludes:
    - System schemas (app, pg_*, information_schema)
    - public schema (handled separately as SNAP QC dataset)

    Args:
        db_engine: SQLAlchemy engine (defaults to main engine)

    Returns:
        List of user-created schema names (e.g., ['state_ca', 'custom_data'])
    """
    if db_engine is None:
        db_engine = engine

    with db_engine.connect() as conn:
        # Query for all schemas
        query = text("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN :system_schemas
                AND schema_name NOT LIKE 'pg_%'
            ORDER BY schema_name
        """)
        result = conn.execute(query, {"system_schemas": tuple(SYSTEM_SCHEMAS)})
        schemas = [row[0] for row in result]

    logger.info(f"Discovered {len(schemas)} user schema(s): {schemas}")
    return schemas


def get_schema_table_list(schema_name: str, db_engine: Engine = None) -> list[str]:
    """
    Get list of all tables in a schema.

    Args:
        schema_name: PostgreSQL schema name
        db_engine: SQLAlchemy engine

    Returns:
        List of table names in the schema
    """
    if db_engine is None:
        db_engine = engine

    with db_engine.connect() as conn:
        query = text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema_name
                AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        result = conn.execute(query, {"schema_name": schema_name})
        tables = [row[0] for row in result]

    return tables


def get_table_ddl(table_name: str, db_engine: Engine = None, schema_name: str = "public") -> str | None:
    """
    Extract DDL for a single table from PostgreSQL.

    Uses information_schema to build CREATE TABLE statement with:
    - Column definitions (name, type, nullable)
    - Primary key constraints
    - Foreign key constraints
    - Comments

    For public schema (SNAP QC): generates unqualified table names
    For custom schemas: generates schema-qualified table names

    Args:
        table_name: Name of the table
        db_engine: SQLAlchemy engine (defaults to main engine)
        schema_name: PostgreSQL schema (defaults to 'public')

    Returns:
        DDL statement as string, or None if table doesn't exist
    """
    if db_engine is None:
        db_engine = engine

    with db_engine.connect() as conn:
        # Check if table exists (check in specified schema)
        check_query = text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = :schema_name AND table_name = :table_name
            )
        """)
        result = conn.execute(check_query, {"schema_name": schema_name, "table_name": table_name})
        if not result.scalar():
            logger.warning(f"Table {schema_name}.{table_name} does not exist")
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
            WHERE c.table_schema = :schema_name AND c.table_name = :table_name
            ORDER BY c.ordinal_position
        """)
        columns = conn.execute(columns_query, {"schema_name": schema_name, "table_name": table_name}).fetchall()

        # Get primary key columns
        pk_query = text("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = :schema_name
                AND tc.table_name = :table_name
            ORDER BY kcu.ordinal_position
        """)
        pk_columns = [row[0] for row in conn.execute(pk_query, {"schema_name": schema_name, "table_name": table_name})]

        # Get foreign key constraints
        fk_query = text("""
            SELECT
                kcu.column_name,
                ccu.table_schema AS foreign_schema,
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
                AND tc.table_schema = :schema_name
                AND tc.table_name = :table_name
        """)
        foreign_keys = conn.execute(fk_query, {"schema_name": schema_name, "table_name": table_name}).fetchall()

        # Build DDL
        # For public schema: use unqualified names (SNAP QC default)
        # For custom schemas: use schema-qualified names
        if schema_name == 'public':
            ddl_lines = [f"CREATE TABLE {table_name} ("]
        else:
            ddl_lines = [f"CREATE TABLE {schema_name}.{table_name} ("]

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
                type_str = f"DECIMAL({num_precision},{num_scale})" if num_precision and num_scale else "DECIMAL"
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
            col_name, fk_schema, fk_table, fk_column, constraint_name = fk
            if constraint_name not in fk_by_constraint:
                fk_by_constraint[constraint_name] = {
                    "columns": [],
                    "ref_schema": fk_schema,
                    "ref_table": fk_table,
                    "ref_columns": []
                }
            fk_by_constraint[constraint_name]["columns"].append(col_name)
            fk_by_constraint[constraint_name]["ref_columns"].append(fk_column)

        for _constraint_name, fk_info in fk_by_constraint.items():
            cols = ", ".join(fk_info["columns"])
            ref_schema = fk_info["ref_schema"]
            ref_table = fk_info["ref_table"]
            ref_cols = ", ".join(fk_info["ref_columns"])

            # For public schema references, omit schema qualification
            # For custom schemas, include schema in FK reference
            if ref_schema == 'public' and schema_name == 'public':
                fk_str = f"    FOREIGN KEY ({cols}) REFERENCES {ref_table}({ref_cols})"
            else:
                fk_str = f"    FOREIGN KEY ({cols}) REFERENCES {ref_schema}.{ref_table}({ref_cols})"
            ddl_lines.append(f",\n{fk_str}")

        ddl_lines.append("\n);")

        ddl = "\n".join(ddl_lines)

        # Add table comment if exists (use schema-qualified name)
        # Comments may contain example queries and multi-line documentation
        table_comment_query = text("""
            SELECT obj_description((quote_ident(:schema_name) || '.' || quote_ident(:table_name))::regclass, 'pg_class')
        """)
        try:
            table_comment = conn.execute(table_comment_query, {"schema_name": schema_name, "table_name": table_name}).scalar()
            if table_comment:
                # Format multi-line comments properly
                comment_lines = table_comment.strip().split('\n')
                formatted_comment = '\n'.join(f"-- {line}" for line in comment_lines)
                ddl += f"\n\n{formatted_comment}"
        except Exception as e:
            logger.debug(f"Could not fetch table comment for {schema_name}.{table_name}: {e}")

        return ddl


def get_reference_table_ddl_with_sample_data(table_name: str, db_engine: Engine = None, schema_name: str = "public") -> str | None:
    """
    Extract DDL for reference table and include sample data as comments.

    This helps Vanna understand what values are available in lookup tables.

    Args:
        table_name: Name of the reference table
        db_engine: SQLAlchemy engine
        schema_name: PostgreSQL schema (defaults to 'public')

    Returns:
        DDL with sample data comments
    """
    ddl = get_table_ddl(table_name, db_engine, schema_name)
    if not ddl:
        return None

    if db_engine is None:
        db_engine = engine

    # Get sample data (first 15 rows)
    with db_engine.connect() as conn:
        # Check if table has description column
        has_description = False
        check_query = text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = :schema_name AND table_name = :table_name AND column_name = 'description'
            )
        """)
        has_description = conn.execute(check_query, {"schema_name": schema_name, "table_name": table_name}).scalar()

        if has_description:
            # Get primary key column name
            pk_query = text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_schema = :schema_name
                    AND tc.table_name = :table_name
                LIMIT 1
            """)
            pk_col = conn.execute(pk_query, {"schema_name": schema_name, "table_name": table_name}).scalar() or "code"

            # Get sample data (use schema-qualified table name if not public)
            if schema_name == 'public':
                sample_query = text(f"""
                    SELECT {pk_col}, description
                    FROM {table_name}
                    ORDER BY {pk_col}
                    LIMIT 15
                """)
            else:
                sample_query = text(f"""
                    SELECT {pk_col}, description
                    FROM {schema_name}.{table_name}
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
                logger.warning(f"Could not get sample data for {schema_name}.{table_name}: {e}")

    return ddl


def get_view_ddl(view_name: str, db_engine: Engine = None, schema_name: str = "public") -> str | None:
    """
    Extract DDL for a database view from PostgreSQL.

    Uses information_schema to build CREATE VIEW statement with view definition.

    Args:
        view_name: Name of the view
        db_engine: SQLAlchemy engine (defaults to main engine)
        schema_name: PostgreSQL schema (defaults to 'public')

    Returns:
        CREATE VIEW DDL statement as string, or None if view doesn't exist
    """
    if db_engine is None:
        db_engine = engine

    with db_engine.connect() as conn:
        # Check if view exists
        check_query = text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views
                WHERE table_schema = :schema_name AND table_name = :view_name
            )
        """)
        result = conn.execute(check_query, {"schema_name": schema_name, "view_name": view_name})
        if not result.scalar():
            logger.warning(f"View {schema_name}.{view_name} does not exist")
            return None

        # Get view definition
        view_query = text("""
            SELECT view_definition
            FROM information_schema.views
            WHERE table_schema = :schema_name AND table_name = :view_name
        """)
        view_def = conn.execute(view_query, {"schema_name": schema_name, "view_name": view_name}).scalar()

        # Get view columns with types
        columns_query = text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = :schema_name AND table_name = :view_name
            ORDER BY ordinal_position
        """)
        columns = conn.execute(columns_query, {"schema_name": schema_name, "view_name": view_name}).fetchall()

        # Build CREATE VIEW statement
        qualified_name = f"{schema_name}.{view_name}" if schema_name != 'public' else view_name
        ddl = f"CREATE OR REPLACE VIEW {qualified_name} AS\n{view_def.strip()};"

        # Add column comments
        ddl += f"\n-- View columns ({len(columns)} total):"
        for col_name, col_type in columns[:10]:  # Show first 10 columns
            ddl += f"\n--   {col_name}: {col_type}"
        if len(columns) > 10:
            ddl += f"\n--   ... and {len(columns) - 10} more columns"

        # Get table comment if exists
        comment_query = text("""
            SELECT obj_description((quote_ident(:schema_name) || '.' || quote_ident(:view_name))::regclass, 'pg_class')
        """)
        try:
            comment = conn.execute(comment_query, {"schema_name": schema_name, "view_name": view_name}).scalar()
            if comment:
                ddl += f"\n-- Description: {comment}"
        except Exception:
            pass  # Table comment is optional

    return ddl


def get_all_ddl_statements(
    include_samples: bool = True,
    include_format_docs: bool = True,
    dataset_name: str | None = None,
    schema_name: str = "public"
) -> list[str]:
    """
    Get DDL statements for all tables and views in the correct order.

    Reference tables are listed first (for FK dependencies), then main tables,
    then enriched views (for public schema only).
    Includes sample data from lookup tables to help Vanna understand values.
    Includes column format documentation from data_mapping.json.

    This function extracts DDL for a single dataset/schema.
    For multi-dataset support, use get_ddl_for_all_datasets().

    Args:
        include_samples: Include sample data from reference tables
        include_format_docs: Include column format documentation
        dataset_name: Optional dataset name for multi-dataset support
        schema_name: PostgreSQL schema to extract from (default: 'public')

    Returns:
        List of DDL statements ready for Vanna training (tables + views)
    """
    ddl_statements = []

    # Use default engine
    db_engine = engine

    # Dynamically discover tables and views following naming conventions
    all_tables, views = discover_tables_and_views(schema_name, db_engine)

    # Separate reference tables from other tables for correct ordering
    reference_tables = [t for t in all_tables if t.startswith('ref_')]
    main_tables = [t for t in all_tables if not t.startswith('ref_')]

    # First, extract reference tables with sample data
    logger.info(f"Extracting DDL for reference tables from schema '{schema_name}'...")
    for table_name in reference_tables:
        if include_samples:
            ddl = get_reference_table_ddl_with_sample_data(table_name, db_engine, schema_name)
        else:
            ddl = get_table_ddl(table_name, db_engine, schema_name)

        if ddl:
            ddl_statements.append(ddl)
            logger.debug(f"Extracted DDL for {schema_name}.{table_name}")
        else:
            logger.warning(f"Could not extract DDL for {schema_name}.{table_name}")

    # Then, extract main tables
    logger.info(f"Extracting DDL for main tables from schema '{schema_name}'...")
    for table_name in main_tables:
        ddl = get_table_ddl(table_name, db_engine, schema_name)
        if ddl:
            ddl_statements.append(ddl)
            logger.debug(f"Extracted DDL for {schema_name}.{table_name}")
        else:
            logger.warning(f"Could not extract DDL for {schema_name}.{table_name}")

    # Then, extract views
    if views:
        logger.info(f"Extracting DDL for views from schema '{schema_name}'...")
        for view_name in views:
            ddl = get_view_ddl(view_name, db_engine, schema_name)
            if ddl:
                ddl_statements.append(ddl)
                logger.debug(f"Extracted DDL for view {schema_name}.{view_name}")
            else:
                logger.warning(f"Could not extract DDL for view {schema_name}.{view_name}")

    # Add column format documentation (only for SNAP QC / public schema)
    if include_format_docs and schema_name == 'public':
        format_doc = get_column_format_documentation()
        if format_doc:
            ddl_statements.append(format_doc)
            logger.info("Added column format documentation from data_mapping.json")

    # Log summary
    item_types = []
    if reference_tables:
        item_types.append(f"{len(reference_tables)} reference tables")
    if main_tables:
        item_types.append(f"{len(main_tables)} main tables")
    if views:
        item_types.append(f"{len(views)} views")

    logger.info(f"Extracted DDL for {len(ddl_statements)} items from schema '{schema_name}' ({', '.join(item_types)})")
    return ddl_statements


def get_ddl_for_all_datasets(
    include_samples: bool = True,
    include_format_docs: bool = True
) -> dict[str, list[str]]:
    """
    Extract DDL for all datasets (public + custom schemas).

    Returns a dictionary mapping dataset names to their DDL statements:
    - 'snap_qc': DDL from public schema (SNAP QC default dataset)
    - Custom schemas: DDL from user-created schemas (e.g., 'state_ca')

    System schemas (app, pg_*, information_schema) are excluded.

    Args:
        include_samples: Include sample data from reference tables
        include_format_docs: Include column format documentation (SNAP QC only)

    Returns:
        Dict mapping dataset names to lists of DDL statements
        Example: {'snap_qc': [...], 'state_ca': [...]}
    """
    datasets = {}

    # 1. Extract SNAP QC dataset (public schema)
    logger.info("Extracting DDL for SNAP QC dataset (public schema)...")
    snap_qc_ddl = get_all_ddl_statements(
        include_samples=include_samples,
        include_format_docs=include_format_docs,
        schema_name='public'
    )
    if snap_qc_ddl:
        datasets['snap_qc'] = snap_qc_ddl
        logger.info(f"SNAP QC dataset: {len(snap_qc_ddl)} DDL statements")

    # 2. Discover and extract custom datasets (user-created schemas)
    user_schemas = discover_user_schemas()

    for schema in user_schemas:
        logger.info(f"Extracting DDL for dataset '{schema}' (schema: {schema})...")
        try:
            schema_ddl = get_all_ddl_statements(
                include_samples=include_samples,
                include_format_docs=False,  # No format docs for custom schemas
                schema_name=schema
            )
            if schema_ddl:
                datasets[schema] = schema_ddl
                logger.info(f"Dataset '{schema}': {len(schema_ddl)} DDL statements")
        except Exception as e:
            logger.error(f"Failed to extract DDL for schema '{schema}': {e}")

    logger.info(f"Total datasets extracted: {len(datasets)}")
    return datasets


def get_ddl_for_dataset(dataset_name: str, include_samples: bool = True) -> list[str]:
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


def verify_database_schema(schema_name: str = "public") -> dict[str, bool]:
    """
    Verify that all expected tables exist in the database.

    Args:
        schema_name: PostgreSQL schema to check (default: 'public')

    Returns:
        Dict mapping table names to existence status
    """
    status = {}

    # Dynamically discover all tables using the same method as get_all_ddl_statements
    all_tables, _ = discover_tables_and_views(schema_name, engine)

    with engine.connect() as conn:
        for table_name in all_tables:
            check_query = text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = :schema_name AND table_name = :table_name
                )
            """)
            exists = conn.execute(check_query, {"schema_name": schema_name, "table_name": table_name}).scalar()
            status[table_name] = exists

    return status


def get_foreign_key_summary(schema_name: str = "public") -> list[dict]:
    """
    Get a summary of all foreign key relationships.

    Useful for understanding and documenting relationships.

    Args:
        schema_name: PostgreSQL schema to check (default: 'public')

    Returns:
        List of FK relationship dictionaries
    """
    fk_summary = []

    with engine.connect() as conn:
        query = text("""
            SELECT
                tc.table_schema as from_schema,
                tc.table_name as from_table,
                kcu.column_name as from_column,
                ccu.table_schema AS to_schema,
                ccu.table_name AS to_table,
                ccu.column_name AS to_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = :schema_name
            ORDER BY tc.table_name, kcu.column_name
        """)
        results = conn.execute(query, {"schema_name": schema_name}).fetchall()

        for row in results:
            fk_summary.append({
                "from_schema": row[0],
                "from_table": row[1],
                "from_column": row[2],
                "to_schema": row[3],
                "to_table": row[4],
                "to_column": row[5]
            })

    return fk_summary


def get_column_format_documentation() -> str | None:
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

        with open(DATA_MAPPING_PATH) as f:
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
                if col_line.strip("-").strip().strip(","):
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


def get_cached_ddl_statements() -> list[str]:
    """
    Get DDL statements with caching for performance.

    First call queries the database, subsequent calls return cached results.
    """
    global DDL_STATEMENTS
    if DDL_STATEMENTS is None:
        DDL_STATEMENTS = get_all_ddl_statements()
    return DDL_STATEMENTS


def refresh_ddl_cache() -> list[str]:
    """
    Refresh the DDL cache from the database.

    Call this after schema changes.
    """
    global DDL_STATEMENTS
    DDL_STATEMENTS = get_all_ddl_statements()
    return DDL_STATEMENTS
