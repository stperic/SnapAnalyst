"""
Global Filter Manager for SnapAnalyst

Provides per-user filtering that applies to all queries and exports.
Filters are stored in database (persists across sessions).

Designed for extensibility - can easily support multiple states/years in future.
"""
from dataclasses import dataclass, field
from datetime import datetime
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

    def get_sql_conditions(self) -> list[str]:
        """
        Get SQL WHERE conditions for this filter.

        Returns:
            List of SQL conditions (e.g., ["state_name = 'Connecticut'", "fiscal_year = 2023"])
        """
        conditions = []

        if self.states:
            # Current: single state
            # Future: state_name IN ('CT', 'MA', 'NY')
            if len(self.states) == 1:
                conditions.append(f"state_name = '{self.states[0]}'")
            else:
                states_str = "', '".join(self.states)
                conditions.append(f"state_name IN ('{states_str}')")

        if self.fiscal_years:
            # Current: single year
            # Future: fiscal_year IN (2021, 2022, 2023)
            if len(self.fiscal_years) == 1:
                conditions.append(f"fiscal_year = {self.fiscal_years[0]}")
            else:
                years_str = ", ".join(map(str, self.fiscal_years))
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
                years = ', '.join(f"FY{y}" for y in self.fiscal_years)
                parts.append(f"Years: {years}")

        return " | ".join(parts)


class FilterManager:
    """Simple per-user filter manager with database persistence."""

    def _get_user_id(self) -> str:
        """Get current user ID from Chainlit session."""
        try:
            import chainlit as cl
            user = cl.user_session.get("user")
            if user and hasattr(user, 'identifier'):
                return user.identifier
        except Exception:
            pass

        # Fallback: use first user in database
        try:
            from sqlalchemy import text

            from src.database.engine import SessionLocal
            session = SessionLocal()
            result = session.execute(text("SELECT identifier FROM users LIMIT 1"))
            row = result.fetchone()
            session.close()
            if row:
                return row[0]
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
            result = session.execute(
                text("SELECT filter_preferences FROM users WHERE identifier = :user_id"),
                {"user_id": user_id}
            )
            row = result.fetchone()
            session.close()

            if row and row[0]:
                prefs = row[0]
                return DataFilter(
                    states=prefs.get('states', []),
                    fiscal_years=prefs.get('fiscal_years', []),
                    created_at=datetime.fromisoformat(prefs['created_at']) if prefs.get('created_at') else None,
                    updated_at=datetime.fromisoformat(prefs['updated_at']) if prefs.get('updated_at') else None,
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
                'states': filter_obj.states,
                'fiscal_years': filter_obj.fiscal_years,
                'created_at': filter_obj.created_at.isoformat() if filter_obj.created_at else None,
                'updated_at': filter_obj.updated_at.isoformat() if filter_obj.updated_at else None,
            }

            session = SessionLocal()
            session.execute(
                text("""
                    INSERT INTO users (id, identifier, metadata, filter_preferences)
                    VALUES (:id, :identifier, '{}'::jsonb, CAST(:prefs AS jsonb))
                    ON CONFLICT (identifier)
                    DO UPDATE SET filter_preferences = EXCLUDED.filter_preferences
                """),
                {"id": str(uuid.uuid4()), "identifier": user_id, "prefs": json.dumps(prefs)}
            )
            session.commit()
            session.close()
        except Exception as e:
            logger.error(f"Error saving filter: {e}", exc_info=True)

    def set_state(self, state: str) -> DataFilter:
        """Set state filter."""
        filter_obj = self.get_filter()
        filter_obj.states = [state] if state else []
        filter_obj.updated_at = datetime.now()
        if filter_obj.created_at is None:
            filter_obj.created_at = datetime.now()
        self._save_filter(filter_obj)
        return filter_obj

    def set_fiscal_year(self, year: int) -> DataFilter:
        """Set fiscal year filter."""
        filter_obj = self.get_filter()
        filter_obj.fiscal_years = [year] if year else []
        filter_obj.updated_at = datetime.now()
        if filter_obj.created_at is None:
            filter_obj.created_at = datetime.now()
        self._save_filter(filter_obj)
        return filter_obj

    def set_filter(self, state: str | None = None, fiscal_year: int | None = None) -> DataFilter:
        """Set both filters at once."""
        filter_obj = self.get_filter()
        filter_obj.states = [state] if state else []
        filter_obj.fiscal_years = [fiscal_year] if fiscal_year else []
        filter_obj.updated_at = datetime.now()
        if filter_obj.created_at is None:
            filter_obj.created_at = datetime.now()
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
        sql_normalized = ' '.join(sql.split())
        sql_upper = sql_normalized.upper()

        # Determine which tables are in the query (case-insensitive)
        has_households = bool(re.search(r'\bhouseholds\b', sql_normalized, re.IGNORECASE))
        has_qc_errors = bool(re.search(r'\bqc_errors\b', sql_normalized, re.IGNORECASE))
        has_members = bool(re.search(r'\bhousehold_members\b', sql_normalized, re.IGNORECASE))

        # Build conditions based on table context
        conditions = []

        # State filter - state_name only exists in households table
        if filter_obj.states:
            state_val = filter_obj.states[0] if len(filter_obj.states) == 1 else filter_obj.states

            if has_households:
                # Direct filter on households table
                if isinstance(state_val, str):
                    conditions.append(f"state_name = '{state_val}'")
                else:
                    states_str = "', '".join(state_val)
                    conditions.append(f"state_name IN ('{states_str}')")
            elif has_qc_errors or has_members:
                # Need subquery to filter by state via case_id
                if isinstance(state_val, str):
                    subquery = f"case_id IN (SELECT case_id FROM households WHERE state_name = '{state_val}')"
                else:
                    states_str = "', '".join(state_val)
                    subquery = f"case_id IN (SELECT case_id FROM households WHERE state_name IN ('{states_str}'))"
                conditions.append(subquery)

        # Fiscal year filter - exists in all tables
        if filter_obj.fiscal_years:
            if len(filter_obj.fiscal_years) == 1:
                conditions.append(f"fiscal_year = {filter_obj.fiscal_years[0]}")
            else:
                years_str = ", ".join(map(str, filter_obj.fiscal_years))
                conditions.append(f"fiscal_year IN ({years_str})")

        if not conditions:
            return sql

        # Join conditions with AND
        filter_clause = " AND ".join(conditions)

        # Inject into SQL
        # Case 1: SQL already has WHERE clause
        if " WHERE " in sql_upper:
            # Add to existing WHERE with AND (case-insensitive single replacement)
            return re.sub(r'\s+WHERE\s+', f' WHERE ({filter_clause}) AND ', sql_normalized, count=1, flags=re.IGNORECASE)

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
        return sql_normalized.rstrip().rstrip(';') + f" WHERE {filter_clause}"


# Global filter manager instance
_filter_manager = FilterManager()


def get_filter_manager() -> FilterManager:
    """Get global filter manager instance."""
    return _filter_manager
