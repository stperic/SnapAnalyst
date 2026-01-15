"""
AI Summary Service

Generates AI-powered summaries of query results using dynamic prompt sizing.
Uses centralized prompts from src/core/prompts.py.
"""

import json
import logging
from typing import Dict, List, Optional

from ..clients.api_client import call_api
from ..core.prompts import (
    build_ai_summary_prompt,
    SIMPLE_SUMMARY_TEMPLATES,
    CODE_REFERENCE_HEADER,
    CODE_REFERENCE_FOOTER,
)
from .code_enrichment import enrich_results_with_code_descriptions

logger = logging.getLogger(__name__)


async def generate_ai_summary(
    question: str,
    sql: str,
    results: List[Dict],
    row_count: int,
    filters: str = "",
    analysis_instructions: Optional[str] = None
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
        question: User's SQL question (left of | separator)
        sql: SQL query executed
        results: Query results
        row_count: Number of rows returned
        filters: Active filters description
        analysis_instructions: Special analysis instructions (right of | separator)
    
    Returns:
        AI-generated summary text or simple fallback
    """
    try:
        # Import settings for dynamic limit
        from ..core.config import settings
        
        # Determine approach based on result size
        if row_count == 0:
            return SIMPLE_SUMMARY_TEMPLATES["no_results"]
        
        # Special case: single row with single column (like COUNT queries)
        if row_count == 1 and results and len(results[0]) == 1:
            column_name = list(results[0].keys())[0]
            value = list(results[0].values())[0]
            filter_text = f" (filtered by {filters})" if filters else ""
            return f"**{value:,}** {column_name.replace('_', ' ')}{filter_text}."
        
        # Format results for LLM
        formatted_results = _format_results_for_llm(results)
        
        # Check for code columns and enrich with descriptions
        code_enrichment = enrich_results_with_code_descriptions(results)
        
        # Build code reference section if codes are present
        code_reference = _build_code_reference(code_enrichment)
        
        # Build data context
        data_context = f"""Complete dataset ({row_count} rows):
{json.dumps(formatted_results, indent=2)}
{code_reference}
Note: Analyze this data to specifically answer the user's question. Consider patterns, comparisons, and insights relevant to what they asked."""
        
        # Build complete prompt using centralized template
        system_prompt = build_ai_summary_prompt(
            question=question,
            data_context=data_context,
            analysis_instructions=analysis_instructions,
            filters=filters,
            has_code_enrichment=bool(code_enrichment)
        )
        
        # Check prompt size against configurable limit
        prompt_size = len(system_prompt)
        max_prompt_size = settings.llm_summary_max_prompt_size
        
        logger.info(f"Summary Generation - Prompt size: {prompt_size} chars, Limit: {max_prompt_size} chars, Row count: {row_count}")
        
        if prompt_size > max_prompt_size:
            logger.info(f"Prompt too large ({prompt_size} > {max_prompt_size}), using fallback")
            return generate_simple_summary(question, row_count, results, filters)
        
        # Prompt fits - send to LLM for AI summary
        # Use configured max tokens, or slightly less for small result sets
        base_max_tokens = settings.llm_summary_max_tokens
        max_tokens = base_max_tokens if row_count > 20 else min(150, base_max_tokens)
        
        try:
            summary_response = await call_api(
                "/chat/generate-text",
                method="POST",
                data={"prompt": system_prompt, "max_tokens": max_tokens}
            )
            
            if summary_response and "text" in summary_response:
                return summary_response["text"].strip()
            else:
                return generate_simple_summary(question, row_count, results, filters)
        except Exception as api_error:
            logger.error(f"LLM API call failed: {api_error}")
            return generate_simple_summary(question, row_count, results, filters)
            
    except Exception as e:
        logger.error(f"Error generating AI summary: {e}")
        return generate_simple_summary(question, row_count, results, filters)


def generate_simple_summary(
    question: str,
    row_count: int,
    results: List[Dict],
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
    filter_text = f" (filtered by {filters})" if filters else ""
    
    if row_count == 1:
        if results and len(results[0]) == 1:
            value = list(results[0].values())[0]
            return SIMPLE_SUMMARY_TEMPLATES["single_result"].format(
                value=value, filter_text=filter_text
            )
        return SIMPLE_SUMMARY_TEMPLATES["few_results"].format(
            count=1, filter_text=filter_text
        )
    elif row_count <= 10:
        return SIMPLE_SUMMARY_TEMPLATES["few_results"].format(
            count=row_count, filter_text=filter_text
        )
    elif row_count <= 100:
        return SIMPLE_SUMMARY_TEMPLATES["medium_results"].format(
            count=row_count, filter_text=filter_text
        )
    else:
        return SIMPLE_SUMMARY_TEMPLATES["large_results"].format(
            count=row_count, filter_text=filter_text
        )


def _format_results_for_llm(data: List[Dict]) -> List[Dict]:
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


def _build_code_reference(code_enrichment: Dict[str, Dict[str, str]]) -> str:
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
