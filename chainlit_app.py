"""
Chainlit Web UI for SnapAnalyst AI Chatbot
Provides an interactive chat interface for querying SNAP QC data with history
"""
import chainlit as cl
import httpx
import json
from typing import Dict, List, Optional
from datetime import datetime
import os
from pathlib import Path

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"


async def generate_ai_summary(question: str, sql: str, results: List[Dict], row_count: int, filters: str = "") -> str:
    """
    Generate AI summary of query results using hybrid approach.
    
    Args:
        question: User's original question
        sql: SQL query executed
        results: Query results
        row_count: Number of rows returned
        filters: Active filters description
    
    Returns:
        AI-generated summary text
    """
    try:
        # Determine approach based on result size
        if row_count == 0:
            return "No results found for your query."
        
        # Special case: single row with single column (like COUNT queries)
        if row_count == 1 and results and len(results[0]) == 1:
            column_name = list(results[0].keys())[0]
            value = list(results[0].values())[0]
            filter_text = f" (filtered by {filters})" if filters else ""
            return f"**{value:,}** {column_name.replace('_', ' ')}{filter_text}."
        
        # Prepare data context based on row count
        if row_count <= 10:
            # Full context - send all results
            data_context = f"All {row_count} results:\n{json.dumps(results, indent=2)}"
            approach = "detailed"
        elif row_count <= 100:
            # Statistical summary + sample
            sample = results[:5]
            
            # Calculate basic statistics for numeric columns
            stats = {}
            if results:
                for key in results[0].keys():
                    values = [r.get(key) for r in results if r.get(key) is not None]
                    if values and isinstance(values[0], (int, float)):
                        try:
                            stats[key] = {
                                "min": min(values),
                                "max": max(values),
                                "avg": sum(values) / len(values) if values else 0
                            }
                        except:
                            pass
            
            data_context = f"Results: {row_count} rows\nSample (first 5):\n{json.dumps(sample, indent=2)}"
            if stats:
                data_context += f"\n\nStatistics:\n{json.dumps(stats, indent=2)}"
            approach = "statistical"
        else:
            # Simple summary - just counts and sample
            sample = results[:3]
            data_context = f"Results: {row_count} rows (large dataset)\nSample (first 3):\n{json.dumps(sample, indent=2)}"
            approach = "simple"
        
        # Build system prompt
        system_prompt = f"""You are a helpful data analyst. Summarize these database query results in 2-3 clear, conversational sentences.

GUIDELINES:
- Start with the main finding and key numbers
- Be specific - mention actual values, not just "results were found"
- If there are interesting patterns, mention them briefly
- Keep it natural and easy to understand
- Don't mention the SQL or technical details
- If filters are active, incorporate that context naturally

USER QUESTION: {question}

ACTIVE FILTERS: {filters if filters else "None"}

DATA SUMMARY:
{data_context}

SQL EXECUTED: {sql}

Provide a brief, insightful summary for a non-technical user:"""

        # Truncate prompt if too long (API max is 2000 chars)
        if len(system_prompt) > 1900:
            # Reduce data_context
            data_context_short = data_context[:500] + "... (truncated)"
            system_prompt = f"""You are a helpful data analyst. Summarize these database query results in 2-3 clear, conversational sentences.

USER QUESTION: {question}
ACTIVE FILTERS: {filters if filters else "None"}
DATA SUMMARY: {data_context_short}
SQL EXECUTED: {sql}

Provide a brief, insightful summary:"""

        # Call LLM service
        try:
            summary_response = await call_api(
                "/chat/generate-text",
                method="POST",
                data={"prompt": system_prompt, "max_tokens": 150}
            )
            
            if summary_response and "text" in summary_response:
                return summary_response["text"].strip()
            else:
                # Fallback: generate simple summary
                return generate_simple_summary(question, row_count, results, filters)
        except Exception as api_error:
            print(f"LLM API call failed: {api_error}")
            return generate_simple_summary(question, row_count, results, filters)
            
    except Exception as e:
        # Fallback on error
        return generate_simple_summary(question, row_count, results, filters)


def generate_simple_summary(question: str, row_count: int, results: List[Dict], filters: str = "") -> str:
    """Generate a simple fallback summary without LLM"""
    filter_text = f" (filtered by {filters})" if filters else ""
    
    if row_count == 1:
        # Single result - try to extract the value
        if results and len(results[0]) == 1:
            value = list(results[0].values())[0]
            return f"The answer is **{value}**{filter_text}."
        return f"Found 1 result{filter_text}."
    elif row_count <= 10:
        return f"Found {row_count} results{filter_text}. See the data table below for details."
    elif row_count <= 100:
        return f"Query returned {row_count} results{filter_text}. Showing key findings in the data table below."
    else:
        return f"Query returned a large dataset with {row_count} rows{filter_text}. Showing the first 50 results."


async def call_api(endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict:
    """Make API call to SnapAnalyst backend"""
    url = f"{API_BASE_URL}{API_PREFIX}{endpoint}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "GET":
            response = await client.get(url)
        elif method == "POST":
            response = await client.post(url, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()


def get_filter_indicator() -> str:
    """Get the active filter indicator HTML if a filter is active"""
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


def format_sql_results(results: List[Dict], row_count: int) -> str:
    """
    Format SQL results as modern HTML table.
    CSV is created on-demand when user clicks the download button.
    
    Returns:
        HTML table string
    """
    if not results or len(results) == 0:
        return "<p>No results returned.</p>"
    
    # Results is a list of dictionaries
    headers = list(results[0].keys())
    
    # Modern table with compact styling
    
    html = '''
<div style="overflow-x: auto; margin: 10px 0;">
    <table class="sortable-table" style="width: 100%; border-collapse: collapse; font-size: 11px; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <thead>
            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'''
    
    # Headers - simpler without onclick since Chainlit might sanitize it
    for idx, header in enumerate(headers):
        html += f'<th data-column="{idx}" style="padding: 2px 6px; text-align: left; font-weight: 600; color: #475569; white-space: nowrap; cursor: pointer; user-select: none;" class="sortable-header">{header} <span style="color: #94a3b8; font-size: 9px;">⇅</span></th>'
    html += "</tr></thead><tbody>"
    
    # Ultra-compact rows
    for idx, row_dict in enumerate(results[:50]):
        bg = "#ffffff" if idx % 2 == 0 else "#f8fafc"
        html += f'<tr style="background: {bg}; border-bottom: 1px solid #e2e8f0;">'
        for header in headers:
            cell = row_dict.get(header)
            cell_value = cell if cell is not None else '<span style="color: #94a3b8; font-style: italic;">NULL</span>'
            html += f'<td style="padding: 2px 6px; color: #1e293b; line-height: 1.2;">{cell_value}</td>'
        html += "</tr>"
    html += "</tbody></table></div>"
    
    if row_count > 50:
        html += f'<div style="margin: 10px 0; padding: 8px 12px; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px; font-size: 13px;">📊 Showing first <strong>50</strong> of <strong>{row_count:,}</strong> rows in table. CSV download includes all {row_count:,} rows.</div>'
    
    return html


@cl.on_chat_start
async def start():
    """Initialize chat session"""
    # Initialize session
    cl.user_session.set("chat_history", [])
    cl.user_session.set("query_count", 0)
    
    # Create filter settings UI
    try:
        # Get available filter options from API
        filter_options = await call_api("/filter/options")
        states = ["All States"] + filter_options.get("states", [])
        years = ["All Years"] + [str(y) for y in filter_options.get("fiscal_years", [])]
        
        # Create filter selection UI
        settings = await cl.ChatSettings(
            [
                cl.input_widget.Select(
                    id="state_filter",
                    label="🗺️ State Filter",
                    values=states,
                    initial_value="All States",
                    description="Filter all queries and exports by state",
                ),
                cl.input_widget.Select(
                    id="year_filter",
                    label="📅 Fiscal Year Filter",
                    values=years,
                    initial_value="All Years",
                    description="Filter all queries and exports by fiscal year",
                ),
            ]
        ).send()
        
        # Store initial filter state
        cl.user_session.set("current_state_filter", "All States")
        cl.user_session.set("current_year_filter", "All Years")
        
    except Exception as e:
        print(f"Error setting up filters: {e}")
        # Continue without filters if API call fails
    
    # Welcome message
    welcome = """
# 🎯 Welcome to SnapAnalyst AI Chatbot!

I'm your AI assistant for analyzing **SNAP Quality Control data**. I can help you:

✅ **Query the database** using natural language  
✅ **Generate SQL** from your questions  
✅ **Execute queries** and show results  
✅ **Upload CSV files** from your browser  
✅ **Load data** from CSV files  
✅ **Download data** to Excel with comprehensive README  
✅ **Explain database schema** and relationships

---



### 🚀 Quick Start Examples:

💬 *"Show me the top 5 states with highest SNAP benefits"*  
💬 *"How many households are in the database?"*  
💬 *"What's the average income by state?"*  
💬 *"Find all cases with payment errors"*

- **`/help`** - Show all commands

---

**Ask me anything about your SNAP QC data!** 🚀
    """
    
    await cl.Message(content=welcome).send()
    
    # Check API health
    try:
        # Try the root health endpoint (not /api/v1/health)
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_BASE_URL}/health")
            health = response.json()
        await cl.Message(
            content=f'<div class="success-box">✅ Connected to SnapAnalyst API (v{health.get("version", "unknown")})</div>',
            author="system"
        ).send()
        
        # Skip stats check on startup - too slow and blocks the API
        # Users can run /status command to check database statistics
            
    except Exception as e:
        await cl.Message(
            content=f'<div class="warning-box">⚠️ Could not connect to API: {str(e)}\n\nMake sure the API is running: `PYTHONPATH=. python src/api/main.py`</div>',
            author="system"
        ).send()


@cl.on_settings_update
async def on_settings_update(settings: Dict):
    """Handle filter settings updates"""
    try:
        state_filter = settings.get("state_filter", "All States")
        year_filter = settings.get("year_filter", "All Years")
        
        # Get previous values
        prev_state = cl.user_session.get("current_state_filter", "All States")
        prev_year = cl.user_session.get("current_year_filter", "All Years")
        
        # Check if filters changed
        if state_filter == prev_state and year_filter == prev_year:
            return  # No change
        
        # Update session
        cl.user_session.set("current_state_filter", state_filter)
        cl.user_session.set("current_year_filter", year_filter)
        
        # Apply to backend API
        state_val = None if state_filter == "All States" else state_filter
        year_val = None if year_filter == "All Years" else int(year_filter)
        
        # Update filter via API
        await call_api(
            "/filter/set",
            method="POST",
            data={"state": state_val, "fiscal_year": year_val}
        )
        
        # Show confirmation message
        if state_val or year_val:
            message = f"🔍 **Filter Applied:** State: **{state_val or 'All'}** | Year: **FY{year_val or 'All'}**\n\nAll queries and exports will now use this filter."
        else:
            message = "🔍 **Filter Cleared:** Showing all data"
        
        await cl.Message(content=message, author="system").send()
        
    except Exception as e:
        await cl.Message(
            content=f'<div class="warning-box">❌ Error updating filter: {str(e)}</div>',
            author="system"
        ).send()


@cl.action_callback("download_csv")
async def on_download_csv(action: cl.Action):
    """Handle CSV download action - create CSV file on-demand"""
    try:
        # Get stored results from session
        results = cl.user_session.get("last_query_results")
        
        if not results or len(results) == 0:
            await cl.Message(content="⚠️ No query results available to download.").send()
            return
        
        # Create CSV file
        import csv
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"query_results_{timestamp}.csv"
        csv_file_path = f"/tmp/{csv_filename}"
        
        headers = list(results[0].keys())
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results)
        
        # Send file to user
        elements = [
            cl.File(
                name=csv_filename,
                path=csv_file_path,
                display="inline"
            )
        ]
        
        await cl.Message(
            content=f"✅ CSV ready ({len(results)} rows)",
            elements=elements
        ).send()
        
    except Exception as e:
        await cl.Message(content=f"❌ Error creating CSV: {str(e)}").send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    user_input = message.content.strip()
    
    # Update chat history
    history = cl.user_session.get("chat_history")
    history.append({
        "timestamp": datetime.now().isoformat(),
        "role": "user",
        "content": user_input
    })
    
    # Handle special commands
    if user_input.startswith("/"):
        # Parse command and arguments
        parts = user_input.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else None
        await handle_command(command, args)
        return
    
    # Normal chat query - send to LLM
    await handle_chat_query(user_input)


async def handle_command(command: str, args: Optional[str] = None):
    """Handle special slash commands"""
    
    if command == "/help":
        await cl.Message(content="""
### 📚 SnapAnalyst Commands

**Data Loading:**
- `/files` - List available CSV files
- `/load <filename>` - Load a specific CSV file (e.g., `/load qc_pub_fy2023`)
- `/upload` - Upload a CSV file from your computer

**Data Export:**
- `/export` - Download all data to Excel with README
- `/export <fiscal_year>` - Download specific year (e.g., `/export 2023`)

**Data Filtering:**
- `/filter status` - Check current filter settings

**Database Management:**
- `/database` - View database statistics
- `/reset` - Reset the database (clear all data)

**Schema & Info:**
- `/schema` - View database schema and tables
- `/provider` - Check LLM provider and model info

**Chat:**
- `/history` - Show your query history
- `/clear` - Clear chat history
- `/help` - Show this help message

Just type your question naturally to query the data! 🚀
        """).send()
    
    elif command == "/load":
        await handle_load_command(args)
    
    elif command == "/files":
        await handle_files_command()
    
    elif command == "/upload":
        await handle_upload_command()
    
    elif command == "/reset":
        await handle_reset_command()
    
    elif command == "/database":
        await handle_database_command()
    
    elif command == "/schema":
        await handle_schema_command()
    
    elif command == "/provider":
        await handle_provider_command()
    
    elif command == "/stats":
        await handle_database_command()  # Alias for /database
    
    elif command == "/history":
        await handle_history_command()
    
    elif command == "/export":
        await handle_download_command(args)
    
    elif command == "/filter":
        await handle_filter_command(args)
    
    elif command == "/clear":
        cl.user_session.set("chat_history", [])
        cl.user_session.set("query_count", 0)
        await cl.Message(content="✅ Chat history cleared!").send()
    
    else:
        await cl.Message(content=f"❌ Unknown command: `{command}`. Type `/help` for available commands.").send()


async def load_file_by_name(filename: str):
    """Load a file by its name"""
    msg = cl.Message(content=f"📥 Loading `{filename}`...")
    await msg.send()
    
    try:
        # Extract fiscal year from filename (e.g., qc_pub_fy2023.csv -> 2023)
        import re
        fy_match = re.search(r'fy(\d{4})', filename, re.IGNORECASE)
        if fy_match:
            fiscal_year = int(fy_match.group(1))
        else:
            # Try to find any 4-digit year
            year_match = re.search(r'20(\d{2})', filename)
            if year_match:
                fiscal_year = int('20' + year_match.group(1))
            else:
                fiscal_year = 2023  # Default
        
        # Trigger data loading with correct format
        result = await call_api(
            "/data/load",
            method="POST",
            data={
                "fiscal_year": fiscal_year,
                "filename": filename
            }
        )
        
        success_msg = f"""
<div class="success-box">
✅ **Data loading initiated!**

**Job ID:** {result.get('job_id', 'N/A')}  
**Status:** {result.get('status', 'Unknown')}  
**File:** {filename}  
**Fiscal Year:** {fiscal_year}

The data is being loaded in the background. You can continue chatting while it processes.

Use `/database` to check progress.
</div>
        """
        
        await cl.Message(content=success_msg).send()
        
    except Exception as e:
        error_msg = f'<div class="warning-box">❌ Error loading file: {str(e)}</div>'
        await cl.Message(content=error_msg).send()


async def handle_load_command(filename: Optional[str] = None):
    """Handle /load command - load CSV file by name (shows interactive selection if no filename provided)"""
    try:
        # Get available files
        files_response = await call_api("/data/files")
        files = files_response.get("files", [])
        
        if not files:
            await cl.Message(content='<div class="warning-box">⚠️ No CSV files found in snapdata directory</div>').send()
            return
        
        # If filename provided, load it directly
        if filename:
            # Remove .csv extension if user included it for matching
            filename_to_match = filename.replace('.csv', '')
            
            # Find matching file (case-insensitive, partial match)
            matching_file = None
            for file_info in files:
                file_name_base = file_info['filename'].replace('.csv', '')
                if filename_to_match.lower() in file_name_base.lower():
                    matching_file = file_info['filename']
                    break
            
            if matching_file:
                # Load the file directly
                await load_file_by_name(matching_file)
            else:
                await cl.Message(content=f'<div class="warning-box">❌ File not found: {filename}\n\nAvailable files: {", ".join([f["filename"] for f in files])}</div>').send()
            return
        
        # No filename provided - show file selection
        actions = []
        for file_info in files:
            actions.append(
                cl.Action(
                    name=f"load_{file_info['filename']}",
                    value=file_info['filename'],
                    label=f"📁 {file_info['filename']} ({file_info['size_mb']:.2f} MB)"
                )
            )
        
        await cl.Message(
            content=f"### 📂 Available CSV Files ({len(files)} found)\n\nClick a file to load it into the database, or use `/load filename`:",
            actions=actions
        ).send()
        
    except Exception as e:
        await cl.Message(content=f'<div class="warning-box">❌ Error listing files: {str(e)}</div>').send()


async def handle_schema_command():
    """Handle /schema command - show database schema"""
    try:
        schema = await call_api("/query/schema")
        
        content = "### 🗄️ Database Schema\n\n"
        
        # Add database info
        db_info = schema.get("database", {})
        if db_info:
            content += f"**Database:** {db_info.get('name', 'SnapAnalyst')}\n"
            content += f"*{db_info.get('description', '')}*\n\n"
            if db_info.get('fiscal_years_available'):
                content += f"**Available Years:** {', '.join(map(str, db_info['fiscal_years_available']))}\n\n"
        
        # Tables is a dict with table_name as key
        tables = schema.get("tables", {})
        
        for table_name, table_info in tables.items():
            content += f"#### 📋 Table: `{table_name}`\n"
            content += f"*{table_info.get('description', 'No description')}*\n\n"
            
            content += "| Column | Type | Nullable | Description |\n"
            content += "|--------|------|----------|-------------|\n"
            
            # Columns is also a dict with column_name as key
            columns = table_info.get("columns", {})
            for col_name, col_info in columns.items():
                col_type = col_info.get('type', 'UNKNOWN')
                nullable = "✓" if col_info.get("nullable", True) else "✗"
                description = col_info.get('description', '-')
                content += f"| `{col_name}` | {col_type} | {nullable} | {description} |\n"
            
            content += "\n"
        
        # Add relationships
        relationships = schema.get("relationships", {})
        if relationships:
            content += "### 🔗 Relationships\n\n"
            for rel_name, rel_info in relationships.items():
                rel_type = rel_info.get('type', 'UNKNOWN')
                description = rel_info.get('description', '')
                join_condition = rel_info.get('join', '')
                content += f"**{rel_name}** ({rel_type})\n"
                content += f"- {description}\n"
                content += f"- Join: `{join_condition}`\n\n"
        
        await cl.Message(content=content).send()
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Debug - Schema command error: {e}")
        print(error_trace)
        await cl.Message(content=f'<div class="warning-box">❌ Error fetching schema: {str(e)}</div>').send()


async def handle_provider_command():
    """Handle /provider command - show LLM provider info"""
    try:
        provider_info = await call_api("/chat/provider")
        
        # Determine status display
        is_initialized = provider_info.get('initialized', False)
        training_enabled = provider_info.get('training_enabled', False)
        
        # Status explanation
        if not training_enabled:
            status_note = "\n\n💡 **Note:** Training is disabled to prevent slow startup. The LLM service initializes automatically on first use (lazy initialization)."
        else:
            status_note = ""
        
        content = f"""
### 🤖 LLM Provider Information

**Provider:** {provider_info.get('provider', 'Unknown').upper()}  
**SQL Model:** {provider_info.get('sql_model', 'Unknown')}  
**Summary Model:** {provider_info.get('summary_model', 'Unknown')}  
**Temperature:** {provider_info.get('temperature', 'N/A')}  
**Max Tokens:** {provider_info.get('max_tokens', 'N/A')}  
**Status:** {provider_info.get('status', 'Unknown')}  
**Training:** {'✅ Enabled' if training_enabled else '⚠️ Disabled (Performance Mode)'}
{status_note}
        """
        
        await cl.Message(content=content).send()
        
    except Exception as e:
        await cl.Message(content=f'<div class="warning-box">❌ Error fetching provider info: {str(e)}</div>').send()


async def handle_files_command():
    """Handle /files command - list all available CSV files"""
    try:
        # Get available files
        files_response = await call_api("/data/files")
        files = files_response.get("files", [])
        
        if not files:
            await cl.Message(content='<div class="warning-box">⚠️ No CSV files found in snapdata directory</div>').send()
            return
        
        # Build file list display
        content = f"### 📂 Available CSV Files ({len(files)} found)\n\n"
        content += f"**Directory:** `{files_response.get('snapdata_path', 'snapdata')}`\n\n"
        
        content += "| File | Size | Fiscal Year | Status |\n"
        content += "|------|------|-------------|--------|\n"
        
        for file_info in files:
            filename = file_info['filename']
            size = f"{file_info['size_mb']:.2f} MB"
            fy = file_info.get('fiscal_year', 'N/A')
            status = "✅ Loaded" if file_info.get('loaded', False) else "⚪ Not loaded"
            content += f"| `{filename}` | {size} | {fy} | {status} |\n"
        
        content += f"\n**Total Size:** {sum(f['size_mb'] for f in files):.2f} MB\n"
        content += f"\n💡 *Use `/load <filename>` to load a file*"
        
        await cl.Message(content=content).send()
        
    except Exception as e:
        await cl.Message(content=f'<div class="warning-box">❌ Error listing files: {str(e)}</div>').send()


async def handle_upload_command():
    """Handle /upload command - upload CSV file from browser"""
    try:
        # Ask user to upload a file
        files = await cl.AskFileMessage(
            content="📤 **Upload CSV File**\n\nPlease select a CSV file to upload to the database.\n\n**Accepted formats:**\n- CSV files (.csv)\n- Maximum size: 100 MB\n\n**File naming:**\n- Include fiscal year in filename (e.g., `qc_pub_fy2023.csv`)\n- File will be saved to the snapdata directory",
            accept=["text/csv", ".csv"],
            max_size_mb=100,
            max_files=1,
            timeout=180,
        ).send()
        
        if not files:
            await cl.Message(content="⚠️ No file uploaded.").send()
            return
        
        uploaded_file = files[0]
        
        # Show upload progress
        msg = cl.Message(content=f"📤 Uploading `{uploaded_file.name}`...")
        await msg.send()
        
        # Upload file to API
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(uploaded_file.path, 'rb') as f:
                files_data = {'file': (uploaded_file.name, f, 'text/csv')}
                response = await client.post(
                    f"{API_BASE_URL}{API_PREFIX}/data/upload",
                    files=files_data
                )
                response.raise_for_status()
                result = response.json()
        
        file_info = result.get("file", {})
        
        # Show success message
        success_msg = f"""
<div class="success-box">
✅ **File Uploaded Successfully!**

**Filename:** `{file_info.get('filename', uploaded_file.name)}`  
**Size:** {file_info.get('size_mb', 0):.2f} MB  
**Fiscal Year:** {file_info.get('fiscal_year', 'N/A')}

The file has been saved to the snapdata directory.

**Next steps:**
- Use `/load {file_info.get('filename', uploaded_file.name)}` to load this file into the database
- Or use `/files` to see all available files
</div>
        """
        
        await cl.Message(content=success_msg).send()
        
        # Optionally ask if they want to load it now
        actions = [
            cl.Action(
                name=f"load_{file_info.get('filename')}",
                value=file_info.get('filename'),
                label=f"📥 Load Now"
            )
        ]
        
        await cl.Message(
            content="Would you like to load this file into the database now?",
            actions=actions
        ).send()
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Upload error: {e}")
        print(error_trace)
        await cl.Message(content=f'<div class="warning-box">❌ Error uploading file: {str(e)}</div>').send()


async def handle_reset_command():
    """Handle /reset command - reset the database"""
    
    # Ask for confirmation
    actions = [
        cl.Action(name="confirm_reset", value="yes", label="⚠️ Yes, Reset Database"),
        cl.Action(name="cancel_reset", value="no", label="❌ Cancel")
    ]
    
    await cl.Message(
        content="""
### ⚠️ Reset Database

**Warning:** This will delete ALL data from the database!

- All households
- All household members
- All QC errors
- All load history

**This action cannot be undone.**

Are you sure you want to continue?
        """,
        actions=actions
    ).send()


async def handle_database_command():
    """Handle /database command - show database statistics"""
    try:
        # Get health/stats info
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_BASE_URL}/api/v1/data/health")
            health = response.json()
        
        db_info = health.get("database", {})
        
        content = f"""
### 📊 Database Statistics

**Connection Status:** {'🟢 Connected' if db_info.get('connected', False) else '🔴 Disconnected'}  
**Database:** {db_info.get('name', 'snapanalyst_db')}

#### 📈 Record Counts
"""
        
        # Get table counts
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                stats_response = await client.get(f"{API_BASE_URL}/api/v1/data/stats")
                stats = stats_response.json()
            
            # Extract from summary object
            summary = stats.get('summary', {})
            content += f"- **Households:** {summary.get('total_households', 0):,}\n"
            content += f"- **Household Members:** {summary.get('total_members', 0):,}\n"
            content += f"- **QC Errors:** {summary.get('total_qc_errors', 0):,}\n"
            content += f"- **Data Loads:** {len(stats.get('by_fiscal_year', [])):,}\n\n"
            
            if summary.get('fiscal_years'):
                content += f"**Fiscal Years:** {', '.join(map(str, summary['fiscal_years']))}\n\n"
            
            if stats.get('last_load'):
                content += f"**Last Load:** {stats['last_load']}\n"
        except Exception as e:
            content += f"*Unable to fetch detailed statistics: {str(e)}*\n\n"
        
        # Check for active loading jobs from API (not session!)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                jobs_response = await client.get(f"{API_BASE_URL}/api/v1/data/load/jobs?active_only=true")
                jobs_data = jobs_response.json()
                active_jobs = jobs_data.get("jobs", [])
            
            if active_jobs:
                # Show the most recent active job
                job_status = active_jobs[0]  # Most recent
                active_job_id = job_status.get("job_id")
                status_value = job_status.get("status")
                
                if status_value in ["in_progress", "processing", "accepted"]:
                    progress = job_status.get("progress", {})
                    percent = progress.get("percent_complete", 0)
                    
                    content += f"""
#### 🔄 Loading in Progress

**Job ID:** `{active_job_id}`  
**Status:** Processing...  
**Progress:** {percent:.1f}% ({progress.get('rows_processed', 0):,} / {progress.get('total_rows', 0):,} rows)  

"""
        except Exception as e:
            # No active jobs or error fetching - this is OK, just log it
            import traceback
            print(f"Debug - Error fetching active jobs: {e}")
            print(traceback.format_exc())
        
        content += f"""
#### 🔧 Actions
- Use `/load` to add data
- Use `/reset` to clear database
- Use `/files` to see available files
        """
        
        await cl.Message(content=content).send()
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Debug - Database command error: {e}")
        print(error_trace)
        await cl.Message(content=f'<div class="warning-box">❌ Error fetching database info: {str(e)}</div>').send()


async def handle_stats_command():
    """Handle /stats command - show database statistics"""
    try:
        # Use the root health endpoint
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_BASE_URL}/health")
            health = response.json()
        db_info = health.get("database", {})
        
        content = f"""
### 📊 Database Statistics

**Status:** {'Connected ✅' if db_info.get('connected', False) else 'Disconnected ❌'}  
**Total Tables:** {db_info.get('tables_count', 0)}  
**Total Records:** {db_info.get('total_records', 'N/A')}  
**Last Updated:** {db_info.get('last_updated', 'Unknown')}
        """
        
        await cl.Message(content=content).send()
        
    except Exception as e:
        await cl.Message(content=f'<div class="warning-box">❌ Error fetching stats: {str(e)}</div>').send()


async def handle_history_command():
    """Handle /history command - show chat history"""
    history = cl.user_session.get("chat_history")
    query_count = cl.user_session.get("query_count")
    
    if not history:
        await cl.Message(content="📝 No chat history yet. Start asking questions!").send()
        return
    
    content = f"### 📝 Your Chat History ({len(history)} messages, {query_count} queries)\n\n"
    
    for i, entry in enumerate(history[-10:], 1):  # Last 10 messages
        role = "👤" if entry["role"] == "user" else "🤖"
        timestamp = entry["timestamp"].split("T")[1][:8]
        content += f"{i}. [{timestamp}] {role} {entry['content'][:100]}...\n\n"
    
    await cl.Message(content=content).send()


async def handle_filter_command(args: Optional[str] = None):
    """Handle /filter command - show or manage filter status"""
    try:
        # Get current filter from API
        filter_data = await call_api("/filter/")
        current_filter = filter_data.get("filter", {})
        description = filter_data.get("description", "No filter")
        is_active = filter_data.get("is_active", False)
        
        # Get session filters
        session_state = cl.user_session.get("current_state_filter", "All States")
        session_year = cl.user_session.get("current_year_filter", "All Years")
        
        content = f"""
### 🔍 Current Data Filter

**Status:** {'✅ Active' if is_active else '⚠️ No Filter (All Data)'}

**Applied Filters:**
- **State:** {current_filter.get('state') or 'All States'}
- **Fiscal Year:** {current_filter.get('fiscal_year') or 'All Years'}

**Description:** {description}

**Session Settings:**
- State Filter: {session_state}
- Year Filter: {session_year}

---

**How filters work:**
- All SQL queries automatically include filter conditions
- Excel downloads are filtered to selected data
- Statistics show only filtered data

**To change filters:**
1. Click the **Settings** icon (⚙️) in the sidebar
2. Select your desired State and/or Fiscal Year
3. Filters apply immediately to all operations

**To clear filter:**
- Set both dropdowns back to "All States" and "All Years"
        """
        
        await cl.Message(content=content).send()
        
    except Exception as e:
        await cl.Message(
            content=f'<div class="warning-box">❌ Error fetching filter status: {str(e)}</div>'
        ).send()


async def handle_download_command(fiscal_year: Optional[str] = None):
    """Handle /export command - download all data to Excel"""
    try:
        await cl.Message(content="📥 Preparing your data export...").send()
        
        # Parse fiscal year if provided
        fy_param = ""
        if fiscal_year:
            try:
                fy = int(fiscal_year)
                if fy in [2021, 2022, 2023]:
                    fy_param = f"?fiscal_year={fy}"
                    await cl.Message(content=f"📊 Exporting data for Fiscal Year {fy}...").send()
                else:
                    await cl.Message(content=f"⚠️ Invalid fiscal year: {fiscal_year}. Using all years (2021-2023).").send()
            except ValueError:
                await cl.Message(content=f"⚠️ Invalid fiscal year format. Using all years.").send()
        else:
            await cl.Message(content="📊 Exporting all data (FY 2021-2023)...").send()
        
        # Generate download URL
        download_url = f"{API_BASE_URL}{API_PREFIX}/data/export/excel{fy_param}"
        
        # Create download message with info
        content = f"""
### ✅ Your Excel export is ready!

**What's included:**
- 📖 **README sheet** - Complete documentation (opens first)
- 📊 **Households** - Household case data
- 👥 **Members** - Household member data
- ⚠️ **QC_Errors** - Quality control errors

**File details:**
- Format: Excel (.xlsx)
- Size: ~2-5 MB
- Data: {'FY ' + fiscal_year if fiscal_year else 'All years (2021-2023)'}

**Download your file:**
[📥 Click here to download]({download_url})

**Note:** The README sheet opens first and contains:
- Column definitions for all tables
- Code lookup tables (status codes, error codes, etc.)
- Table relationships
- Usage instructions

This is a complete, self-documenting data package! 🎉
        """
        
        # Create file element for download
        elements = [
            cl.Text(
                name="Download Link",
                content=f"Download URL: {download_url}",
                display="inline"
            )
        ]
        
        await cl.Message(content=content, elements=elements).send()
        
        # Show tips
        tips = """
### 💡 Pro Tips:

1. **README First**: The README sheet opens automatically and explains everything
2. **Code Lookups**: Use the code tables in README to decode numeric codes
3. **Filtering**: Use Excel's built-in filters on each data sheet
4. **Pivot Tables**: Create pivot tables for quick analysis
5. **Formulas**: Reference the README sheet for column descriptions

**Example analysis:**
- Filter Households by `status=2` (overissuance errors)
- Create pivot table by `state_name` and `snap_benefit`
        """
        
        await cl.Message(content=tips).send()
        
    except Exception as e:
        await cl.Message(content=f'<div class="warning-box">❌ Error generating download: {str(e)}</div>').send()


async def handle_chat_query(question: str):
    """Handle natural language chat query"""
    
    try:
        query_response = await call_api(
            "/chat/query",
            method="POST",
            data={"question": question, "execute": True, "explain": False}  # Execute immediately, no follow-ups
        )
        
        sql = query_response.get("sql")
        explanation = query_response.get("explanation", "")
        
        if not sql:
            await cl.Message(content='<div class="warning-box">❌ Could not generate SQL for this question. Try rephrasing?</div>').send()
            return
        
        # Show SQL and results together
        if query_response.get("executed") and query_response.get("results") is not None:
            # Format and display results
            results_html = format_sql_results(
                query_response["results"],
                query_response.get("row_count", 0)
            )
            
            # Store results in session for CSV download (all results, no limit)
            results_data = query_response["results"]
            cl.user_session.set("last_query_results", results_data)
            
            # Get active filters description
            state_filter = cl.user_session.get("current_state_filter", "All States")
            year_filter = cl.user_session.get("current_year_filter", "All Years")
            filter_parts = []
            if state_filter and state_filter != "All States":
                filter_parts.append(f"State: {state_filter}")
            if year_filter and year_filter != "All Years":
                filter_parts.append(f"Year: {year_filter}")
            filters_desc = ", ".join(filter_parts) if filter_parts else ""
            
            # Generate AI summary using hybrid approach
            ai_summary = await generate_ai_summary(
                question=question,
                sql=sql,
                results=query_response["results"],
                row_count=query_response.get("row_count", 0),
                filters=filters_desc
            )
            
            # Get filter indicator for bottom of response
            filter_indicator = get_filter_indicator()
            
            # Send everything in ONE message for clean output
            await cl.Message(content=f"""
{ai_summary}

---

### 📊 Data

{results_html}

---

### 🔍 Technical Details
```sql
{sql}
```

{f"**Note:** {explanation}" if explanation else ""}
{filter_indicator}
            """, actions=[
                cl.Action(name="download_csv", value="download", label="📥 CSV")
            ]).send()
            
            # Update query count
            query_count = cl.user_session.get("query_count", 0)
            cl.user_session.set("query_count", query_count + 1)
            
            # Add to history
            history = cl.user_session.get("chat_history")
            history.append({
                "timestamp": datetime.now().isoformat(),
                "role": "assistant",
                "content": f"Executed: {sql}",
                "results": query_response.get("row_count", 0)
            })
        else:
            await cl.Message(content='<div class="warning-box">⚠️ Query executed but returned no results.</div>').send()
        
    except Exception as e:
        await cl.Message(content=f'<div class="warning-box">❌ Error: {str(e)}</div>').send()


@cl.action_callback("execute")
async def on_execute(action: cl.Action):
    """Execute the pending SQL query"""
    sql = cl.user_session.get("pending_sql")
    question = cl.user_session.get("pending_question")
    
    if not sql:
        await cl.Message(content="❌ No pending query to execute.").send()
        return
    
    await cl.Message(content="⚙️ Executing query...").send()
    
    try:
        # Execute the query
        result = await call_api(
            "/chat/query",
            method="POST",
            data={"question": question, "execute": True}
        )
        
        if result.get("executed") and result.get("results"):
            # Format and display results
            results_html = format_sql_results(
                result["results"],
                result.get("row_count", 0)
            )
            
            # Store results in session for CSV download (all results, no limit)
            results_data = result["results"]
            cl.user_session.set("last_query_results", results_data)
            
            await cl.Message(content=f"""
### ✅ Query Results

{results_html}

**SQL Executed:**
<div class="sql-code">{result.get('sql', 'N/A')}</div>
            """, actions=[
                cl.Action(name="download_csv", value="download", label="📥 CSV")
            ]).send()
            
            # Update query count
            query_count = cl.user_session.get("query_count", 0)
            cl.user_session.set("query_count", query_count + 1)
            
            # Add to history
            history = cl.user_session.get("chat_history")
            history.append({
                "timestamp": datetime.now().isoformat(),
                "role": "assistant",
                "content": f"Executed: {sql}",
                "results": result.get("row_count", 0)
            })
            
            # Show follow-up suggestions
            if result.get("followup_questions"):
                followup_actions = [
                    cl.Action(
                        name=f"followup_{i}",
                        value=q,
                        label=q
                    )
                    for i, q in enumerate(result["followup_questions"][:3])
                ]
                
                await cl.Message(
                    content="### 💬 Follow-up Questions",
                    actions=followup_actions
                ).send()
        else:
            await cl.Message(content='<div class="warning-box">⚠️ Query executed but returned no results.</div>').send()
        
    except Exception as e:
        await cl.Message(content=f'<div class="warning-box">❌ Execution error: {str(e)}</div>').send()
    
    # Clear pending query
    cl.user_session.set("pending_sql", None)
    cl.user_session.set("pending_question", None)


@cl.action_callback("cancel")
async def on_cancel(action: cl.Action):
    """Cancel the pending query"""
    cl.user_session.set("pending_sql", None)
    cl.user_session.set("pending_question", None)
    await cl.Message(content="✅ Query cancelled.").send()


@cl.action_callback("followup_*")
async def on_followup(action: cl.Action):
    """Handle follow-up question click"""
    question = action.value
    await cl.Message(content=question, author="User").send()
    await handle_chat_query(question)


@cl.action_callback("confirm_reset")
async def on_confirm_reset(action: cl.Action):
    """Handle database reset confirmation"""
    await cl.Message(content="⚙️ Resetting database...").send()
    
    try:
        # Call reset API with confirmation
        result = await call_api("/data/reset", method="POST", data={"confirm": True})
        
        await cl.Message(content=f"""
<div class="success-box">
✅ **Database Reset Complete**

{result.get('message', 'All data has been cleared')}

**Tables Reset:**
- Households
- Household Members  
- QC Errors
- Load History

You can now load fresh data using `/load`.
</div>
        """).send()
        
    except Exception as e:
        await cl.Message(content=f'<div class="warning-box">❌ Error resetting database: {str(e)}</div>').send()


@cl.action_callback("cancel_reset")
async def on_cancel_reset(action: cl.Action):
    """Cancel database reset"""
    await cl.Message(content="✅ Database reset cancelled. No changes made.").send()


@cl.action_callback("load_*")
async def on_load_file(action: cl.Action):
    """Handle file loading"""
    filename = action.value
    
    await cl.Message(content=f"📥 Loading `{filename}`...").send()
    
    try:
        # Extract fiscal year from filename
        import re
        fy_match = re.search(r'fy(\d{4})', filename, re.IGNORECASE)
        if fy_match:
            fiscal_year = int(fy_match.group(1))
        else:
            year_match = re.search(r'20(\d{2})', filename)
            if year_match:
                fiscal_year = int('20' + year_match.group(1))
            else:
                fiscal_year = 2023  # Default
        
        # Trigger data loading
        result = await call_api(
            "/data/load",
            method="POST",
            data={
                "fiscal_year": fiscal_year,
                "filename": filename
            }
        )
        
        await cl.Message(content=f"""
<div class="success-box">
✅ **Data loading initiated!**

**Job ID:** {result.get('job_id', 'N/A')}  
**Status:** {result.get('status', 'Unknown')}  
**File:** {filename}  
**Fiscal Year:** {fiscal_year}

The data is being loaded in the background. You can continue chatting while it processes.

Use `/database` to check progress.
</div>
        """).send()
        
    except Exception as e:
        await cl.Message(content=f'<div class="warning-box">❌ Error loading file: {str(e)}</div>').send()


if __name__ == "__main__":
    # This is handled by chainlit CLI
    pass
