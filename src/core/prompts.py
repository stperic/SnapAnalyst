"""
Centralized Prompts and Constants

All system prompts, business context, and LLM-related constants
are defined here for easy reference and maintenance.

This file contains:
- Vanna SQL generation system prompt (loaded from training folder or generic default)
- KB insight system prompt (loaded from training folder or generic default)
- AI Summary system prompt (loaded from training folder or generic default)
- Business context documentation
- UI message templates

ARCHITECTURE:
- Dataset-specific prompts live in the training folder as .txt files:
    sql_system_prompt.txt      — SQL generation system prompt
    kb_system_prompt.txt       — KB insight system prompt
    summary_system_prompt.txt  — AI summary system prompt
- If these files exist, they are used. Otherwise, generic defaults apply.
- DDL is extracted directly from PostgreSQL (database is source of truth)

Usage:
    from src.core.prompts import (
        AI_SUMMARY_SYSTEM_PROMPT,
        VANNA_SQL_SYSTEM_PROMPT,
    )
"""


def _load_prompt_file(filename: str) -> str | None:
    """Load a prompt from the system prompts folder, or return None if not found."""
    from pathlib import Path

    from src.core.config import settings

    prompt_path = Path(settings.resolved_prompts_path) / filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return None


# =============================================================================
# AI SUMMARY PROMPTS
# =============================================================================

# Generic default — used when no summary_system_prompt.txt exists in prompts folder
_DEFAULT_AI_SUMMARY_SYSTEM_PROMPT = """You are a data analyst. The user asked a question about the data. Your job is to analyze the query results and provide insights that directly answer their question.

INSTRUCTIONS:
1. Answer the user's specific question based on the data provided
2. Provide 2-3 sentences with relevant insights and specific values
3. Use actual values from the data (numbers are already rounded to 2 decimals)
4. When citing dollar amounts or rates, use the exact values shown (e.g., '$1,012.71' not '1012.714285...')
5. If the question asks about extremes (highest/lowest), identify them accurately
6. If the question asks about patterns or comparisons, discuss those
7. Present findings from the data without speculating on causes unless the data directly supports it
8. Be natural and conversational
9. Don't mention SQL, technical details, or how you got the data"""

AI_SUMMARY_SYSTEM_PROMPT = _load_prompt_file("summary_system_prompt.txt") or _DEFAULT_AI_SUMMARY_SYSTEM_PROMPT


# =============================================================================
# VANNA SQL GENERATION PROMPT (for generate_sql)
# =============================================================================

# Generic default — used when no sql_system_prompt.txt exists in training folder
_DEFAULT_SQL_SYSTEM_PROMPT = """You are an expert data analyst and PostgreSQL specialist. Generate accurate, executable SQL queries based on natural language questions.

### SQL Guidelines
- **Dialect**: PostgreSQL
- **Text search**: Use `ILIKE` for case-insensitive matching
- **Limits**: Apply `LIMIT 100` for non-aggregate queries
- **Aliases**: Use clear column names in results (e.g., `total_amount` not `sum`)
- **NULL handling**: Use `COALESCE(column, 0)` for financial calculations

Return **only** the SQL query without markdown formatting."""

VANNA_SQL_SYSTEM_PROMPT = _load_prompt_file("sql_system_prompt.txt") or _DEFAULT_SQL_SYSTEM_PROMPT


# =============================================================================
# KB INSIGHT PROMPTS (for Knowledge/Insights chat modes)
# =============================================================================

# Generic default — used when no kb_system_prompt.txt exists in training folder
_DEFAULT_KB_SYSTEM_PROMPT = """You are a data analyst. Answer briefly and directly.
When citing numbers from the data, use the EXACT formatted values shown (e.g., '$1,012.71' not '1012.714285...')."""

KB_INSIGHT_SYSTEM_PROMPT = _load_prompt_file("kb_system_prompt.txt") or _DEFAULT_KB_SYSTEM_PROMPT

KB_INSIGHT_INSTRUCTION = """Answer in 2-3 sentences. Be direct and factual. Use exact values from the data - do not recalculate or show raw decimals."""


def build_kb_insight_prompt(
    question: str, data_context: str = None, chromadb_context: str = None, user_id: str = None
) -> tuple[str, str]:
    """
    Build the complete KB insight prompt as (system, user) message pair.

    Args:
        question: User's insight question
        data_context: Previous query data (JSON formatted)
        chromadb_context: Relevant documentation from ChromaDB
        user_id: User identifier for custom prompt lookup

    Returns:
        Tuple of (system_message, user_message)
    """
    # Get user's custom prompt or default
    if user_id:
        try:
            from src.core.logging import get_logger
            from src.database.prompt_manager import get_user_prompt

            logger = get_logger(__name__)
            system_prompt = get_user_prompt(user_id, "kb")
            logger.info(f"Using KB prompt for user {user_id}: {system_prompt[:100]}...")
        except Exception as e:
            from src.core.logging import get_logger

            logger = get_logger(__name__)
            logger.warning(f"Failed to get custom KB prompt for {user_id}: {e}, using default")
            system_prompt = KB_INSIGHT_SYSTEM_PROMPT
    else:
        system_prompt = KB_INSIGHT_SYSTEM_PROMPT

    # System message: persona + instructions
    system_message = f"{system_prompt}\n\n{KB_INSIGHT_INSTRUCTION}"

    # User message: sources + data + question
    user_parts = []

    if chromadb_context:
        user_parts.append(chromadb_context)

    if data_context:
        user_parts.append(f"DATA TO ANALYZE:\n{data_context}")

    user_parts.append(f"Question: {question}")

    user_message = "\n\n".join(user_parts)

    return system_message, user_message


# =============================================================================
# AI SUMMARY HELPER
# =============================================================================


# Helper function to build the complete prompt
def build_ai_summary_prompt(
    question: str,
    data_context: str,
    filters: str = None,
    has_code_enrichment: bool = False,
    sql: str = None,
    system_prompt_override: str = None,
) -> tuple[str, str]:
    """
    Build the complete AI summary prompt as (system, user) message pair.

    Args:
        question: User's question
        data_context: Formatted data for analysis
        filters: Active filter description
        has_code_enrichment: Whether code lookups are included
        sql: SQL query that produced the results
        system_prompt_override: Custom system prompt (from per-user prompt)

    Returns:
        Tuple of (system_message, user_message)
    """
    # System message: analyst persona + instructions
    system_parts = [system_prompt_override or AI_SUMMARY_SYSTEM_PROMPT]

    if has_code_enrichment:
        system_parts.append(
            "CRITICAL: Always use code descriptions (from CODE REFERENCE), never use numeric codes in your response!"
        )

    system_message = "\n\n".join(system_parts)

    # User message: question + filters + SQL + data
    user_parts = [f'USER\'S QUESTION: "{question}"']

    if filters:
        user_parts.append(f"ACTIVE FILTERS: {filters}")

    if sql:
        user_parts.append(f"SQL QUERY:\n{sql}")

    user_parts.append(f"DATA TO ANALYZE:\n{data_context}")
    user_parts.append("Provide your analysis:")

    user_message = "\n\n".join(user_parts)

    return system_message, user_message


# =============================================================================
# DDL STATEMENTS - NOW EXTRACTED FROM DATABASE
# =============================================================================
#
# ARCHITECTURE: Gold Standard (Database is Source of Truth)
# ---------------------------------------------------------
# DDL statements are now extracted directly from PostgreSQL using:
#   from src.database.ddl_extractor import get_all_ddl_statements
#
# This eliminates the need to maintain duplicate DDL here.
# DDL is extracted from whatever tables exist in the active database.
#
# See src/database/ddl_extractor.py for implementation details.


# =============================================================================
# BUSINESS CONTEXT DOCUMENTATION
# =============================================================================


# =============================================================================
# CODE LOOKUP REFERENCE
# =============================================================================
#
# All code lookups now come from data_mapping.json (single source of truth).
# Use src/services/code_enrichment.py to load and apply code descriptions.
#
# Reference tables in database (ref_*) also contain these mappings.


# =============================================================================
# SIMPLE SUMMARY TEMPLATES
# =============================================================================

SIMPLE_SUMMARY_TEMPLATES = {
    "single_result": "The answer is **{value}**{filter_text}.",
    "few_results": "Found **{count}** records{filter_text}. See the data table below.",
    "medium_results": "Query returned **{count}** records{filter_text}. Review the data table below for details.",
    "large_results": "Query returned **{count}** records{filter_text}. Data table shows the results below.",
    "no_results": "No matching records found{filter_text}. Try adjusting your filters or rephrasing your question.",
}


# =============================================================================
# CODE REFERENCE PROMPT SECTION
# =============================================================================

CODE_REFERENCE_HEADER = """
CODE REFERENCE (CRITICAL - Use descriptions, NOT numeric codes):
"""

CODE_REFERENCE_FOOTER = """
⚠️ IMPORTANT: When discussing results, use the descriptions above (e.g., 'Shelter deduction'), NOT the numeric codes (e.g., '363')!
"""


# =============================================================================
# UI MESSAGE TEMPLATES
# =============================================================================

# --- System Status ---
MSG_SYSTEM_STATUS = """### System Status

{api_status} **API Service** (v{api_version})
{db_status} **PostgreSQL Database**
{llm_status} **LLM Inference Service** ({llm_provider})

---

{ready_message}"""

def _get_app_display_name() -> str:
    """Get application display name from active dataset."""
    try:
        from datasets import get_active_dataset

        ds = get_active_dataset()
        if ds and ds.display_name:
            return ds.display_name
    except Exception:
        pass
    return "SnapAnalyst"


MSG_SYSTEM_READY = f"🟢 **{_get_app_display_name()} is ready**"
MSG_SYSTEM_DEGRADED = "🟡 **Some services unavailable** - Check logs for details"

# --- Welcome ---
MSG_WELCOME = "**Ask me anything about your data! See Readme for more information** 🚀"

# --- CSV Export ---
MSG_CSV_READY = """Great! I've prepared your CSV export for you.

**Export Details:**
- **Rows:** {row_count:,}
- **Columns:** {column_count}
- **File Size:** {file_size_kb:.1f} KB
- **Filename:** `{filename}`

Your file is ready to download below. You can open it in Excel, Google Sheets, or any spreadsheet application."""

MSG_CSV_NO_RESULTS = """I don't have any query results to export right now. Please run a query first, then I can create a CSV export for you."""

MSG_CSV_ERROR = """I encountered an error while creating your CSV file: {error}

Please try again, or let me know if you need help troubleshooting this."""

MSG_EXPORT_STATS = """**Export Details:**
- **Rows:** {row_count:,}
- **Columns:** {column_count}
- **File Size:** {file_size_kb:.1f} KB"""

# --- Filter ---
MSG_FILTER_APPLIED = (
    "**Filter Applied:** State: **{state}** | Year: **FY{year}**\n\nAll queries and exports will now use this filter."
)
MSG_FILTER_CLEARED = "**Filter Cleared:** Showing all data"


# --- Data Loading ---
MSG_DATA_LOADING_INITIATED = """<div class="success-box">
✅ **Data loading initiated!**

**Job ID:** {job_id}
**Status:** {status}
**File:** {filename}
**Fiscal Year:** {fiscal_year}

The data is being loaded in the background. You can continue chatting while it processes.

Use the **Settings** button → **Database** to check progress.
</div>"""


# --- Database Reset ---
MSG_DATABASE_RESET_COMPLETE = """<div class="success-box">
✅ **Database Reset Complete**

{message}

{tables_section}

You can now load fresh data using **Settings > Database**.
</div>"""

# --- Query Results ---
MSG_QUERY_RESULT = """{ai_summary}
{result_summary}

---

<details open>
<summary><strong>Results</strong></summary>

{results_html}
</details>

<details>
<summary><strong>SQL Query</strong></summary>

```sql
{sql}
```
</details>

{filter_indicator}"""

MSG_DIRECT_SQL_RESULT = """### ✅ Query Results

{results_html}

**SQL Executed:**
```sql
{sql}
```"""
