"""
Global Filter Manager for SnapAnalyst

Provides application-level filtering that applies to all queries and exports.
Filter persists until application restart.

Designed for extensibility - can easily support multiple states/years in future.
"""
from typing import Optional, List, Dict, Any
from threading import Lock
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DataFilter:
    """
    Application-level data filter.
    
    Currently supports single state/year, but designed for future multi-select.
    """
    states: List[str] = field(default_factory=list)  # Future: multiple states
    fiscal_years: List[int] = field(default_factory=list)  # Future: multiple years
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def state(self) -> Optional[str]:
        """Get single state (current implementation)."""
        return self.states[0] if self.states else None
    
    @property
    def fiscal_year(self) -> Optional[int]:
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
    
    def to_dict(self) -> Dict[str, Any]:
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
    
    def get_sql_conditions(self) -> List[str]:
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
    """
    Thread-safe global filter manager.
    
    Maintains application-level filter state that persists until restart.
    """
    
    def __init__(self):
        self._filter = DataFilter()
        self._lock = Lock()
    
    def get_filter(self) -> DataFilter:
        """Get current filter (thread-safe)."""
        with self._lock:
            return DataFilter(
                states=self._filter.states.copy(),
                fiscal_years=self._filter.fiscal_years.copy(),
                created_at=self._filter.created_at,
                updated_at=self._filter.updated_at,
            )
    
    def set_state(self, state: str) -> DataFilter:
        """
        Set state filter (single state for now).
        
        Args:
            state: State name (e.g., "Connecticut")
            
        Returns:
            Updated filter
        """
        with self._lock:
            self._filter.states = [state] if state else []
            self._filter.updated_at = datetime.now()
            if self._filter.created_at is None:
                self._filter.created_at = datetime.now()
            return self.get_filter()
    
    def set_fiscal_year(self, year: int) -> DataFilter:
        """
        Set fiscal year filter (single year for now).
        
        Args:
            year: Fiscal year (e.g., 2023)
            
        Returns:
            Updated filter
        """
        with self._lock:
            self._filter.fiscal_years = [year] if year else []
            self._filter.updated_at = datetime.now()
            if self._filter.created_at is None:
                self._filter.created_at = datetime.now()
            return self.get_filter()
    
    def set_filter(self, state: Optional[str] = None, fiscal_year: Optional[int] = None) -> DataFilter:
        """
        Set both filters at once.
        
        Args:
            state: State name or None to clear
            fiscal_year: Fiscal year or None to clear
            
        Returns:
            Updated filter
        """
        with self._lock:
            self._filter.states = [state] if state else []
            self._filter.fiscal_years = [fiscal_year] if fiscal_year else []
            self._filter.updated_at = datetime.now()
            if self._filter.created_at is None:
                self._filter.created_at = datetime.now()
            return self.get_filter()
    
    def clear(self) -> DataFilter:
        """Clear all filters."""
        with self._lock:
            self._filter = DataFilter()
            return self.get_filter()
    
    def apply_to_sql(self, sql: str) -> str:
        """
        Apply filter to SQL query by injecting WHERE conditions.
        
        Args:
            sql: Original SQL query
            
        Returns:
            Modified SQL with filter conditions
        """
        filter_obj = self.get_filter()
        
        if filter_obj.is_empty:
            return sql  # No filter, return original SQL
        
        conditions = filter_obj.get_sql_conditions()
        
        if not conditions:
            return sql
        
        # Join conditions with AND
        filter_clause = " AND ".join(conditions)
        
        # Inject into SQL
        sql_upper = sql.upper()
        
        # Case 1: SQL already has WHERE clause
        if " WHERE " in sql_upper:
            # Add to existing WHERE with AND
            return sql.replace(" WHERE ", f" WHERE ({filter_clause}) AND ", 1).replace(" where ", f" WHERE ({filter_clause}) AND ", 1)
        
        # Case 2: SQL has GROUP BY, ORDER BY, LIMIT, etc. but no WHERE
        # Insert WHERE before these clauses
        for keyword in [" GROUP BY ", " ORDER BY ", " LIMIT ", " OFFSET ", " HAVING "]:
            if keyword in sql_upper:
                # Find position (case-insensitive)
                import re
                match = re.search(keyword, sql, re.IGNORECASE)
                if match:
                    pos = match.start()
                    return sql[:pos] + f" WHERE {filter_clause} " + sql[pos:]
        
        # Case 3: Simple SELECT without WHERE or other clauses
        # Add WHERE at the end
        return sql.rstrip().rstrip(';') + f" WHERE {filter_clause}"


# Global filter manager instance
_filter_manager = FilterManager()


def get_filter_manager() -> FilterManager:
    """Get global filter manager instance."""
    return _filter_manager
