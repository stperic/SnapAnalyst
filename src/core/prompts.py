"""
Centralized Prompts and Constants

All system prompts, business context, and LLM-related constants
are defined here for easy reference and maintenance.

This file contains:
- AI Summary system prompts
- Business context documentation
- Code lookup references
- Common query patterns
- UI message templates

ARCHITECTURE NOTE (Gold Standard):
- DDL is now extracted directly from PostgreSQL, NOT maintained here
- Use src/database/ddl_extractor.get_all_ddl_statements() for Vanna training
- The database is the single source of truth for schema

Usage:
    from src.core.prompts import (
        AI_SUMMARY_SYSTEM_PROMPT,
        BUSINESS_CONTEXT_DOCUMENTATION,
    )
    
    # For DDL, use the extractor:
    from src.database.ddl_extractor import get_all_ddl_statements
"""

# =============================================================================
# AI SUMMARY PROMPTS
# =============================================================================

AI_SUMMARY_SYSTEM_PROMPT = """You are a data analyst. The user asked a question about their data. Your job is to analyze the data and provide insights that directly answer their question.

USER'S QUESTION: "{question}"

{analysis_section}

{filter_section}

DATA TO ANALYZE:
{data_context}

INSTRUCTIONS:
1. Answer the user's specific question based on the data provided
2. {priority_instruction}
3. Use actual values from the data (numbers are already rounded to 2 decimals)
4. If the question asks about extremes (highest/lowest), identify them accurately
5. If the question asks about patterns or comparisons, discuss those
6. Be natural and conversational
7. Don't mention SQL, technical details, or how you got the data
8. {code_instruction}

Provide your analysis:"""


# Helper function to build the complete prompt
def build_ai_summary_prompt(
    question: str,
    data_context: str,
    analysis_instructions: str = None,
    filters: str = None,
    has_code_enrichment: bool = False
) -> str:
    """
    Build the complete AI summary prompt from template.
    
    Args:
        question: User's question
        data_context: Formatted data for analysis
        analysis_instructions: Optional special instructions
        filters: Active filter description
        has_code_enrichment: Whether code lookups are included
        
    Returns:
        Complete prompt string
    """
    analysis_section = ""
    if analysis_instructions:
        analysis_section = f"""🎯 SPECIAL ANALYSIS INSTRUCTIONS: {analysis_instructions}
^^^ CRITICAL: Follow these specific instructions in your analysis! ^^^"""
    
    filter_section = f"ACTIVE FILTERS: {filters}" if filters else ""
    
    priority_instruction = (
        f"MOST IMPORTANT: {analysis_instructions}" 
        if analysis_instructions 
        else "Provide 2-3 sentences with relevant insights and specific values"
    )
    
    code_instruction = (
        "CRITICAL: Always use code descriptions (from CODE REFERENCE), never use numeric codes in your response!"
        if has_code_enrichment
        else ""
    )
    
    return AI_SUMMARY_SYSTEM_PROMPT.format(
        question=question,
        analysis_section=analysis_section,
        filter_section=filter_section,
        data_context=data_context,
        priority_instruction=priority_instruction,
        code_instruction=code_instruction
    )


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
# The actual database schema includes:
# - Reference/lookup tables (ref_*) with FK constraints
# - Main tables (households, household_members, qc_errors)
# - Foreign key relationships for automatic JOINs
#
# See src/database/ddl_extractor.py for implementation details.


# =============================================================================
# BUSINESS CONTEXT DOCUMENTATION
# =============================================================================

BUSINESS_CONTEXT_DOCUMENTATION = """
SNAP QC Database - Business Context and Query Patterns

PROGRAM TERMS:
- SNAP = Supplemental Nutrition Assistance Program (formerly "food stamps")
- QC = Quality Control review process to ensure benefit accuracy
- Overissuance = Household received more benefits than entitled
- Underissuance = Household received less benefits than entitled
- RSDI = Retirement, Survivors, and Disability Insurance (Social Security)
- SSI = Supplemental Security Income
- TANF = Temporary Assistance for Needy Families (welfare/cash assistance)
- ABAWD = Able-Bodied Adults Without Dependents (work requirement rules)

DATABASE ARCHITECTURE - REFERENCE TABLES:
The database uses lookup/reference tables (ref_*) for all code values.
For human-readable results, JOIN to these tables instead of using raw codes.

KEY REFERENCE TABLES:
- ref_status: status codes → 'Amount correct', 'Overissuance', 'Underissuance'
- ref_element: element_code → error types like 'Wages and salaries', 'Shelter deduction'
- ref_nature: nature_code → what went wrong, e.g., 'Unreported source of income'
- ref_agency_responsibility: responsible_agency → who caused error (has responsibility_type column: 'client' or 'agency')
- ref_error_finding: error_finding → 'Overissuance', 'Underissuance', 'Ineligible'
- ref_sex: sex → 'Male', 'Female', 'Prefer not to answer'
- ref_snap_affiliation: snap_affiliation_code → member eligibility status

COMMON QUERY PATTERNS (using reference table JOINs):

1. Error analysis by type:
   SELECT re.description, COUNT(*) 
   FROM qc_errors e 
   JOIN ref_element re ON e.element_code = re.code 
   GROUP BY re.description

2. Client vs Agency errors:
   SELECT ra.responsibility_type, COUNT(*) 
   FROM qc_errors e 
   JOIN ref_agency_responsibility ra ON e.responsible_agency = ra.code 
   GROUP BY ra.responsibility_type

3. Income-related errors:
   SELECT re.description, SUM(e.error_amount) 
   FROM qc_errors e 
   JOIN ref_element re ON e.element_code = re.code 
   WHERE re.category = 'earned_income' OR re.category = 'unearned_income'
   GROUP BY re.description

4. Error patterns by state:
   SELECT h.state_name, re.description, COUNT(*)
   FROM qc_errors e
   JOIN households h ON e.case_id = h.case_id AND e.fiscal_year = h.fiscal_year
   JOIN ref_element re ON e.element_code = re.code
   GROUP BY h.state_name, re.description

5. Overissuance cases:
   SELECT h.*, rs.description as status_desc
   FROM households h
   JOIN ref_status rs ON h.status = rs.code
   WHERE rs.description = 'Overissuance'

TABLE RELATIONSHIPS:
- households: Core table with state_name, income totals, benefits
- household_members: Person-level data (JOIN to households via case_id + fiscal_year)
- qc_errors: Error details (JOIN to households via case_id + fiscal_year)
- ref_* tables: Lookup tables (JOIN via code columns)

IMPORTANT:
- state_name is ONLY in households table - always JOIN when querying members or errors by state
- Use ref_element.category to filter error types: 'eligibility', 'assets', 'earned_income', 'unearned_income', 'deductions', 'computation'
- Use ref_agency_responsibility.responsibility_type to distinguish 'client' vs 'agency' errors
- case_id is a STRING (not numeric) - use proper string comparison when needed
- Column display formats are documented in DDL (extracted from data_mapping.json)
"""


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
    "few_results": "Found {count} results{filter_text}. See the data table below for details.",
    "medium_results": "Query returned {count} results{filter_text}. Showing key findings in the data table below.",
    "large_results": "Query returned a large dataset with {count} rows{filter_text}. Showing the first 50 results.",
    "no_results": "No results found for your query.",
}


# =============================================================================
# CODE REFERENCE PROMPT SECTION
# =============================================================================

CODE_REFERENCE_HEADER = """
📖 CODE REFERENCE (CRITICAL - Use descriptions, NOT numeric codes):
"""

CODE_REFERENCE_FOOTER = """
⚠️ IMPORTANT: When discussing results, use the descriptions above (e.g., 'Shelter deduction'), NOT the numeric codes (e.g., '363')!
"""


# =============================================================================
# UI MESSAGE TEMPLATES
# =============================================================================

# --- System Status ---
MSG_SYSTEM_STATUS = """### 🚀 System Status

{api_status} **API Service** (v{api_version})
{db_status} **PostgreSQL Database** )
{llm_status} **LLM Inference Service** ({llm_provider})

---

{ready_message}"""

MSG_SYSTEM_READY = "🟢 **SnapAnalysis is ready**"
MSG_SYSTEM_DEGRADED = "🟡 **Some services unavailable** - Check logs for details"

# --- Welcome ---
MSG_WELCOME = "**Ask me anything about your SNAP QC data! See Readme for more information** 🚀"

# --- CSV Export ---
MSG_CSV_READY = """Great! I've prepared your CSV export for you.

📊 **Export Details:**
- **Rows:** {row_count:,}
- **Columns:** {column_count}
- **File Size:** {file_size_kb:.1f} KB
- **Filename:** `{filename}`

Your file is ready to download below. You can open it in Excel, Google Sheets, or any spreadsheet application."""

MSG_CSV_NO_RESULTS = """I don't have any query results to export right now. Please run a query first, then I can create a CSV export for you."""

MSG_CSV_ERROR = """I encountered an error while creating your CSV file: {error}

Please try again, or let me know if you need help troubleshooting this."""

MSG_EXPORT_STATS = """📊 **Export Details:**
- **Rows:** {row_count:,}
- **Columns:** {column_count}
- **File Size:** {file_size_kb:.1f} KB"""

# --- Filter ---
MSG_FILTER_APPLIED = "🔍 **Filter Applied:** State: **{state}** | Year: **FY{year}**\n\nAll queries and exports will now use this filter."
MSG_FILTER_CLEARED = "🔍 **Filter Cleared:** Showing all data"

MSG_FILTER_STATUS = """### 🔍 Current Data Filter

**Status:** {status}

**Applied Filters:**
- **State:** {state}
- **Fiscal Year:** {fiscal_year}

**Description:** {description}

**To change filters:** Use the filter dropdowns in the settings panel (bottom left)."""

# --- Training Toggle ---
MSG_TRAINING_ENABLED = """🧠 **AI Training Enabled**

The system will now:
- Store embeddings in ChromaDB for faster queries
- Learn from query patterns
- Persist training data across restarts

Note: First queries may be slower while building embeddings."""

MSG_TRAINING_DISABLED_CLEANED = """🧠 **AI Training Disabled**

✅ Vector database cleaned successfully.

The system will now:
- Generate SQL from schema on each query (no persistence)
- Faster startup times
- No disk storage for embeddings"""

MSG_TRAINING_DISABLED_EMPTY = """🧠 **AI Training Disabled**

✅ No vector database to clean (already empty)."""

MSG_TRAINING_DISABLED_ERROR = """🧠 **AI Training Disabled**

⚠️ Error cleaning vector database: {error}

You may need to manually delete the `chromadb/` folder."""

# --- Data Loading ---
MSG_DATA_LOADING_INITIATED = """<div class="success-box">
✅ **Data loading initiated!**

**Job ID:** {job_id}  
**Status:** {status}  
**File:** {filename}  
**Fiscal Year:** {fiscal_year}

The data is being loaded in the background. You can continue chatting while it processes.

Use `/status` to check progress.
</div>"""

MSG_LOADING_IN_PROGRESS = """#### 🔄 Loading in Progress

**Job ID:** `{job_id}`  
**Status:** Processing...  
**Progress:** {percent:.1f}% ({rows_processed:,} / {total_rows:,} rows)  

"""

# --- Database Reset ---
MSG_DATABASE_RESET_COMPLETE = """<div class="success-box">
✅ **Database Reset Complete**

{message}

**Tables Reset:**
- Households
- Household Members  
- QC Errors

You can now load fresh data using `/load` or by uploading a CSV file.
</div>"""

# --- File Upload ---
MSG_FILE_UPLOAD_SUCCESS = """<div class="success-box">
✅ **File Uploaded Successfully!**

**Filename:** `{filename}`  
**Size:** {size_mb:.2f} MB  
**Fiscal Year:** {fiscal_year}

The file has been saved to the snapdata directory.

**Next steps:**
- Use `/load {filename}` to load this data
- Or select the file from the available files list
</div>"""

# --- Database Stats ---
MSG_DATABASE_STATS_HEADER = """### 📊 Database Statistics

**Connection Status:** {connection_status}  
**Database:** {db_name}

#### 📈 Record Counts
"""

# --- LLM Provider Info ---
MSG_LLM_PROVIDER_INFO = """### 🤖 LLM Provider Information

**Provider:** {provider}  
**Status:** {status}  
**Training:** {training_status}

#### SQL Generation
| Setting | Value |
|---------|-------|
| Model | {sql_model} |
| Max Tokens | {sql_max_tokens} |
| Temperature | {sql_temperature} |

#### Summary Generation
| Setting | Value |
|---------|-------|
| Model | {summary_model} |
| Max Tokens | {summary_max_tokens} |
| Max Prompt Size | {summary_max_prompt_size:,} chars |
{status_note}"""

MSG_LLM_TRAINING_NOTE = "\n\n💡 **Note:** Training is disabled to prevent slow startup. The LLM service initializes automatically on first use (lazy initialization)."

# --- Excel Export ---
MSG_EXCEL_EXPORT_READY = """### ✅ Your Excel export is ready!

**What's included:**
- 📖 **README sheet** - Complete documentation (opens first)
- 📊 **Households** - Household case data
- 👥 **Members** - Household member data
- ⚠️ **QC_Errors** - Quality control errors

**File details:**
- Format: Excel (.xlsx)
- Size: ~2-5 MB
- Data: {data_scope}

**Download your file:**
[📥 Click here to download]({download_url})

💡 **Tip:** The README sheet opens first with complete documentation."""

# --- Query Results ---
MSG_QUERY_RESULT = """{ai_summary}

---

### Data

{results_html}

{sql_section}

{filter_indicator}"""

MSG_QUERY_SQL_SECTION = """SQL Query

```sql
{sql}
```"""

MSG_DIRECT_SQL_RESULT = """### ✅ Query Results

{results_html}

**SQL Executed:**
```sql
{sql}
```"""

# --- Sample Questions ---
MSG_SAMPLES_HEADER = """### 📚 Sample Questions

{content}

---
**💡 Tip**: Use `/edit-samples` to add your own questions!"""

MSG_SAMPLES_NOT_FOUND = "⚠️ Sample questions file not found. Use `/edit-samples` to create it."

MSG_EDIT_SAMPLES_PROMPT = """### ✏️ Edit Sample Questions

**Current content** ({char_count} characters):

```markdown
{preview}...
```

Please provide the **complete new content** for the sample questions file:
"""

MSG_SAMPLES_UPDATED = """✅ **Sample questions updated successfully!**

- File: `sample_questions.md`
- Size: {char_count} characters
- Location: {path}

Use `/samples` to view the updated questions."""

MSG_EDIT_CANCELLED = "❌ Edit cancelled - no changes made."

# --- Help Text ---
MSG_HELP = """### 📚 Available Commands

**Quick Stats:**
- `/status` - Check health of all services (API, Database, LLM)
- `/provider` - LLM configuration details
- `/database` - Database statistics 

**Data Management:**
- `/files` - List available data files
- `/reset` - Clear all data (with confirmation)

**Data Export:**
- `/export` - Download all data to Excel with README

**Data Filtering:**
- `/filter status` - Check current filter settings

**Schema & Documentation:**
- `/schema` - View database schema summary
- `/samples` - View sample questions

**Feedback:**
- `/notes <feedback>` - Add notes about the last response
- Use 👍 / 👎 buttons on responses to rate quality

**Other:**
- `/help` - Show this message

---
**💡 Tip**: Just type your question naturally! The AI will convert it to SQL."""
