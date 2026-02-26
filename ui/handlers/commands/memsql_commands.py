"""
Vanna SQL Training Commands Module

Handles /memsql command — opens a self-contained sidebar panel with:
- Stats (DDL, docs, SQL pairs, total)
- Grouped entry lists with inline delete buttons
- File upload form (.md/.txt for docs, .json for question-SQL pairs)
- Reset button with "Reload SNAP training data" checkbox
- System Prompt section (view, update, reset)

Subcommands (stats, list, add, reset) are still supported for
backward compatibility but the primary UX is the sidebar panel.
"""

import chainlit as cl
import httpx

from src.clients.api_client import call_api, get_api_base_url, get_api_prefix
from src.core.logging import get_logger

from ...responses import send_error, send_message, send_warning

logger = get_logger(__name__)


async def handle_memsql_command(args: str | None = None):
    """
    Handle /memsql command with subcommands.

    Usage:
        /memsql stats - Show Vanna ChromaDB statistics
        /memsql list - List training data by type
        /memsql add - Add training data (attach files first)
        /memsql reset - Reset: clear all + retrain DDL + reload training data
    """
    if not args or not args.strip():
        await handle_memsql_panel()
        return

    parts = args.strip().split(None, 1)
    subcommand = parts[0].lower()
    sub_args = parts[1] if len(parts) > 1 else None

    if subcommand == "stats":
        await handle_memsql_stats()
    elif subcommand == "list":
        await handle_memsql_list()
    elif subcommand == "add":
        await handle_memsql_add(sub_args)
    elif subcommand == "reset":
        await handle_memsql_reset(sub_args)
    else:
        await send_error(
            f"Unknown subcommand: `{subcommand}`\n\n"
            "Valid subcommands: `stats`, `list`, `add`, `reset`\n\n"
            "Or use **Settings > Knowledge SQL** panel."
        )


async def handle_memsql_stats():
    """Handle /memsql stats - show Vanna ChromaDB per-collection counts."""
    try:
        await send_message("Retrieving Vanna SQL training statistics...")

        stats = await call_api("/llm/vanna/stats")

        ddl = stats.get("ddl_count", 0)
        doc = stats.get("documentation_count", 0)
        sql = stats.get("sql_count", 0)
        total = stats.get("total_count", 0)

        content = f"""### Vanna SQL Training Statistics

| Collection | Entries |
|------------|---------|
| DDL (schema) | {ddl} |
| Documentation | {doc} |
| SQL (question-SQL pairs) | {sql} |
| **Total** | **{total}** |

**Tip:** Open **Settings > Knowledge SQL** to manage training data."""

        await send_message(content)

    except Exception as e:
        await send_error(f"Error fetching Vanna stats: {str(e)}")


async def handle_memsql_list():
    """Handle /memsql list - list Vanna training data grouped by type."""
    try:
        result = await call_api("/llm/vanna/list")

        total = result.get("total_count", 0)

        if total == 0:
            await send_message(
                "**No Vanna training data found.**\n\n"
                "The Vanna ChromaDB is empty or not initialized.\n\n"
                "Use **Settings > Knowledge SQL** to reset and train from scratch."
            )
            return

        content = f"### Vanna SQL Training Data ({total} entries)\n\n"

        # DDL entries
        ddl_entries = result.get("ddl", [])
        if ddl_entries:
            content += f"#### DDL ({len(ddl_entries)} shown)\n"
            for entry in ddl_entries:
                preview = entry.get("content", "")
                # Extract table name from CREATE TABLE statement
                table_name = ""
                if preview and "CREATE TABLE" in preview:
                    parts = preview.split("CREATE TABLE", 1)
                    if len(parts) > 1:
                        table_name = parts[1].strip().split("(")[0].strip()
                if table_name:
                    content += f"- `{entry['id'][:12]}...` - **{table_name}**\n"
                else:
                    content += f"- `{entry['id'][:12]}...` - {preview[:80]}...\n"
            content += "\n"

        # Documentation entries
        doc_entries = result.get("documentation", [])
        if doc_entries:
            content += f"#### Documentation ({len(doc_entries)} shown)\n"
            for entry in doc_entries:
                preview = entry.get("content", "")[:100]
                content += f"- `{entry['id'][:12]}...` - {preview}...\n"
            content += "\n"

        # SQL entries
        sql_entries = result.get("sql", [])
        if sql_entries:
            content += f"#### Question-SQL Pairs ({len(sql_entries)} shown)\n"
            for entry in sql_entries:
                question = entry.get("question", "")
                content += f"- `{entry['id'][:12]}...` - *{question}*\n"
            content += "\n"

        content += "**Tip:** Open **Settings > Knowledge SQL** for summary counts and management."

        await send_message(content)

    except Exception as e:
        await send_error(f"Error listing Vanna training data: {str(e)}")


async def handle_memsql_add(args: str | None = None):
    """Handle /memsql add - add training data from attached files."""
    try:
        message_files = cl.user_session.get("message_files") or []

        if not message_files:
            await send_error(
                "**No files attached**\n\n"
                "Please attach files to your message, or use the **Settings > Knowledge SQL** panel to upload.\n\n"
                "**Supported file types:**\n"
                "- `.md` / `.txt` - Added as documentation context for SQL generation\n"
                '- `.json` - Must contain `{"example_queries": [{"question": "...", "sql": "..."}]}`\n\n'
                "**Example:**\n"
                "Attach files, then type `/memsql add`"
            )
            return

        valid_extensions = (".md", ".txt", ".json")
        valid_files = []
        invalid_files = []

        for file in message_files:
            filename = file.name if hasattr(file, "name") else str(file)
            if filename.endswith(valid_extensions):
                valid_files.append(file)
            else:
                invalid_files.append(filename)

        if not valid_files:
            invalid_list = "\n".join(f"  - {name}" for name in invalid_files)
            await send_error(
                f"**No valid files attached**\n\n"
                f"Only .md, .txt, and .json files are supported.\n\n"
                f"**Rejected files:**\n{invalid_list}"
            )
            return

        if invalid_files:
            invalid_list = ", ".join(f"`{name}`" for name in invalid_files)
            await send_warning(f"Skipping unsupported files: {invalid_list}")

        await send_message(
            f"Uploading {len(valid_files)} file(s) to Vanna SQL training...\n\n"
            f"**Files:** {', '.join(f'`{f.name}`' for f in valid_files)}"
        )

        # Upload files to API
        api_base_url = get_api_base_url()
        api_prefix = get_api_prefix()

        async with httpx.AsyncClient(timeout=60.0) as client:
            files_data = []
            for file in valid_files:
                with open(file.path, "rb") as f:
                    content = f.read()
                    files_data.append(("files", (file.name, content, "text/plain")))

            try:
                response = await client.post(
                    f"{api_base_url}{api_prefix}/llm/vanna/add",
                    files=files_data,
                )
                response.raise_for_status()
                result = response.json()

            except httpx.HTTPError as e:
                await send_error(f"API Error: {str(e)}")
                return

        # Display results
        files_processed = result.get("files_processed", 0)
        files_failed = result.get("files_failed", 0)
        entries_added = result.get("entries_added", 0)
        file_results = result.get("results", [])

        if files_processed > 0 and files_failed == 0:
            status_text = "**All files added successfully!**"
        elif files_processed > 0:
            status_text = f"**Partial success:** {files_processed} succeeded, {files_failed} failed"
        else:
            status_text = f"**All files failed:** {files_failed} error(s)"

        content_parts = [
            status_text,
            f"**Training entries added:** {entries_added}\n",
        ]

        if file_results:
            content_parts.append("**File Results:**")
            for fr in file_results:
                filename = fr.get("filename", "unknown")
                success = fr.get("success", False)
                entries = fr.get("entries", 0)
                error = fr.get("error")

                if success:
                    content_parts.append(f"- `{filename}` ({entries} entries)")
                else:
                    content_parts.append(f"- `{filename}` - {error}")

        content_parts.append("\nOpen **Settings > Knowledge SQL** to see updated statistics.")
        await send_message("\n".join(content_parts))

    except Exception as e:
        import traceback

        logger.error(f"Error in /memsql add: {e}\n{traceback.format_exc()}")
        await send_error(f"Error adding training data: {str(e)}")


async def handle_memsql_panel():
    """Open the ElementSidebar panel with Vanna SQL training overview."""
    try:
        stats = await call_api("/llm/vanna/stats")
        data_list = await call_api("/llm/vanna/list")

        from src.clients.api_client import get_api_external_url, get_api_prefix

        api_url = get_api_external_url() + get_api_prefix()

        user = cl.user_session.get("user")
        user_id = user.identifier if user else "default"

        element = cl.CustomElement(
            name="MemsqlPanel",
            props={
                "stats": stats,
                "ddl": data_list.get("ddl", []),
                "documentation": data_list.get("documentation", []),
                "sql": data_list.get("sql", []),
                "apiUrl": api_url,
                "userId": user_id,
            },
            display="side",
        )
        cl.user_session.set("memsql_panel_element", element)
        await cl.ElementSidebar.set_title("Knowledge SQL")
        await cl.ElementSidebar.set_elements([element], key="memsql")

    except Exception as e:
        await send_error(f"Error opening SQL training panel: {e}")


async def handle_memsql_reset(sub_args: str | None = None):
    """Handle /memsql reset - confirmation dialog for Vanna reset."""
    operation = "reset_vanna"
    warning_text = """### Reset Vanna SQL Training

**Warning:** This will clear ALL Vanna training data and rebuild from scratch!

**What will happen:**
- All training data cleared (DDL, docs, SQL pairs)
- DDL retrained from database schema (all tables)
- Training data from the training folder will be reloaded (docs + query examples)

**This action cannot be undone.** Are you sure?"""

    cl.user_session.set("pending_confirmation", {"operation": operation})

    await cl.Message(
        content=warning_text,
        actions=[
            cl.Action(name="confirm_action", payload={"confirm": "yes"}, label="Yes, Reset"),
            cl.Action(name="confirm_action", payload={"confirm": "no"}, label="Cancel"),
        ],
    ).send()
