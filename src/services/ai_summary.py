"""
AI Summary Service

Generates simple template-based summaries for query results.
Uses centralized templates from src/core/prompts.py.

Note: Helper functions (_format_results_for_llm, _build_code_reference) are kept
for potential future use and for test compatibility.
"""

import json  # noqa: F401 - Used by helper functions
import logging

from ..core.prompts import (
    CODE_REFERENCE_FOOTER,  # noqa: F401 - Used by helper functions
    CODE_REFERENCE_HEADER,  # noqa: F401 - Used by helper functions
    SIMPLE_SUMMARY_TEMPLATES,
)
from .code_enrichment import enrich_results_with_code_descriptions  # noqa: F401 - Used by helper functions

logger = logging.getLogger(__name__)


async def generate_ai_summary(
    question: str,
    sql: str,
    results: list[dict],
    row_count: int,
    filters: str = ""
) -> str:
    """
    Generate AI summary of query results using dynamic prompt sizing.

    Strategy:
    1. Always format full dataset
    2. Build complete prompt
    3. Check if prompt size is under limit (configured in .env)
    4. If yes: send to LLM for AI summary
    5. If no: use simple fallback message

    Args:
        question: User's SQL question
        sql: SQL query executed
        results: Query results
        row_count: Number of rows returned
        filters: Active filters description

    Returns:
        AI-generated summary text or simple fallback
    """
    try:
        # Determine approach based on result size
        if row_count == 0:
            return SIMPLE_SUMMARY_TEMPLATES["no_results"]

        # Use simple template-based summary for all regular queries
        # AI-powered summaries are only used by /? and /?? KB commands
        return generate_simple_summary(question, row_count, results, filters)

    except Exception as e:
        logger.error(f"Error generating AI summary: {e}")
        return generate_simple_summary(question, row_count, results, filters)


def generate_simple_summary(
    question: str,
    row_count: int,
    results: list[dict],
    filters: str = ""
) -> str:
    """
    Generate a simple fallback summary without LLM.

    Uses templates from src/core/prompts.py.

    Args:
        question: User's question
        row_count: Number of rows
        results: Query results
        filters: Active filters description

    Returns:
        Simple summary string
    """
    def format_number(value):
        """Format number with commas for readability."""
        try:
            if isinstance(value, (int, float)):
                return f"{value:,}"
            return value
        except (ValueError, TypeError):
            return value

    filter_text = f" (filtered by {filters})" if filters else ""

    if row_count == 1:
        if results and len(results[0]) == 1:
            value = list(results[0].values())[0]
            formatted_value = format_number(value)
            return SIMPLE_SUMMARY_TEMPLATES["single_result"].format(
                value=formatted_value, filter_text=filter_text
            )
        return SIMPLE_SUMMARY_TEMPLATES["few_results"].format(
            count=format_number(1), filter_text=filter_text
        )
    elif row_count <= 10:
        return SIMPLE_SUMMARY_TEMPLATES["few_results"].format(
            count=format_number(row_count), filter_text=filter_text
        )
    elif row_count <= 100:
        return SIMPLE_SUMMARY_TEMPLATES["medium_results"].format(
            count=format_number(row_count), filter_text=filter_text
        )
    else:
        return SIMPLE_SUMMARY_TEMPLATES["large_results"].format(
            count=format_number(row_count), filter_text=filter_text
        )


def _format_results_for_llm(data: list[dict]) -> list[dict]:
    """
    Format numeric values to 2 decimals to reduce tokens and improve readability.
    """
    formatted = []
    for row in data:
        formatted_row = {}
        for key, value in row.items():
            try:
                if isinstance(value, float):
                    formatted_row[key] = round(value, 2)
                elif isinstance(value, str):
                    float_val = float(value)
                    formatted_row[key] = round(float_val, 2)
                else:
                    formatted_row[key] = value
            except (ValueError, TypeError):
                formatted_row[key] = value
        formatted.append(formatted_row)
    return formatted


def _build_code_reference(code_enrichment: dict[str, dict[str, str]]) -> str:
    """
    Build code reference section for LLM prompt.

    Uses header/footer from src/core/prompts.py.
    """
    if not code_enrichment:
        return ""

    code_reference = CODE_REFERENCE_HEADER

    for col_name, code_dict in code_enrichment.items():
        code_reference += f"\n{col_name.replace('_', ' ').title()}:\n"

        # Sort codes numerically
        def numeric_sort_key(item):
            code = item[0]
            try:
                return (0, int(code))
            except (ValueError, TypeError):
                return (1, code)

        for code, description in sorted(code_dict.items(), key=numeric_sort_key):
            code_reference += f"  - Code {code}: {description}\n"

    code_reference += CODE_REFERENCE_FOOTER

    return code_reference
