"""
Query Handler

Handles natural language chat queries, direct SQL execution, and ChromaDB-enhanced insights.
Uses centralized message templates from src/core/prompts.py.

AI-generated responses (query results with summaries) use AI_PERSONA.
System messages (errors, status) use APP_PERSONA via send_message.
"""

import contextlib
import uuid
from datetime import datetime

import chainlit as cl

# Import from src/ for business logic
from src.clients.api_client import APIError, call_api, stream_from_api
from src.core.config import settings
from src.core.logging import get_logger

# Import centralized prompts
from src.core.prompts import (
    MSG_DIRECT_SQL_RESULT,
    MSG_QUERY_RESULT,
)
from src.services.ai_summary import generate_ai_summary
from src.utils.sql_validator import is_direct_sql, validate_readonly_sql

from ..config import AI_PERSONA

# Import from ui/ for formatting and personas
from ..formatters import format_sql_display, format_sql_results, get_filter_indicator
from ..responses import send_ai_message, send_error, send_message, send_warning

logger = get_logger(__name__)

MAX_SESSION_RESULT_ROWS = 5000  # Cap stored results for CSV download (full export via API)
MAX_CHAT_HISTORY = 100  # Cap in-memory chat history entries


async def handle_chat_query(question: str):
    """
    Handle natural language chat query for SQL data retrieval.

    Supports:
    - Natural language queries (sent to LLM for SQL generation)
    - Direct SQL queries (SELECT/WITH only, executed directly)
    - Analysis instructions using | separator

    Note: SQL queries use direct API call (no streaming) for immediate results.
    For streaming text generation, use handle_kb_insight() instead.

    Args:
        question: User's question or SQL query
    """
    try:
        # Check if user provided direct SQL
        is_sql_query = is_direct_sql(question)

        logger.info(f"Processing query - Is SQL: {is_sql_query}, Question: {question[:100]}")

        if is_sql_query:
            query_response = await _execute_direct_sql(question)
            if query_response is None:
                return  # Error already handled
            sql = query_response.get("sql")
            explanation = query_response.get("explanation", "")
        else:
            # Natural language - use direct API call (no streaming)
            logger.info("Sending to Vanna for SQL generation (direct API)")
            user_id = cl.user_session.get("user_id") or "system"
            # Pass per-session SQL LLM settings
            llm_sql_settings = cl.user_session.get("llm_sql_settings")
            llm_params = None
            if llm_sql_settings:
                llm_params = {
                    k: v
                    for k, v in llm_sql_settings.items()
                    if k in ("model", "temperature", "max_tokens", "top_p", "context_window") and v is not None
                }
            query_response = await call_api(
                "/chat/data",
                method="POST",
                data={
                    "question": question,
                    "execute": True,
                    "explain": False,
                    "user_id": user_id,
                    "llm_params": llm_params,
                },
            )
            sql = query_response.get("sql")
            explanation = query_response.get("explanation", "")

        if not sql:
            await send_error("Could not generate SQL for this question. Try rephrasing?")
            return

        # Show SQL and results together
        if query_response.get("executed") and query_response.get("results") is not None:
            await _display_query_results(
                query_response=query_response, sql=sql, question=question, explanation=explanation
            )
        else:
            await send_warning("Query executed but returned no results.")

    except APIError as e:
        # User-friendly error from the API (e.g., LLM couldn't generate SQL)
        logger.warning(f"API error in chat query: {e.message}")
        await send_error(e.message)
    except Exception as e:
        logger.error(f"Error in chat query: {e}")
        # Check if it's an httpx error with response detail
        if hasattr(e, "response") and e.response is not None:
            try:
                detail = e.response.json().get("detail", str(e))
                await send_message(detail)
                return
            except Exception:
                pass
        await send_error(f"Error: {str(e)}")


async def _execute_direct_sql(sql_question: str) -> dict | None:
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
        response = await call_api("/query/sql", method="POST", data={"sql": sql_question, "limit": 50000})

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
            "explanation": f"Direct SQL execution (bypassed Vanna) - {response.get('execution_time_ms', 0):.2f}ms",
        }

    except APIError as e:
        logger.warning(f"API error in direct SQL: {e.message}")
        await send_message(e.message)
        return None
    except Exception as e:
        logger.error(f"Direct SQL execution error: {e}")
        # Check if it's an httpx error with response detail
        if hasattr(e, "response") and e.response is not None:
            try:
                detail = e.response.json().get("detail", str(e))
                await send_message(detail)
                return None
            except Exception:
                pass
        await send_error(f"SQL execution error: {str(e)}")
        return None


async def _display_query_results(query_response: dict, sql: str, question: str, explanation: str):
    """
    Display query results with AI summary and data table.

    Args:
        query_response: Response from query execution
        sql: SQL that was executed
        question: Original user question
        explanation: Explanation from query generator
    """
    # Format and display results
    results_html = format_sql_results(query_response["results"], query_response.get("row_count", 0))

    # Store results in session for CSV download (capped to limit memory; full export via API)
    results_data = query_response["results"]
    cl.user_session.set("last_query_results", results_data[:MAX_SESSION_RESULT_ROWS])
    cl.user_session.set("last_query_row_count", query_response.get("row_count", 0))

    # Store in thread context for Insights mode
    from ..services.thread_context import get_thread_context

    thread_ctx = get_thread_context()

    # Generate a unique response ID for feedback tracking
    response_id = str(uuid.uuid4())[:8]

    thread_ctx.add_query(
        question=question,
        sql=sql,
        results=results_data,
        row_count=query_response.get("row_count", 0),
        response_id=response_id,
    )

    # Get active filters description
    state_filter = cl.user_session.get("current_state_filter", "All States")
    year_filter = cl.user_session.get("current_year_filter", "All Years")
    filter_parts = []
    if state_filter and state_filter != "All States":
        filter_parts.append(f"State: {state_filter}")
    if year_filter and year_filter != "All Years":
        filter_parts.append(f"Year: {year_filter}")
    filters_desc = ", ".join(filter_parts) if filter_parts else ""

    # Generate AI summary (use separate summary LLM settings)
    llm_summary_settings = cl.user_session.get("llm_summary_settings")
    summary_llm_params = None
    if llm_summary_settings:
        summary_llm_params = {
            k: v
            for k, v in llm_summary_settings.items()
            if k
            in ("model", "temperature", "max_tokens", "top_p", "context_window", "summary_enabled", "summary_max_rows")
            and v is not None
        }

    row_count = query_response.get("row_count", 0)
    user_id = cl.user_session.get("user_id") or "system"

    ai_summary = await generate_ai_summary(
        question=question,
        sql=sql,
        results=query_response["results"],
        row_count=row_count,
        filters=filters_desc,
        llm_params=summary_llm_params,
        user_id=user_id,
    )

    # Always generate the template summary as a footer line
    # When AI summary is enabled and succeeded, show both: AI text on top, template footer below
    # When AI summary is disabled/failed, ai_summary already IS the template, so skip duplicate
    from src.services.ai_summary import generate_simple_summary

    result_summary = ""
    summary_enabled = (summary_llm_params or {}).get("summary_enabled", settings.llm_sql_summary_enabled)
    if summary_enabled and row_count > 0:
        result_summary = "\n" + generate_simple_summary(question, row_count, query_response["results"], filters_desc)

    # Get filter indicator for bottom of response
    filter_indicator = get_filter_indicator()

    # Build SQL section with formatted SQL for readability
    formatted_sql = format_sql_display(sql)

    # Build complete message using template
    # SQL is now embedded in MSG_QUERY_RESULT as a collapsible <details> section
    content = MSG_QUERY_RESULT.format(
        ai_summary=ai_summary,
        result_summary=result_summary,
        results_html=results_html,
        sql=formatted_sql,
        filter_indicator=filter_indicator,
    )

    # Store response context for feedback logging
    cl.user_session.set("last_response_id", response_id)
    cl.user_session.set("last_question", question)
    cl.user_session.set("last_sql", sql)

    # Create CSV download action to be displayed with the message
    csv_action = cl.Action(name="download_csv", payload={"action": "download"}, label="↓ CSV")

    # Send message with only CSV button - Chainlit's built-in feedback will appear automatically
    message = cl.Message(content=content, author=AI_PERSONA, actions=[csv_action])
    await message.send()

    # Store mapping for feedback-driven Vanna training (SQL mode only)
    from ui.services.feedback_training import store_query_for_feedback

    store_query_for_feedback(message.id, question, sql)

    # Update query count
    query_count = cl.user_session.get("query_count", 0)
    cl.user_session.set("query_count", query_count + 1)

    # Add to history (cap to prevent unbounded growth)
    history = cl.user_session.get("chat_history")
    history.append(
        {
            "timestamp": datetime.now().isoformat(),
            "role": "assistant",
            "content": f"Executed: {sql}",
            "results": query_response.get("row_count", 0),
            "response_id": response_id,
        }
    )
    if len(history) > MAX_CHAT_HISTORY:
        cl.user_session.set("chat_history", history[-MAX_CHAT_HISTORY:])


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
        user_id = cl.user_session.get("user_id") or "system"
        result = await call_api(
            "/chat/data", method="POST", data={"question": question, "execute": True, "user_id": user_id}
        )

        if result.get("executed") and result.get("results"):
            results_html = format_sql_results(result["results"], result.get("row_count", 0))

            # Store results in session for CSV download (capped to limit memory)
            results_data = result["results"]
            cl.user_session.set("last_query_results", results_data[:MAX_SESSION_RESULT_ROWS])

            content = MSG_DIRECT_SQL_RESULT.format(
                results_html=results_html, sql=format_sql_display(result.get("sql", "N/A"))
            )

            # AI query responses use AI_PERSONA
            await send_ai_message(
                content, actions=[cl.Action(name="download_csv", payload={"action": "download"}, label="📥 CSV")]
            )

            # Update query count
            query_count = cl.user_session.get("query_count", 0)
            cl.user_session.set("query_count", query_count + 1)

            # Add to history (cap to prevent unbounded growth)
            history = cl.user_session.get("chat_history")
            history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "role": "assistant",
                    "content": f"Executed: {sql}",
                    "results": result.get("row_count", 0),
                }
            )
            if len(history) > MAX_CHAT_HISTORY:
                cl.user_session.set("chat_history", history[-MAX_CHAT_HISTORY:])

            # Show follow-up suggestions
            if result.get("followup_questions"):
                followup_actions = [
                    cl.Action(name=f"followup_{i}", payload={"question": q}, label=q)
                    for i, q in enumerate(result["followup_questions"][:3])
                ]

                await send_message("### 💬 Follow-up Questions", actions=followup_actions)
        else:
            await send_warning("Query executed but returned no results.")

    except APIError as e:
        await send_message(e.message)
    except Exception as e:
        # Check if it's an httpx error with response detail
        error_msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                detail = e.response.json().get("detail", error_msg)
                await send_message(detail)
            except Exception:
                await send_error(f"Execution error: {error_msg}")
        else:
            await send_error(f"Execution error: {error_msg}")

    # Clear pending query
    cl.user_session.set("pending_sql", None)
    cl.user_session.set("pending_question", None)


async def handle_insight_query(insight_question: str, include_thread: bool = False, use_streaming: bool = True):
    """
    Handle insight request using KB ChromaDB + optional thread context.

    Supports filtering: snap_qc prefix, #tag, @me, etc.
    Uses streaming for real-time text generation when use_streaming=True.
    """
    from src.utils.kb_filter_parser import format_search_scope, parse_kb_filters

    try:
        # Get user ID
        user_id = cl.user_session.get("user_id")
        if not user_id:
            from datasets import get_active_dataset

            ds = get_active_dataset()
            user_id = ds.get_anonymous_email() if ds else "anonymous@app.com"

        # Parse filters
        filters = parse_kb_filters(insight_question, user_id)

        logger.info(f"Insight: path={filters['chromadb_path']}, question={filters['question'][:60]}")

        # Show scope
        scope = format_search_scope(filters)

        if use_streaming:
            # Use streaming for real-time text generation
            await _handle_insight_streaming(insight_question, user_id, scope, include_thread)
        else:
            # Fallback to non-streaming
            msg = f"{scope}\n🔍 " + ("Analyzing with thread..." if include_thread else "Looking up...")
            await send_message(msg)

            # Call API for insight generation
            response = await call_api(
                "/chat/insights",
                method="POST",
                data={"question": filters["question"], "include_thread": include_thread, "user_id": user_id},
            )

            if response and "insight" in response:
                await send_ai_message(response["insight"])
            else:
                await send_message("Unable to generate insight.")

        # Update history (cap to prevent unbounded growth)
        history = cl.user_session.get("chat_history")
        history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "role": "assistant",
                "content": f"Insight: {filters['question']}",
                "type": "insight",
            }
        )
        if len(history) > MAX_CHAT_HISTORY:
            cl.user_session.set("chat_history", history[-MAX_CHAT_HISTORY:])

    except APIError as e:
        logger.warning(f"API error: {e.message}")
        await send_message(e.message)
    except Exception as e:
        logger.error(f"Error in insight query: {e}")
        await send_error(f"Error: {str(e)}")


async def _handle_insight_streaming(question: str, user_id: str, scope: str, include_thread: bool = False) -> None:
    """
    Handle insight generation with streaming text output.

    Args:
        question: The insight question
        user_id: User ID for filtering
        scope: Formatted search scope string
        include_thread: Whether to include thread context (previous query data)
    """
    msg = cl.Message(content=f"{scope}\n\n🔍 Searching knowledge base...")
    await msg.send()

    sources_text = ""
    text_content = ""

    # Pass per-session LLM settings for insights/knowledge
    llm_session_key = "llm_insights_settings" if include_thread else "llm_knowledge_settings"
    llm_settings = cl.user_session.get(llm_session_key)
    llm_params = None
    if llm_settings:
        llm_params = {
            k: v
            for k, v in llm_settings.items()
            if k in ("model", "temperature", "max_tokens", "top_p", "context_window") and v is not None
        }

    # Get thread context if requested
    data_context = None
    if include_thread:
        from ..services.thread_context import get_thread_context

        thread_ctx = get_thread_context()
        all_queries = thread_ctx.get_queries_for_insight()  # All queries, newest first

        if all_queries:
            import json

            from src.core.config import settings

            # Dynamic budget: use context_window to determine how much thread data to send
            # Estimate: 1 token ≈ 4 chars. Reserve space for system prompt, KB docs, and response.
            context_window = (llm_params or {}).get("context_window") or 0
            max_response_tokens = (llm_params or {}).get("max_tokens") or settings.llm_kb_max_tokens

            if context_window and context_window > 0:
                # Context-window-aware: use 50% of input budget for thread data
                available_input_tokens = context_window - max_response_tokens - 500  # 500 token safety margin
                max_context_size = int(available_input_tokens * 4 * 0.5)  # 50% for thread, rest for KB + prompt
                max_context_size = max(8000, min(max_context_size, settings.llm_kb_max_data_size))
            else:
                # Fallback to config default
                max_context_size = settings.llm_kb_max_data_size

            # Dynamic sample rows: more rows for larger budgets
            if max_context_size > 40000:
                max_sample_rows = 30
            elif max_context_size > 20000:
                max_sample_rows = 15
            elif max_context_size > 10000:
                max_sample_rows = 10
            else:
                max_sample_rows = 5

            thread_data = []
            current_size = 0

            # Prioritize most recent queries first
            for query in all_queries:
                query_data = {
                    "question": query.question,
                    "sql": query.sql,
                    "row_count": query.row_count,
                    "results": query.results[:max_sample_rows] if query.results else [],
                    "timestamp": query.timestamp,
                }

                query_size = len(json.dumps(query_data))

                if current_size + query_size > max_context_size:
                    # Try with fewer rows before giving up
                    query_data["results"] = query.results[:3] if query.results else []
                    query_size = len(json.dumps(query_data))
                    if current_size + query_size > max_context_size:
                        break

                thread_data.append(query_data)
                current_size += query_size

            logger.info(
                f"Thread context: {len(thread_data)} queries, {current_size} chars (budget: {max_context_size}, rows/query: {max_sample_rows})"
            )

            data_context = json.dumps(
                {"thread_queries": thread_data, "total_queries": len(thread_data), "context_size_chars": current_size}
            )

    stream = None
    try:
        stream = stream_from_api(
            "/chat/insights/stream",
            data={
                "question": question,
                "user_id": user_id,
                "data_context": data_context,
                "llm_params": llm_params,
            },
        )

        async for event in stream:
            event_type = event.get("event", "message")
            data = event.get("data", {})

            if event_type == "progress":
                progress_msg = data.get("message", "")
                if progress_msg:
                    msg.content = f"{scope}\n\n{progress_msg}"
                    await msg.update()

            elif event_type == "sources":
                sources = data.get("sources", [])
                if sources:
                    # Deduplicate: multiple chunks from the same document should show once
                    source_names = list(dict.fromkeys(s.split(" - ")[-1] if " - " in s else s for s in sources))
                    shown = source_names[:3]
                    sources_text = f"\n\n---\n*Sources: {', '.join(shown)}*"
                    if len(source_names) > 3:
                        sources_text = f"\n\n---\n*Sources: {', '.join(shown)} (+{len(source_names) - 3} more)*"
                    msg.content = f"{scope}\n\n💡 **Generating insight...**"
                    await msg.update()

            elif event_type == "text":
                chunk = data.get("chunk", "")
                if chunk:
                    text_content += chunk
                    # Show text content, sources will be appended at the end
                    msg.content = f"{text_content}{sources_text}"
                    await msg.update()

            elif event_type == "error":
                error_msg = data.get("error", "Unknown error")
                msg.content = f"❌ {error_msg}"
                await msg.update()
                return

            elif event_type == "done":
                break

        # Final update with AI persona
        if text_content:
            msg.author = AI_PERSONA
            await msg.update()

    except APIError as e:
        msg.content = f"❌ {e.message}"
        await msg.update()
    except Exception as e:
        logger.error(f"Insight streaming error: {e}")
        msg.content = f"❌ Error: {str(e)}"
        await msg.update()
    finally:
        # Ensure stream is properly closed
        if stream is not None:
            with contextlib.suppress(Exception):
                await stream.aclose()
