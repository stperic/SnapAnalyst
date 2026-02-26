"""
Schema Introspection Utilities

Dynamically generates schema information from the database using SQLAlchemy
introspection and PostgreSQL information_schema queries.
"""

from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from src.core.logging import get_logger

logger = get_logger(__name__)


class SchemaIntrospector:
    """Introspects database schema dynamically."""

    def __init__(self, engine: Engine):
        """
        Initialize schema introspector.

        Args:
            engine: SQLAlchemy engine instance
        """
        self.engine = engine
        self.inspector = inspect(engine)

    def get_all_tables(self) -> dict[str, Any]:
        """
        Get all tables with their complete structure from the database.

        Returns:
            Dictionary with table names as keys and table metadata as values
        """
        tables = {}

        for table_name in self.inspector.get_table_names():
            tables[table_name] = self.get_table_structure(table_name)

        return tables

    def get_all_views(self) -> dict[str, Any]:
        """
        Get all views with their structure from the database.

        Returns:
            Dictionary with view names as keys and view metadata as values
        """
        views = {}

        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT table_name
                    FROM information_schema.views
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                result = conn.execute(query)
                view_names = [row[0] for row in result]

                for view_name in view_names:
                    views[view_name] = self.get_view_structure(view_name)

        except Exception as e:
            logger.warning(f"Could not get views: {e}")

        return views

    def get_view_structure(self, view_name: str) -> dict[str, Any]:
        """
        Get structure for a specific view.

        Args:
            view_name: Name of the view to introspect

        Returns:
            Dictionary with view metadata including columns and definition
        """
        # Get columns (views support get_columns just like tables)
        columns = {}
        try:
            for col in self.inspector.get_columns(view_name):
                col_name = col["name"]
                columns[col_name] = {
                    "name": col_name,
                    "type": str(col["type"]),
                    "nullable": col["nullable"],
                }
        except Exception as e:
            logger.warning(f"Could not get columns for view {view_name}: {e}")

        # Get view definition
        view_definition = None
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT view_definition
                    FROM information_schema.views
                    WHERE table_schema = 'public' AND table_name = :view_name
                """)
                result = conn.execute(query, {"view_name": view_name})
                view_definition = result.scalar()
        except Exception as e:
            logger.warning(f"Could not get definition for view {view_name}: {e}")

        # Get row count (views can be queried just like tables)
        row_count = self._get_row_count(view_name)

        return {
            "name": view_name,
            "type": "view",
            "columns": columns,
            "definition": view_definition,
            "row_count": row_count,
        }

    def get_table_structure(self, table_name: str) -> dict[str, Any]:
        """
        Get complete structure for a specific table.

        Args:
            table_name: Name of the table to introspect

        Returns:
            Dictionary with table metadata including columns, keys, indexes
        """
        # Get columns
        columns = {}
        for col in self.inspector.get_columns(table_name):
            col_name = col["name"]
            columns[col_name] = {
                "name": col_name,
                "type": str(col["type"]),
                "nullable": col["nullable"],
                "default": str(col["default"]) if col["default"] is not None else None,
                "autoincrement": col.get("autoincrement", False),
            }

        # Get primary keys
        pk_constraint = self.inspector.get_pk_constraint(table_name)
        primary_keys = pk_constraint.get("constrained_columns", []) if pk_constraint else []

        # Get foreign keys
        foreign_keys = []
        for fk in self.inspector.get_foreign_keys(table_name):
            foreign_keys.append(
                {
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"],
                }
            )

        # Get indexes
        indexes = []
        for idx in self.inspector.get_indexes(table_name):
            indexes.append(
                {
                    "name": idx["name"],
                    "columns": idx["column_names"],
                    "unique": idx["unique"],
                }
            )

        # Get row count
        row_count = self._get_row_count(table_name)

        return {
            "name": table_name,
            "columns": columns,
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "indexes": indexes,
            "row_count": row_count,
        }

    def _get_row_count(self, table_name: str) -> int:
        """
        Get approximate row count for a table.

        Args:
            table_name: Name of the table

        Returns:
            Approximate number of rows
        """
        try:
            # Validate table_name against known tables to prevent SQL injection
            import re

            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", table_name):
                logger.warning(f"Invalid table name rejected: {table_name}")
                return 0
            with self.engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                return result.scalar()
        except Exception as e:
            logger.warning(f"Could not get row count for {table_name}: {e}")
            return 0

    def get_column_descriptions(self, table_name: str) -> dict[str, str]:
        """
        Get column descriptions from PostgreSQL comments.

        Args:
            table_name: Name of the table

        Returns:
            Dictionary mapping column names to their descriptions
        """
        descriptions = {}

        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT
                        cols.column_name,
                        pg_catalog.col_description(c.oid, cols.ordinal_position::int) as description
                    FROM information_schema.columns cols
                    JOIN pg_catalog.pg_class c ON c.relname = cols.table_name
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE cols.table_schema = 'public'
                    AND cols.table_name = :table_name
                """)

                result = conn.execute(query, {"table_name": table_name})
                for row in result:
                    if row[1]:  # If description exists
                        descriptions[row[0]] = row[1]

        except Exception as e:
            logger.warning(f"Could not get column descriptions for {table_name}: {e}")

        return descriptions

    def get_table_relationships(self) -> dict[str, Any]:
        """
        Get relationships between tables based on foreign keys.

        Returns:
            Dictionary describing table relationships
        """
        relationships = {}

        for table_name in self.inspector.get_table_names():
            fks = self.inspector.get_foreign_keys(table_name)

            for fk in fks:
                rel_name = f"{table_name}_to_{fk['referred_table']}"
                relationships[rel_name] = {
                    "from_table": table_name,
                    "to_table": fk["referred_table"],
                    "from_columns": fk["constrained_columns"],
                    "to_columns": fk["referred_columns"],
                    "type": "many-to-one",  # Most common case
                }

        return relationships

    def get_database_info(self) -> dict[str, Any]:
        """
        Get high-level database information.

        Returns:
            Dictionary with database metadata
        """
        tables = self.inspector.get_table_names()

        total_rows = 0
        for table in tables:
            total_rows += self._get_row_count(table)

        # Get PostgreSQL version
        pg_version = "Unknown"
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                pg_version = result.scalar()
        except Exception as e:
            logger.warning(f"Could not get PostgreSQL version: {e}")

        return {
            "database_name": self.engine.url.database,
            "host": self.engine.url.host,
            "port": self.engine.url.port,
            "tables": tables,
            "table_count": len(tables),
            "total_rows": total_rows,
            "postgresql_version": pg_version,
        }

    def merge_with_static_metadata(
        self, dynamic_schema: dict[str, Any], static_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Merge dynamic schema from database with static metadata from JSON.

        This preserves rich descriptions, examples, and documentation from
        data_mapping.json while ensuring column lists match the actual database.

        Args:
            dynamic_schema: Schema introspected from database
            static_metadata: Metadata from data_mapping.json

        Returns:
            Merged schema with database truth + rich metadata
        """
        merged = dynamic_schema.copy()

        # For each table in dynamic schema
        for table_name, table_info in dynamic_schema.get("columns", {}).items():
            # Get static metadata for this table if it exists
            static_table = static_metadata.get("tables", {}).get(table_name, {})
            static_columns = static_table.get("columns", {})

            # Merge column metadata
            for col_name, col_info in table_info.items():
                if col_name in static_columns:
                    # Add rich metadata from static file
                    static_col = static_columns[col_name]
                    col_info["description"] = static_col.get("description", "")
                    col_info["range"] = static_col.get("range", "")
                    col_info["example"] = static_col.get("example", "")
                    col_info["source_field"] = static_col.get("source_field", "")

        return merged
