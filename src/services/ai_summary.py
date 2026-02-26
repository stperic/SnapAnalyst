"""
AI Summary Service

Generates AI-powered summaries for SQL query results using the configured LLM,
with a simple template fallback when AI summaries are disabled or fail.

Uses centralized templates from src/core/prompts.py.
"""

import asyncio
import json

from ..core.config import settings
from ..core.logging import get_logger
from ..core.prompts import (
    CODE_REFERENCE_FOOTER,
    CODE_REFERENCE_HEADER,
    SIMPLE_SUMMARY_TEMPLATES,
    build_ai_summary_prompt,
)
from .code_enrichment import enrich_results_with_code_descriptions  # noqa: F401 - re-exported via src.services

logger = get_logger(__name__)


async def generate_ai_summary(
    question: str,
    sql: str,
    results: list[dict],
    row_count: int,
    filters: str = "",
    llm_params: dict | None = None,
    user_id: str | None = None,
) -> str:
    """
    Generate AI summary of query results.

    When LLM_SQL_SUMMARY_ENABLED=true (default), sends the question, SQL, and
    a sample of results to the LLM for a natural language summary.
    Falls back to simple templates when disabled, on error, or for empty results.

    Args:
        question: User's SQL question
        sql: SQL query executed
        results: Query results
        row_count: Number of rows returned
        filters: Active filters description
        llm_params: Optional per-request LLM parameters (for context-window-aware sizing)

    Returns:
        AI-generated summary text or simple fallback
    """
    try:
        if row_count == 0:
            filter_text = f" (filtered by {filters})" if filters else ""
            return SIMPLE_SUMMARY_TEMPLATES["no_results"].format(filter_text=filter_text)

        # Check per-session override, fall back to server config
        summary_enabled = (llm_params or {}).get("summary_enabled")
        if summary_enabled is None:
            summary_enabled = settings.llm_sql_summary_enabled
        logger.debug(f"AI summary enabled={summary_enabled} (session={llm_params.get('summary_enabled') if llm_params else None}, config={settings.llm_sql_summary_enabled})")
        if not summary_enabled:
            return generate_simple_summary(question, row_count, results, filters)

        # Determine how many rows to send based on context window budget
        max_rows = (llm_params or {}).get("summary_max_rows") or settings.llm_sql_summary_max_rows
        context_window = (llm_params or {}).get("context_window") or 0
        if context_window and context_window > 0:
            # Larger context = more rows. Reserve ~50% for results.
            available_chars = int((context_window - 2000) * 4 * 0.5)  # 50% of input budget
            # Estimate ~200 chars per row on average
            max_rows = min(max_rows, max(10, available_chars // 200))

        # Truncate results to budget
        sample_results = _format_results_for_llm(results[:max_rows])
        data_context = json.dumps(sample_results, default=str)

        # Build the prompt (returns system, user tuple)
        # Use per-user summary prompt if available
        custom_system_prompt = None
        if user_id:
            try:
                from src.database.prompt_manager import get_user_prompt

                custom_system_prompt = get_user_prompt(user_id, "summary")
            except Exception as e:
                logger.warning(f"Failed to get custom summary prompt for {user_id}: {e}")

        system_message, user_message = build_ai_summary_prompt(
            question=question,
            data_context=data_context,
            filters=filters,
            sql=sql,
            system_prompt_override=custom_system_prompt,
        )

        # Call LLM in a thread to avoid blocking
        from .llm_service import get_llm_service

        llm_service = get_llm_service()

        summary = await asyncio.to_thread(
            llm_service.generate_text,
            user_message,
            settings.effective_sql_max_tokens,
            llm_params,
            system_message,
        )

        if summary and not summary.startswith("**LLM Error**"):
            truncation_note = ""
            if row_count > max_rows:
                truncation_note = f"\n\n*Summary based on {max_rows} of {row_count:,} rows.*"
            logger.info(f"AI summary generated ({len(summary)} chars, {max_rows} rows sent)")
            return summary + truncation_note

        # LLM failed, fall back to simple
        error_detail = summary[:200] if summary else "No response"
        logger.warning(f"AI summary LLM call failed, falling back to template: {error_detail}")
        return generate_simple_summary(question, row_count, results, filters)

    except Exception as e:
        logger.error(f"AI summary error, falling back to template: {e}")
        return generate_simple_summary(question, row_count, results, filters)


def generate_simple_summary(question: str, row_count: int, results: list[dict], filters: str = "") -> str:
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
            return SIMPLE_SUMMARY_TEMPLATES["single_result"].format(value=formatted_value, filter_text=filter_text)
        return SIMPLE_SUMMARY_TEMPLATES["few_results"].format(count=format_number(1), filter_text=filter_text)
    elif row_count <= 10:
        return SIMPLE_SUMMARY_TEMPLATES["few_results"].format(count=format_number(row_count), filter_text=filter_text)
    elif row_count <= 100:
        return SIMPLE_SUMMARY_TEMPLATES["medium_results"].format(
            count=format_number(row_count), filter_text=filter_text
        )
    else:
        return SIMPLE_SUMMARY_TEMPLATES["large_results"].format(count=format_number(row_count), filter_text=filter_text)


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
