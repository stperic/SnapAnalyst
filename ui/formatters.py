"""
Formatters

HTML and display formatting utilities for the Chainlit UI.
Uses centralized message templates from src/core/prompts.py.
Column display formats are loaded from datasets/snap/data_mapping.json.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set

import chainlit as cl
import sqlparse

from .config import MAX_DISPLAY_ROWS
from src.core.prompts import MSG_EXPORT_STATS

logger = logging.getLogger(__name__)

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
        formatted = sqlparse.format(
            sql,
            reindent=True,
            keyword_case='upper',
            indent_width=2,
            wrap_after=80
        )
        return formatted
    except Exception as e:
        logger.warning(f"Could not format SQL: {e}")
        return sql


@lru_cache(maxsize=1)
def _load_column_formats() -> Dict[str, Set[str]]:
    """
    Load column display formats from data_mapping.json.
    Results are cached for performance.
    
    Returns:
        Dictionary mapping format type to set of column names
    """
    formats: Dict[str, Set[str]] = {
        "integer": set(),
        "currency": set(),
        "weight": set(),
        "text": set(),
        "boolean": set(),
        "datetime": set(),
    }
    
    try:
        if DATA_MAPPING_PATH.exists():
            with open(DATA_MAPPING_PATH, 'r') as f:
                data = json.load(f)
            
            display_formats = data.get("column_display_formats", {})
            for format_type, config in display_formats.items():
                if format_type.startswith("_"):
                    continue  # Skip description fields
                if isinstance(config, dict) and "columns" in config:
                    formats[format_type] = set(col.lower() for col in config["columns"])
            
            logger.debug(f"Loaded column formats from {DATA_MAPPING_PATH}")
        else:
            logger.warning(f"Data mapping file not found: {DATA_MAPPING_PATH}")
    except Exception as e:
        logger.error(f"Failed to load column formats: {e}")
    
    return formats


def get_column_format(column_name: str) -> str:
    """
    Get the display format for a column.
    
    Args:
        column_name: The column name to look up
        
    Returns:
        Format type: 'integer', 'currency', 'weight', 'text', 'boolean', 'datetime', or 'default'
    """
    formats = _load_column_formats()
    column_lower = column_name.lower()
    
    for format_type, columns in formats.items():
        if column_lower in columns:
            return format_type
    
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
        if format_type == "integer":
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
        
        elif format_type == "boolean":
            # Display as Yes/No
            if isinstance(value, bool):
                return "Yes" if value else "No"
            elif str(value).lower() in ('true', '1', 'yes'):
                return "Yes"
            elif str(value).lower() in ('false', '0', 'no'):
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
            if '.' in str_val:
                str_val = str_val.split('.')[0]
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


def format_sql_results(results: List[Dict], row_count: int) -> str:
    """
    Format SQL results as modern HTML table.
    Column formatting is loaded from data_mapping.json.
    CSV is created on-demand when user clicks the download button.
    
    Args:
        results: List of result dictionaries
        row_count: Total number of rows
        
    Returns:
        HTML table string
    """
    if not results or len(results) == 0:
        return "<p>No results returned.</p>"
    
    headers = list(results[0].keys())
    
    # Pre-compute format types for all headers
    header_formats = {header: get_column_format(header) for header in headers}
    
    # Modern table with compact styling
    html = '''
<div style="overflow-x: auto; margin: 10px 0;">
    <table class="sortable-table" style="width: 100%; border-collapse: collapse; font-size: 11px; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <thead>
            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'''
    
    # Headers
    for idx, header in enumerate(headers):
        html += f'<th data-column="{idx}" style="padding: 2px 6px; text-align: left; font-weight: 600; color: #475569; white-space: nowrap; cursor: pointer; user-select: none;" class="sortable-header">{header} <span style="color: #94a3b8; font-size: 9px;">⇅</span></th>'
    html += "</tr></thead><tbody>"
    
    # Ultra-compact rows (limit to MAX_DISPLAY_ROWS)
    for idx, row_dict in enumerate(results[:MAX_DISPLAY_ROWS]):
        bg = "#ffffff" if idx % 2 == 0 else "#f8fafc"
        html += f'<tr style="background: {bg}; border-bottom: 1px solid #e2e8f0;">'
        for header in headers:
            cell = row_dict.get(header)
            format_type = header_formats[header]
            cell_value = format_cell_value(cell, format_type)
            html += f'<td style="padding: 2px 6px; color: #1e293b; line-height: 1.2;">{cell_value}</td>'
        html += "</tr>"
    html += "</tbody></table></div>"
    
    if row_count > MAX_DISPLAY_ROWS:
        html += f'<div style="margin: 10px 0; padding: 8px 12px; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px; font-size: 13px;">📊 Showing first <strong>{MAX_DISPLAY_ROWS}</strong> of <strong>{row_count:,}</strong> rows in table. CSV download includes all {row_count:,} rows.</div>'
    
    return html


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
        return f'<div style="text-align: center; font-size: 11px; color: #666; padding: 8px; margin-top: 16px; border-top: 1px solid #eee;">🔍 Active Filter: {" | ".join(filter_parts)}</div>'
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


def format_table_stats(headers: List[str], row_count: int, file_size_kb: float) -> str:
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
    return MSG_EXPORT_STATS.format(
        row_count=row_count,
        column_count=len(headers),
        file_size_kb=file_size_kb
    )
