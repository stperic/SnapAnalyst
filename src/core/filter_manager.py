"""
Global Filter Manager for SnapAnalyst

Provides per-user filtering that applies to all queries and exports.
Filters are stored in database (persists across sessions).

Designed for extensibility - can easily support multiple states/years in future.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DataFilter:
    """
    Application-level data filter.

    Currently supports single state/year, but designed for future multi-select.
    """

    states: list[str] = field(default_factory=list)  # Future: multiple states
    fiscal_years: list[int] = field(default_factory=list)  # Future: multiple years
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def state(self) -> str | None:
        """Get single state (current implementation)."""
        return self.states[0] if self.states else None

    @property
    def fiscal_year(self) -> int | None:
        """Get single fiscal year (current implementation)."""
        return self.fiscal_years[0] if self.fiscal_years else None

    @property
    def is_active(self) -> bool:
        """Check if any filter is active."""
        return bool(self.states or self.fiscal_years)

    @property
    def is_empty(self) -> bool:
        """Check if filter is empty."""
        return not self.is_active

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "state": self.state,  # Current: single value
            "fiscal_year": self.fiscal_year,  # Current: single value
            "states": self.states,  # Future: multiple values
            "fiscal_years": self.fiscal_years,  # Future: multiple values
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def _validate_state(state: str) -> str:
        """Validate state name contains only safe characters."""
        if not re.match(r"^[A-Za-z\s\-\.]+$", state):
            raise ValueError(f"Invalid state name: {state!r}")
        return state

    @staticmethod
    def _validate_fiscal_year(year: int) -> int:
        """Validate fiscal year is an integer in a reasonable range."""
        if not isinstance(year, int) or year < 2000 or year > 2100:
            raise ValueError(f"Invalid fiscal year: {year!r}")
        return year

    def get_sql_conditions(self) -> list[str]:
        """
        Get SQL WHERE conditions for this filter.

        Returns:
            List of SQL conditions (e.g., ["state_name = 'Connecticut'", "fiscal_year = 2023"])
        """
        conditions = []

        if self.states:
            validated = [self._validate_state(s) for s in self.states]
            if len(validated) == 1:
                conditions.append(f"state_name = '{validated[0]}'")
            else:
                states_str = "', '".join(validated)
                conditions.append(f"state_name IN ('{states_str}')")

        if self.fiscal_years:
            validated_years = [self._validate_fiscal_year(y) for y in self.fiscal_years]
            if len(validated_years) == 1:
                conditions.append(f"fiscal_year = {validated_years[0]}")
            else:
                years_str = ", ".join(map(str, validated_years))
                conditions.append(f"fiscal_year IN ({years_str})")

        return conditions

    def get_description(self) -> str:
        """Get human-readable description of filter."""
        if self.is_empty:
            return "No filter (All data)"

        parts = []
        if self.states:
            if len(self.states) == 1:
                parts.append(f"State: {self.states[0]}")
            else:
                parts.append(f"States: {', '.join(self.states)}")

        if self.fiscal_years:
            if len(self.fiscal_years) == 1:
                parts.append(f"FY{self.fiscal_years[0]}")
            else:
                years = ", ".join(f"FY{y}" for y in self.fiscal_years)
                parts.append(f"Years: {years}")

        return " | ".join(parts)


class FilterManager:
    """Simple per-user filter manager with database persistence."""

    def _get_user_id(self) -> str:
        """
        Get current user ID from request context.

        THREAD-SAFE: Tries multiple sources in order of preference:
        1. FastAPI request context (API endpoints)
        2. Chainlit session (UI)
        3. Default fallback

        This ensures proper user isolation in multi-user environments.

        Returns:
            User identifier string
        """
        # Try FastAPI request context first (for API endpoints)
        try:
            from src.api.dependencies import get_request_user

            user_id = get_request_user()
            if user_id:
                return user_id
        except Exception:
            pass

        # Try Chainlit session (for UI)
        try:
            import chainlit as cl

            user = cl.user_session.get("user")
            if user and hasattr(user, "identifier"):
                return user.identifier
        except Exception:
            pass

        # Fallback: use first user in database
        try:
            from sqlalchemy import text

            from src.database.engine import SessionLocal

            session = SessionLocal()
            try:
                result = session.execute(text("SELECT identifier FROM users LIMIT 1"))
                row = result.fetchone()
                if row:
                    return row[0]
            finally:
                session.close()
        except Exception:
            pass

        return "default"

    def get_filter(self) -> DataFilter:
        """Get current filter from database."""
        try:
            from sqlalchemy import text

            from src.database.engine import SessionLocal

            user_id = self._get_user_id()
            session = SessionLocal()
            try:
                result = session.execute(
                    text("SELECT filter_preferences FROM users WHERE identifier = :user_id"), {"user_id": user_id}
                )
                row = result.fetchone()
            finally:
                session.close()

            if row and row[0]:
                prefs = row[0]
                return DataFilter(
                    states=prefs.get("states", []),
                    fiscal_years=prefs.get("fiscal_years", []),
                    created_at=datetime.fromisoformat(prefs["created_at"]) if prefs.get("created_at") else None,
                    updated_at=datetime.fromisoformat(prefs["updated_at"]) if prefs.get("updated_at") else None,
                )
        except Exception as e:
            logger.error(f"Error loading filter: {e}")

        return DataFilter()

    def _save_filter(self, filter_obj: DataFilter):
        """Save filter to database."""
        try:
            import json
            import uuid

            from sqlalchemy import text

            from src.database.engine import SessionLocal

            user_id = self._get_user_id()
            prefs = {
                "states": filter_obj.states,
                "fiscal_years": filter_obj.fiscal_years,
                "created_at": filter_obj.created_at.isoformat() if filter_obj.created_at else None,
                "updated_at": filter_obj.updated_at.isoformat() if filter_obj.updated_at else None,
            }

            session = SessionLocal()
            try:
                session.execute(
                    text("""
                        INSERT INTO users (id, identifier, metadata, filter_preferences)
                        VALUES (:id, :identifier, '{}'::jsonb, CAST(:prefs AS jsonb))
                        ON CONFLICT (identifier)
                        DO UPDATE SET filter_preferences = EXCLUDED.filter_preferences
                    """),
                    {"id": str(uuid.uuid4()), "identifier": user_id, "prefs": json.dumps(prefs)},
                )
                session.commit()
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error saving filter: {e}", exc_info=True)

    def set_state(self, state: str) -> DataFilter:
        """Set state filter."""
        filter_obj = self.get_filter()
        filter_obj.states = [state] if state else []
        filter_obj.updated_at = datetime.now(UTC)
        if filter_obj.created_at is None:
            filter_obj.created_at = datetime.now(UTC)
        self._save_filter(filter_obj)
        return filter_obj

    def set_fiscal_year(self, year: int) -> DataFilter:
        """Set fiscal year filter."""
        filter_obj = self.get_filter()
        filter_obj.fiscal_years = [year] if year else []
        filter_obj.updated_at = datetime.now(UTC)
        if filter_obj.created_at is None:
            filter_obj.created_at = datetime.now(UTC)
        self._save_filter(filter_obj)
        return filter_obj

    def set_filter(self, state: str | None = None, fiscal_year: int | None = None) -> DataFilter:
        """Set both filters at once."""
        filter_obj = self.get_filter()
        filter_obj.states = [state] if state else []
        filter_obj.fiscal_years = [fiscal_year] if fiscal_year else []
        filter_obj.updated_at = datetime.now(UTC)
        if filter_obj.created_at is None:
            filter_obj.created_at = datetime.now(UTC)
        self._save_filter(filter_obj)
        return filter_obj

    def clear(self) -> DataFilter:
        """Clear all filters."""
        filter_obj = DataFilter()
        self._save_filter(filter_obj)
        return filter_obj

    def apply_to_sql(self, sql: str) -> str:
        """
        Apply filter to SQL query by injecting WHERE conditions.

        Handles table-specific filtering:
        - state_name only exists in 'households' table
        - For qc_errors or household_members, uses case_id subquery for state filter
        - fiscal_year exists in all tables

        Args:
            sql: Original SQL query

        Returns:
            Modified SQL with filter conditions
        """
        import re

        filter_obj = self.get_filter()

        if filter_obj.is_empty:
            return sql  # No filter, return original SQL

        # Normalize whitespace to handle newlines
        sql_normalized = " ".join(sql.split())
        sql_upper = sql_normalized.upper()

        # Get filter dimensions from active dataset
        from datasets import get_active_dataset

        ds = get_active_dataset()
        dimensions = ds.get_filter_dimensions() if ds else []

        # Build a lookup: dimension_name -> dimension config
        dim_map = {d["name"]: d for d in dimensions}

        # Determine which tables are in the query (case-insensitive)
        # Build a set of all table names mentioned in dimensions
        all_dim_tables = set()
        for d in dimensions:
            if d.get("table") and d["table"] != "*":
                all_dim_tables.add(d["table"])
        # Also discover tables from main table names
        if ds:
            for t in ds.get_main_table_names():
                all_dim_tables.add(t)

        tables_in_query = {
            t for t in all_dim_tables if re.search(rf"\b{re.escape(t)}\b", sql_normalized, re.IGNORECASE)
        }

        # Build conditions based on table context
        conditions = []

        # State filter — uses dimension config
        if filter_obj.states:
            state_dim = dim_map.get("state")
            if state_dim:
                col = state_dim["column"]
                source_table = state_dim.get("table", "")
                join_col = state_dim.get("join_column")

                # Validate state values before interpolating into SQL (security boundary)
                validated_states = [DataFilter._validate_state(s) for s in filter_obj.states]
                # Defense-in-depth: escape single quotes even though regex disallows them
                validated_states = [s.replace("'", "''") for s in validated_states]
                state_val = validated_states[0] if len(validated_states) == 1 else validated_states

                # Determine filter strategy:
                # 1. Source table is directly in query → filter on it
                # 2. Known tables in query but not source → subquery via join_column
                # 3. Unknown table/view (e.g. mv_state_error_rates) → apply column directly
                use_direct = source_table in tables_in_query or not tables_in_query
                use_subquery = not use_direct and join_col and tables_in_query

                if use_direct:
                    if isinstance(state_val, str):
                        conditions.append(f"{col} = '{state_val}'")
                    else:
                        states_str = "', '".join(state_val)
                        conditions.append(f"{col} IN ('{states_str}')")
                elif use_subquery:
                    if isinstance(state_val, str):
                        subquery = f"{join_col} IN (SELECT {join_col} FROM {source_table} WHERE {col} = '{state_val}')"
                    else:
                        states_str = "', '".join(state_val)
                        subquery = (
                            f"{join_col} IN (SELECT {join_col} FROM {source_table} WHERE {col} IN ('{states_str}'))"
                        )
                    conditions.append(subquery)

        # Fiscal year filter — uses dimension config (table="*" means all tables)
        if filter_obj.fiscal_years:
            fy_dim = dim_map.get("fiscal_year")
            if fy_dim:
                col = fy_dim["column"]
                if len(filter_obj.fiscal_years) == 1:
                    conditions.append(f"{col} = {filter_obj.fiscal_years[0]}")
                else:
                    years_str = ", ".join(map(str, filter_obj.fiscal_years))
                    conditions.append(f"{col} IN ({years_str})")

        if not conditions:
            return sql

        # Join conditions with AND
        filter_clause = " AND ".join(conditions)

        # Inject into SQL
        # Case 1: SQL already has WHERE clause
        if " WHERE " in sql_upper:
            # Add to existing WHERE with AND (case-insensitive single replacement)
            return re.sub(
                r"\s+WHERE\s+", f" WHERE ({filter_clause}) AND ", sql_normalized, count=1, flags=re.IGNORECASE
            )

        # Case 2: SQL has GROUP BY, ORDER BY, LIMIT, etc. but no WHERE
        # Insert WHERE before these clauses
        for keyword in [" GROUP BY ", " ORDER BY ", " LIMIT ", " OFFSET ", " HAVING "]:
            if keyword in sql_upper:
                # Find position (case-insensitive)
                match = re.search(keyword, sql_normalized, re.IGNORECASE)
                if match:
                    pos = match.start()
                    return sql_normalized[:pos] + f" WHERE {filter_clause} " + sql_normalized[pos:]

        # Case 3: Simple SELECT without WHERE or other clauses
        # Add WHERE at the end
        return sql_normalized.rstrip().rstrip(";") + f" WHERE {filter_clause}"


# Global filter manager instance
_filter_manager = FilterManager()


def get_filter_manager() -> FilterManager:
    """Get global filter manager instance."""
    return _filter_manager
