"""
Formatters

HTML and display formatting utilities for the Chainlit UI.
Uses centralized message templates from src/core/prompts.py.
Column display formats are loaded from datasets/snap/data_mapping.json.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import chainlit as cl
import sqlparse

from src.core.logging import get_logger
from src.core.prompts import MSG_EXPORT_STATS

logger = get_logger(__name__)

# Path to data mapping configuration
DATA_MAPPING_PATH = Path(__file__).parent.parent / "datasets" / "snap" / "data_mapping.json"


def format_sql_display(sql: str) -> str:
    """
    Format SQL for display with proper indentation and line breaks.

    Args:
        sql: Raw SQL query string

    Returns:
        Formatted SQL string with proper indentation
    """
    try:
        formatted = sqlparse.format(sql, reindent=True, keyword_case="upper", indent_width=2, wrap_after=80)
        return formatted
    except Exception as e:
        logger.warning(f"Could not format SQL: {e}")
        return sql


@lru_cache(maxsize=1)
def _load_column_formats() -> dict[str, set[str]]:
    """
    Load column display formats from data_mapping.json.
    Results are cached for performance.

    Returns:
        Dictionary mapping format type to set of column names
    """
    formats: dict[str, set[str]] = {
        "integer": set(),  # Counts with comma separators
        "rawint": set(),  # Codes/dates without comma separators
        "year": set(),  # Years without comma separators
        "currency": set(),
        "weight": set(),
        "text": set(),
        "boolean": set(),
        "datetime": set(),
    }

    try:
        if DATA_MAPPING_PATH.exists():
            with open(DATA_MAPPING_PATH) as f:
                data = json.load(f)

            display_formats = data.get("column_display_formats", {})
            for format_type, config in display_formats.items():
                if format_type.startswith("_"):
                    continue  # Skip description fields
                if isinstance(config, dict) and "columns" in config:
                    formats[format_type] = {col.lower() for col in config["columns"]}

            logger.debug(f"Loaded column formats from {DATA_MAPPING_PATH}")
        else:
            logger.warning(f"Data mapping file not found: {DATA_MAPPING_PATH}")
    except Exception as e:
        logger.error(f"Failed to load column formats: {e}")

    return formats


def get_column_format(column_name: str) -> str:
    """
    Get the display format for a column.
    Uses explicit mappings from data_mapping.json, plus pattern-based fallbacks
    for aggregate columns (avg_*, sum_*, total_*, average_*).

    Args:
        column_name: The column name to look up

    Returns:
        Format type: 'integer', 'currency', 'weight', 'text', 'boolean', 'datetime', or 'default'
    """
    formats = _load_column_formats()
    column_lower = column_name.lower()

    # First check explicit mappings
    for format_type, columns in formats.items():
        if column_lower in columns:
            return format_type

    # Conservative approach: ONLY use explicit mappings from data_mapping.json
    # No pattern matching or guessing - if we don't know, show raw value
    return "default"


def format_cell_value(value, format_type: str) -> str:
    """
    Format a cell value based on the format type.

    Args:
        value: The raw cell value
        format_type: The format type ('integer', 'currency', 'weight', 'text', 'boolean', 'datetime', 'default')

    Returns:
        Formatted string for display
    """
    if value is None:
        return '<span style="color: #94a3b8; font-style: italic;">NULL</span>'

    try:
        if format_type == "year":
            # Display as year WITHOUT comma separators (e.g., 2023 not 2,023)
            try:
                int_val = int(float(value))
                return str(int_val)
            except (ValueError, TypeError):
                return str(value)

        elif format_type == "rawint":
            # Display as integer WITHOUT comma separators (for codes, YYYYMMDD dates, etc.)
            try:
                int_val = int(float(value))
                return str(int_val)
            except (ValueError, TypeError):
                return str(value)

        elif format_type == "integer":
            # Display as whole number with comma separators, strip any decimal places
            try:
                int_val = int(float(value))
                return f"{int_val:,}"
            except (ValueError, TypeError):
                return str(value)

        elif format_type == "currency":
            # Display with dollar sign and 2 decimal places
            # Handle negative values properly: -$100.50 not $-100.50
            float_val = float(value)
            if float_val < 0:
                return f"-${abs(float_val):,.2f}"
            return f"${float_val:,.2f}"

        elif format_type == "weight":
            # Display with 4 decimal places for statistical weights
            return f"{float(value):,.4f}"

        elif format_type == "decimal":
            # Display with 2 decimal places for averages and aggregates
            try:
                float_val = float(value)
                return f"{float_val:,.2f}"
            except (ValueError, TypeError):
                return str(value)

        elif format_type == "boolean":
            # Display as Yes/No
            if isinstance(value, bool):
                return "Yes" if value else "No"
            elif str(value).lower() in ("true", "1", "yes"):
                return "Yes"
            elif str(value).lower() in ("false", "0", "no"):
                return "No"
            return str(value)

        elif format_type == "datetime":
            # Display datetime in clean format
            from datetime import datetime

            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d %H:%M")
            # Try to parse string datetime
            str_val = str(value)
            # Remove microseconds if present
            if "." in str_val:
                str_val = str_val.split(".")[0]
            return str_val

        elif format_type == "text":
            # Display as-is
            return str(value)

        else:  # "default"
            # Smart formatting: only format actual floats that aren't whole numbers
            if isinstance(value, float):
                if value == int(value):
                    return f"{int(value):,}"
                return f"{value:,.2f}"
            elif isinstance(value, int):
                return f"{value:,}"
            return str(value)

    except (ValueError, TypeError):
        return str(value)


def format_sql_results(results: list[dict], row_count: int) -> str:
    """
    Format SQL results using Tabulator for a modern, sortable, paginated table.
    Data values are pre-formatted using column_display_formats from data_mapping.json.

    Args:
        results: List of result dictionaries
        row_count: Total number of rows

    Returns:
        HTML string containing the table container and data
    """
    if not results or len(results) == 0:
        return "<p>No results returned.</p>"

    # Generate unique ID for this table instance
    import uuid

    table_id = f"table-{str(uuid.uuid4())[:8]}"

    # Pre-format data using Python's format mapping from data_mapping.json
    formatted_results = []
    for row in results:
        formatted_row = {}
        for col_name, value in row.items():
            # Get format type from data_mapping.json
            format_type = get_column_format(col_name)
            # Format the value (but don't use HTML for Tabulator, just plain text)
            formatted_row[col_name] = _format_for_tabulator(value, format_type)
        formatted_results.append(formatted_row)

    # Escape </script> sequences to prevent breaking out of the JSON script tag
    json_data = json.dumps(formatted_results, default=str).replace("</", "<\\/")

    # Use textwrap.dedent to ensure no leading whitespace makes it into Markdown
    from textwrap import dedent

    html = dedent(f'''
    <div class="tabulator-container">
        <div id="{table_id}" style="min-height: 50px;">Loading table...</div>
        <script id="data-{table_id}" type="application/json">
            {json_data}
        </script>
    </div>
    ''')

    return html


def _format_for_tabulator(value, format_type: str) -> str:
    """
    Format a cell value for Tabulator display (plain text, no HTML).
    Uses format definitions from data_mapping.json.

    Args:
        value: The raw cell value
        format_type: The format type from data_mapping.json

    Returns:
        Formatted string for display
    """
    if value is None:
        return ""

    try:
        if format_type == "year":
            # Display as year WITHOUT comma separators (e.g., 2023 not 2,023)
            try:
                int_val = int(float(value))
                return str(int_val)
            except (ValueError, TypeError):
                return str(value)

        elif format_type == "rawint":
            # Display as integer WITHOUT comma separators (for codes, YYYYMMDD dates, etc.)
            try:
                int_val = int(float(value))
                return str(int_val)
            except (ValueError, TypeError):
                return str(value)

        elif format_type == "integer":
            # Display as whole number with comma separators
            try:
                int_val = int(float(value))
                return f"{int_val:,}"
            except (ValueError, TypeError):
                return str(value)

        elif format_type == "currency":
            # Display with dollar sign and 2 decimal places
            float_val = float(value)
            if float_val < 0:
                return f"-${abs(float_val):,.2f}"
            return f"${float_val:,.2f}"

        elif format_type == "weight":
            # Display with 4 decimal places for statistical weights
            return f"{float(value):,.4f}"

        elif format_type == "boolean":
            # Display as Yes/No
            if isinstance(value, bool):
                return "Yes" if value else "No"
            elif str(value).lower() in ("true", "1", "yes"):
                return "Yes"
            elif str(value).lower() in ("false", "0", "no"):
                return "No"
            return str(value)

        elif format_type == "datetime":
            # Display datetime in clean format
            from datetime import datetime

            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d %H:%M")
            str_val = str(value)
            if "." in str_val:
                str_val = str_val.split(".")[0]
            return str_val

        elif format_type == "text":
            return str(value)

        else:  # "default" - smart formatting for numeric types
            # Handle float and int types (Decimal is converted to float by API)
            if isinstance(value, float):
                # Check if it's a whole number
                if value == int(value):
                    return f"{int(value):,}"
                # Format with 2 decimal places
                return f"{value:,.2f}"
            elif isinstance(value, int):
                return f"{value:,}"
            # Non-numeric values - return as-is
            return str(value)

    except (ValueError, TypeError):
        return str(value)


def clear_format_cache():
    """Clear the cached column formats. Call this if data_mapping.json is updated."""
    _load_column_formats.cache_clear()
    logger.info("Column format cache cleared")


def get_filter_indicator() -> str:
    """
    Get the active filter indicator HTML if a filter is active.

    Returns:
        HTML string for filter indicator, or empty string if no filter
    """
    state_filter = cl.user_session.get("current_state_filter", "All States")
    year_filter = cl.user_session.get("current_year_filter", "All Years")

    # Build filter parts
    filter_parts = []
    if state_filter and state_filter != "All States":
        filter_parts.append(state_filter)
    if year_filter and year_filter != "All Years":
        filter_parts.append(f"FY{year_filter}")

    # Return indicator HTML only if filter is active
    if filter_parts:
        from html import escape

        safe_parts = [escape(p) for p in filter_parts]
        return f'<div style="text-align: center; font-size: 11px; color: #666; padding: 8px; margin-top: 16px; border-top: 1px solid #eee;">Active Filter: {" | ".join(safe_parts)}</div>'
    return ""


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "2.4 KB", "1.2 MB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_table_stats(headers: list[str], row_count: int, file_size_kb: float) -> str:
    """
    Format table statistics for display.
    Uses template from src/core/prompts.py.

    Args:
        headers: List of column names
        row_count: Number of rows
        file_size_kb: File size in KB

    Returns:
        Formatted statistics string
    """
    return MSG_EXPORT_STATS.format(row_count=row_count, column_count=len(headers), file_size_kb=file_size_kb)
