"""
Query Handler

Handles natural language chat queries and direct SQL execution.
Uses centralized message templates from src/core/prompts.py.

AI-generated responses (query results with summaries) use AI_PERSONA.
System messages (errors, status) use APP_PERSONA via send_message.
"""

import chainlit as cl
from datetime import datetime
from typing import Optional
import logging
import uuid

# Import from src/ for business logic
from src.clients.api_client import call_api, APIError
from src.services.ai_summary import generate_ai_summary
from src.utils.sql_validator import is_direct_sql, validate_readonly_sql

# Import from ui/ for formatting and personas
from ..formatters import format_sql_results, get_filter_indicator, format_sql_display
from ..config import AI_PERSONA
from ..responses import send_message, send_error, send_warning, send_ai_message

# Import centralized prompts
from src.core.prompts import (
    MSG_QUERY_RESULT,
    MSG_QUERY_SQL_SECTION,
    MSG_DIRECT_SQL_RESULT,
)

logger = logging.getLogger(__name__)


async def handle_chat_query(question: str):
    """
    Handle natural language chat query with optional separator for analysis instructions.
    
    Supports:
    - Natural language queries (sent to LLM for SQL generation)
    - Direct SQL queries (SELECT/WITH only, executed directly)
    - Analysis instructions using | separator
    
    Args:
        question: User's question or SQL query
    """
    try:
        # Parse question for separator pattern: <SQL_QUERY> | <ANALYSIS_INSTRUCTIONS>
        sql_question = question
        analysis_instructions = None
        
        if "|" in question:
            parts = question.split("|", maxsplit=1)
            sql_question = parts[0].strip()
            analysis_instructions = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
        
        # Check if user provided direct SQL
        is_sql_query = is_direct_sql(sql_question)
        
        logger.info(f"Processing query - Is SQL: {is_sql_query}, Question: {sql_question[:100]}")
        
        if is_sql_query:
            query_response = await _execute_direct_sql(sql_question)
            if query_response is None:
                return  # Error already handled
        else:
            # Natural language - send to Vanna for SQL generation
            logger.info("Sending to Vanna for SQL generation")
            query_response = await call_api(
                "/chat/query",
                method="POST",
                data={"question": sql_question, "execute": True, "explain": False}
            )
        
        sql = query_response.get("sql")
        explanation = query_response.get("explanation", "")
        
        if not sql:
            await send_error("Could not generate SQL for this question. Try rephrasing?")
            return
        
        # Show SQL and results together
        if query_response.get("executed") and query_response.get("results") is not None:
            await _display_query_results(
                query_response=query_response,
                sql=sql,
                sql_question=sql_question,
                analysis_instructions=analysis_instructions,
                explanation=explanation
            )
        else:
            await send_warning("Query executed but returned no results.")
        
    except APIError as e:
        # User-friendly error from the API (e.g., LLM couldn't generate SQL)
        logger.warning(f"API error in chat query: {e.message}")
        await send_message(e.message)
    except Exception as e:
        logger.error(f"Error in chat query: {e}")
        # Check if it's an httpx error with response detail
        if hasattr(e, 'response') and e.response is not None:
            try:
                detail = e.response.json().get('detail', str(e))
                await send_message(detail)
                return
            except Exception:
                pass
        await send_error(f"Error: {str(e)}")


async def _execute_direct_sql(sql_question: str) -> Optional[dict]:
    """
    Execute direct SQL query after validation.
    
    Args:
        sql_question: SQL query to execute
        
    Returns:
        Query response dict or None if validation/execution failed
    """
    # Validate it's read-only
    is_valid, error_msg = validate_readonly_sql(sql_question)
    
    logger.info(f"SQL validation - Valid: {is_valid}")
    
    if not is_valid:
        await send_error(error_msg)
        return None
    
    # Execute directly without Vanna
    logger.info("Executing SQL directly (bypassing Vanna)")
    try:
        response = await call_api(
            "/query/sql",
            method="POST",
            data={"sql": sql_question, "limit": 50000}
        )
        
        if not response.get("success"):
            error_msg = response.get("error", "Unknown error")
            logger.error(f"SQL execution failed: {error_msg}")
            await send_error(f"SQL execution error: {error_msg}")
            return None
        
        # Reformat response to match expected structure
        sql = sql_question
        results = response.get("data", [])
        row_count = response.get("row_count", len(results))
        
        logger.info(f"Direct SQL execution successful - {row_count} rows returned")
        
        return {
            "sql": sql,
            "executed": True,
            "results": results,
            "row_count": row_count,
            "explanation": f"Direct SQL execution (bypassed Vanna) - {response.get('execution_time_ms', 0):.2f}ms"
        }
        
    except APIError as e:
        logger.warning(f"API error in direct SQL: {e.message}")
        await send_message(e.message)
        return None
    except Exception as e:
        logger.error(f"Direct SQL execution error: {e}")
        # Check if it's an httpx error with response detail
        if hasattr(e, 'response') and e.response is not None:
            try:
                detail = e.response.json().get('detail', str(e))
                await send_message(detail)
                return None
            except Exception:
                pass
        await send_error(f"SQL execution error: {str(e)}")
        return None


async def _display_query_results(
    query_response: dict,
    sql: str,
    sql_question: str,
    analysis_instructions: Optional[str],
    explanation: str
):
    """
    Display query results with AI summary and data table.
    
    Args:
        query_response: Response from query execution
        sql: SQL that was executed
        sql_question: Original question (left of | separator)
        analysis_instructions: Special analysis instructions (right of | separator)
        explanation: Explanation from query generator
    """
    # Format and display results
    results_html = format_sql_results(
        query_response["results"],
        query_response.get("row_count", 0)
    )
    
    # Store results in session for CSV download
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
    
    # Generate AI summary
    ai_summary = await generate_ai_summary(
        question=sql_question,
        sql=sql,
        results=query_response["results"],
        row_count=query_response.get("row_count", 0),
        filters=filters_desc,
        analysis_instructions=analysis_instructions
    )
    
    # Get filter indicator for bottom of response
    filter_indicator = get_filter_indicator()
    
    # Build SQL section with formatted SQL for readability
    formatted_sql = format_sql_display(sql)
    sql_section = MSG_QUERY_SQL_SECTION.format(sql=formatted_sql)
    if explanation:
        sql_section += f"\n\n**Note:** {explanation}"
    
    # Build complete message using template
    content = MSG_QUERY_RESULT.format(
        ai_summary=ai_summary,
        results_html=results_html,
        sql_section=sql_section,
        filter_indicator=filter_indicator
    )
    
    # Generate a unique response ID for feedback tracking
    response_id = str(uuid.uuid4())[:8]
    
    # Store response context for feedback logging
    cl.user_session.set("last_response_id", response_id)
    cl.user_session.set("last_question", sql_question)
    cl.user_session.set("last_sql", sql)
    
    # AI query responses use AI_PERSONA with feedback buttons
    await send_ai_message(content, actions=[
        cl.Action(name="download_csv", value="download", label="📥 CSV"),
        cl.Action(name="feedback_positive", value=response_id, label="👍"),
        cl.Action(name="feedback_negative", value=response_id, label="👎"),
    ])
    
    # Update query count
    query_count = cl.user_session.get("query_count", 0)
    cl.user_session.set("query_count", query_count + 1)
    
    # Add to history
    history = cl.user_session.get("chat_history")
    history.append({
        "timestamp": datetime.now().isoformat(),
        "role": "assistant",
        "content": f"Executed: {sql}",
        "results": query_response.get("row_count", 0),
        "response_id": response_id
    })


async def execute_pending_query():
    """
    Execute a pending SQL query that was previewed.
    Called by the execute action callback.
    """
    sql = cl.user_session.get("pending_sql")
    question = cl.user_session.get("pending_question")
    
    if not sql:
        await send_error("No pending query to execute.")
        return
    
    await send_message("⚙️ Executing query...")
    
    try:
        result = await call_api(
            "/chat/query",
            method="POST",
            data={"question": question, "execute": True}
        )
        
        if result.get("executed") and result.get("results"):
            results_html = format_sql_results(
                result["results"],
                result.get("row_count", 0)
            )
            
            # Store results in session for CSV download
            results_data = result["results"]
            cl.user_session.set("last_query_results", results_data)
            
            content = MSG_DIRECT_SQL_RESULT.format(
                results_html=results_html,
                sql=format_sql_display(result.get('sql', 'N/A'))
            )
            
            # AI query responses use AI_PERSONA
            await send_ai_message(content, actions=[
                cl.Action(name="download_csv", value="download", label="📥 CSV")
            ])
            
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
                
                await send_message(
                    "### 💬 Follow-up Questions",
                    actions=followup_actions
                )
        else:
            await send_warning("Query executed but returned no results.")
        
    except APIError as e:
        await send_message(e.message)
    except Exception as e:
        # Check if it's an httpx error with response detail
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                detail = e.response.json().get('detail', error_msg)
                await send_message(detail)
            except Exception:
                await send_error(f"Execution error: {error_msg}")
        else:
            await send_error(f"Execution error: {error_msg}")
    
    # Clear pending query
    cl.user_session.set("pending_sql", None)
    cl.user_session.set("pending_question", None)
