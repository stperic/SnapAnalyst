"""
SnapAnalyst Query API Router

Endpoints for executing SQL queries safely and providing schema information for LLM training.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_serializer
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from src.core.logging import get_logger
from src.database.engine import SessionLocal, engine

logger = get_logger(__name__)

router = APIRouter(tags=["query"])


class SQLQueryRequest(BaseModel):
    """Request to execute SQL query"""
    sql: str = Field(..., description="SQL query to execute (SELECT only)")
    limit: int = Field(50000, ge=1, le=100000, description="Maximum rows to return")
    format: str = Field("json", description="Response format: json, markdown, csv")


class SQLQueryResponse(BaseModel):
    """Response from SQL query execution"""
    success: bool
    query: str
    execution_time_ms: float
    row_count: int
    columns: list[str]
    data: list[dict]
    formatted: str | None = None
    error: str | None = None

    @field_serializer('data')
    def serialize_data(self, data: list[dict], _info) -> list[dict]:
        """Convert Decimal values to float in data for JSON serialization"""
        from decimal import Decimal
        return [
            {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}
            for row in data
        ]


class QueryValidator:
    """Validates SQL queries for safety"""

    # Dangerous SQL keywords that should be blocked
    DANGEROUS_KEYWORDS = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
        'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE',
        'EXEC', 'EXECUTE', 'CALL', 'PROCEDURE',
        'INTO OUTFILE', 'INTO DUMPFILE', 'LOAD_FILE'
    ]

    # Allowed keywords (whitelist approach)
    ALLOWED_KEYWORDS = [
        'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER',
        'OUTER', 'ON', 'GROUP', 'BY', 'HAVING', 'ORDER', 'LIMIT',
        'OFFSET', 'AS', 'AND', 'OR', 'NOT', 'IN', 'BETWEEN', 'LIKE',
        'IS', 'NULL', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
        'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'CAST', 'COALESCE'
    ]

    @classmethod
    def validate_query(cls, sql: str) -> tuple[bool, str | None]:
        """
        Validate SQL query for safety.

        Args:
            sql: SQL query string

        Returns:
            (is_valid, error_message)
        """
        sql_upper = sql.upper()

        # Check for dangerous keywords
        for keyword in cls.DANGEROUS_KEYWORDS:
            if re.search(r'\b' + keyword + r'\b', sql_upper):
                return False, f"Query contains forbidden keyword: {keyword}"

        # Must start with SELECT or WITH (for CTEs)
        sql_stripped = sql_upper.strip()
        if not (sql_stripped.startswith('SELECT') or sql_stripped.startswith('WITH')):
            return False, "Only SELECT and WITH queries are allowed"

        # Check for semicolons (multiple statements)
        if sql.count(';') > 1 or (sql.count(';') == 1 and not sql.strip().endswith(';')):
            return False, "Multiple statements not allowed"

        # Check for comments that might hide dangerous code
        if '--' in sql or '/*' in sql or '*/' in sql:
            return False, "Comments not allowed in queries"

        return True, None

    @classmethod
    def sanitize_query(cls, sql: str, limit: int) -> str:
        """
        Sanitize query by adding LIMIT if not present.

        Args:
            sql: SQL query
            limit: Maximum rows to return

        Returns:
            Sanitized SQL query
        """
        sql = sql.strip()

        # Remove trailing semicolon
        if sql.endswith(';'):
            sql = sql[:-1]

        # Add LIMIT if not present
        if 'LIMIT' not in sql.upper():
            sql = f"{sql} LIMIT {limit}"

        return sql


@router.get("/schema")
async def get_schema_documentation():
    """
    Get complete schema documentation with hybrid approach:
    - Query database for accurate structure (tables, columns, types, constraints)
    - Overlay descriptions and business context from JSON documentation

    This ensures the schema is always accurate while maintaining rich documentation.

    Returns:
        Complete schema documentation JSON
    """
    try:
        # Step 1: Get actual schema from database
        inspector = inspect(engine)
        db_schema = _get_database_schema(inspector)

        # Step 2: Load documentation from JSON file (now in datasets/snap/)
        schema_path = Path(__file__).parent.parent.parent.parent / "datasets" / "snap" / "data_mapping.json"

        if not schema_path.exists():
            # Fallback to old schema_documentation.json
            schema_path = Path(__file__).parent.parent.parent.parent / "schema_documentation.json"

        docs = {}
        if schema_path.exists():
            with open(schema_path) as f:
                docs = json.load(f)

        # Step 3: Merge database schema with documentation
        merged_schema = _merge_schema_with_docs(db_schema, docs)

        logger.info("Hybrid schema documentation requested (DB + JSON)")
        return merged_schema

    except Exception as e:
        logger.error(f"Error generating schema documentation: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate schema documentation: {e}"
        )


def _get_database_schema(inspector) -> dict:
    """
    Query database for actual schema structure.

    Uses the same table discovery config (datasets/snap/config.yaml) as Vanna training
    to exclude Chainlit internals, migration tables, and system prefixes.

    Args:
        inspector: SQLAlchemy inspector

    Returns:
        Dictionary with tables, columns, types, and constraints
    """
    from src.database.ddl_extractor import _load_table_discovery_config

    config = _load_table_discovery_config()
    exclude_tables = set(config["exclude_tables"])
    exclude_prefixes = tuple(config["exclude_table_prefixes"])

    schema = {
        "tables": {},
        "relationships": {},
        "database": {
            "name": "SnapAnalyst",
            "description": "SNAP Quality Control database (queried from live database)",
            "source": "PostgreSQL Database"
        }
    }

    # Get all table names
    table_names = inspector.get_table_names()

    for table_name in table_names:
        # Skip internal/excluded tables using shared config
        if table_name.startswith('_') or table_name in exclude_tables or table_name.startswith(exclude_prefixes):
            continue

        table_info = {
            "description": f"Table: {table_name}",
            "columns": {}
        }

        # Get columns
        columns = inspector.get_columns(table_name)
        for col in columns:
            col_name = col['name']
            col_type = str(col['type'])
            nullable = col.get('nullable', True)
            default = col.get('default')

            table_info["columns"][col_name] = {
                "type": col_type,
                "nullable": nullable,
                "description": f"Column: {col_name}"
            }

            if default is not None:
                table_info["columns"][col_name]["default"] = str(default)

        # Get primary keys
        pk_constraint = inspector.get_pk_constraint(table_name)
        if pk_constraint and pk_constraint.get('constrained_columns'):
            table_info["primary_key"] = pk_constraint['constrained_columns']

        # Get foreign keys
        fk_constraints = inspector.get_foreign_keys(table_name)
        if fk_constraints:
            table_info["foreign_keys"] = []
            for fk in fk_constraints:
                fk_info = {
                    "columns": fk.get('constrained_columns', []),
                    "referred_table": fk.get('referred_table'),
                    "referred_columns": fk.get('referred_columns', [])
                }
                table_info["foreign_keys"].append(fk_info)

                # Add to relationships
                rel_name = f"{table_name}_to_{fk['referred_table']}"
                schema["relationships"][rel_name] = {
                    "type": "MANY_TO_ONE" if len(fk['constrained_columns']) == 1 else "MANY_TO_MANY",
                    "join": f"{table_name}.{fk['constrained_columns'][0]} = {fk['referred_table']}.{fk['referred_columns'][0]}",
                    "description": "Foreign key relationship"
                }

        schema["tables"][table_name] = table_info

    return schema


def _merge_schema_with_docs(db_schema: dict, docs: dict) -> dict:
    """
    Merge database schema with documentation from JSON.
    Database schema takes precedence for structure, docs provide descriptions.

    Args:
        db_schema: Schema from database
        docs: Documentation from JSON file

    Returns:
        Merged schema with both structure and descriptions
    """
    merged = db_schema.copy()

    # Update database info from docs
    if "database" in docs:
        merged["database"].update(docs["database"])
        merged["database"]["source"] = "PostgreSQL Database (live schema with JSON documentation)"

    # Merge table information
    doc_tables = docs.get("tables", {})

    for table_name, table_info in merged["tables"].items():
        if table_name in doc_tables:
            doc_table = doc_tables[table_name]

            # Update table description
            if "description" in doc_table:
                table_info["description"] = doc_table["description"]

            # Copy additional table-level metadata from docs
            for key in ["row_count", "source_notes", "unique_constraint"]:
                if key in doc_table:
                    table_info[key] = doc_table[key]

            # Merge column information
            doc_columns = doc_table.get("columns", {})
            for col_name, col_info in table_info["columns"].items():
                if col_name in doc_columns:
                    doc_col = doc_columns[col_name]

                    # Keep DB type but overlay documentation
                    if "description" in doc_col:
                        col_info["description"] = doc_col["description"]

                    # Add additional metadata from docs
                    for key in ["example", "range", "codes", "source_field", "notes"]:
                        if key in doc_col:
                            col_info[key] = doc_col[key]

    # Better relationship merging - match by join condition
    doc_relationships = docs.get("relationships", {})

    # Create a lookup by join condition for better matching
    doc_rels_by_join = {}
    for rel_name, rel_info in doc_relationships.items():
        join = rel_info.get("join", "")
        # Normalize join condition (swap direction if needed)
        doc_rels_by_join[join] = (rel_name, rel_info)
        # Also add reversed version
        parts = join.split(" = ")
        if len(parts) == 2:
            reversed_join = f"{parts[1]} = {parts[0]}"
            doc_rels_by_join[reversed_join] = (rel_name, rel_info)

    # Update database relationships with doc info
    for _db_rel_name, db_rel_info in merged["relationships"].items():
        db_join = db_rel_info.get("join", "")

        # Try to find matching doc relationship
        if db_join in doc_rels_by_join:
            doc_rel_name, doc_rel_info = doc_rels_by_join[db_join]

            # Use doc description and type (they're more meaningful)
            if "description" in doc_rel_info:
                db_rel_info["description"] = doc_rel_info["description"]
            if "type" in doc_rel_info:
                db_rel_info["type"] = doc_rel_info["type"]

    # Add code_lookups from docs (these aren't in database)
    if "code_lookups" in docs:
        merged["code_lookups"] = docs["code_lookups"]

    return merged


@router.post("/sql", response_model=SQLQueryResponse)
async def execute_sql_query(request: SQLQueryRequest):
    """
    Execute a SQL query safely with validation.

    Only SELECT queries are allowed. Dangerous operations like
    DROP, DELETE, UPDATE are blocked.

    Args:
        request: SQL query request with query string and options

    Returns:
        Query results with execution metadata
    """
    try:
        # Validate query
        is_valid, error_msg = QueryValidator.validate_query(request.sql)
        if not is_valid:
            logger.warning(f"Invalid query rejected: {error_msg}")
            return SQLQueryResponse(
                success=False,
                query=request.sql,
                execution_time_ms=0,
                row_count=0,
                columns=[],
                data=[],
                error=error_msg
            )

        # Sanitize query
        sanitized_sql = QueryValidator.sanitize_query(request.sql, request.limit)

        # Execute query
        session = SessionLocal()
        start_time = time.time()

        try:
            result = session.execute(text(sanitized_sql))
            execution_time = (time.time() - start_time) * 1000  # Convert to ms

            # Fetch results
            rows = result.fetchall()
            columns = list(result.keys()) if rows else []

            # Limit columns if configured (for SELECT * queries)
            from src.core.config import settings
            max_cols = settings.max_result_columns
            if len(columns) > max_cols:
                logger.info(f"Limiting columns from {len(columns)} to {max_cols}")
                columns = columns[:max_cols]
                # Truncate rows to match limited columns
                rows = [row[:max_cols] for row in rows]

            # Convert to list of dicts
            data = [dict(zip(columns, row, strict=False)) for row in rows]

            # Format response based on format parameter
            formatted = None
            if request.format == "markdown":
                formatted = _format_as_markdown(columns, data)
            elif request.format == "csv":
                formatted = _format_as_csv(columns, data)

            logger.info(
                f"Query executed successfully: {len(data)} rows in {execution_time:.2f}ms"
            )

            return SQLQueryResponse(
                success=True,
                query=sanitized_sql,
                execution_time_ms=round(execution_time, 2),
                row_count=len(data),
                columns=columns,
                data=data,
                formatted=formatted
            )

        except SQLAlchemyError as e:
            logger.error(f"SQL execution error: {e}")
            return SQLQueryResponse(
                success=False,
                query=sanitized_sql,
                execution_time_ms=0,
                row_count=0,
                columns=[],
                data=[],
                error=f"Query execution failed: {str(e)}"
            )
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Unexpected error executing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute query: {e}"
        )


@router.get("/examples")
async def get_example_queries():
    """
    Get example SQL queries for common questions.

    These examples help users understand how to query the database
    and can be used to train LLMs.

    Returns:
        List of example queries with descriptions
    """
    try:
        from src.services.llm_training import load_training_examples

        examples = load_training_examples()
        if not examples:
            return {"example_queries": []}

        return {"example_queries": examples}

    except Exception as e:
        logger.error(f"Error loading example queries: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load examples: {e}"
        )


def _format_as_markdown(columns: list[str], data: list[dict]) -> str:
    """Format query results as markdown table"""
    if not data:
        return "No results"

    # Header
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"

    # Rows
    rows = []
    for row in data[:100]:  # Limit to first 100 rows for markdown
        row_values = [str(row.get(col, "")) for col in columns]
        rows.append("| " + " | ".join(row_values) + " |")

    result = "\n".join([header, separator] + rows)

    if len(data) > 100:
        result += f"\n\n*Showing first 100 of {len(data)} rows*"

    return result


def _format_as_csv(columns: list[str], data: list[dict]) -> str:
    """Format query results as CSV"""
    if not data:
        return ""

    # Header
    lines = [",".join(columns)]

    # Rows
    for row in data:
        row_values = [str(row.get(col, "")).replace(",", ";") for col in columns]
        lines.append(",".join(row_values))

    return "\n".join(lines)
