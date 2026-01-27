"""
Memory Commands Module

Handles AI memory/ChromaDB management commands:
- /mem stats: Show ChromaDB statistics
- /mem list: List all documentation entries
- /mem add [category]: Add documentation to knowledge base
- /mem delete <id>: Delete a documentation entry
- /mem reset: Reset ChromaDB and re-train
"""

import logging

import chainlit as cl
import httpx

# Import from src/ for business logic
from src.clients.api_client import call_api, get_api_base_url, get_api_prefix

# Import from ui/ for UI-specific config and message helpers
from ...responses import send_error, send_message, send_warning

logger = logging.getLogger(__name__)


async def handle_mem_command(args: str | None = None):
    """
    Handle /mem command with subcommands.

    Usage:
        /mem stats - Show ChromaDB statistics
        /mem list - List all documentation entries
        /mem add [category] - Add documentation (attach files first)
        /mem delete <id> - Delete a documentation entry
        /mem reset - Reset ChromaDB and re-train
    """
    if not args or not args.strip():
        await send_message(
            """### AI Memory Management

**Usage:** `/mem <command>`

**Commands:**
- `/mem stats` - Show ChromaDB statistics
- `/mem list` - List all documentation in knowledge base
- `/mem add [category]` - Add custom documentation (attach .md/.txt files)
- `/mem delete <id>` - Remove documentation entry
- `/mem reset` - Clear and rebuild AI memory

**Examples:**
```
/mem stats
/mem list
/mem add business-rules #SNAP #eligibility
/mem delete doc-12345
```"""
        )
        return

    # Parse subcommand and remaining args
    parts = args.strip().split(None, 1)
    subcommand = parts[0].lower()
    sub_args = parts[1] if len(parts) > 1 else None

    if subcommand == "stats":
        await handle_memstats()
    elif subcommand == "list":
        await handle_memlist()
    elif subcommand == "add":
        await handle_memadd(sub_args)
    elif subcommand == "delete":
        await handle_memdelete(sub_args)
    elif subcommand == "reset":
        await handle_memreset()
    else:
        await send_error(
            f"❌ Unknown subcommand: `{subcommand}`\n\n"
            "Valid subcommands: `stats`, `list`, `add`, `delete`, `reset`\n\n"
            "Type `/mem` for help."
        )


async def handle_memreset():
    """Handle /memreset command - reset ChromaDB and re-train."""
    actions = [
        cl.Action(name="confirm_memreset", payload={"confirm": "yes"}, label="⚠️ Yes, Reset Memory"),
        cl.Action(name="cancel_memreset", payload={"confirm": "no"}, label="❌ Cancel")
    ]

    await send_message(
        """### ⚠️ Reset AI Memory (ChromaDB)

**Warning:** This will clear ALL training data and rebuild from scratch!

**What will be deleted:**
- All vector embeddings
- User query history (if ongoing training was enabled)
- Custom documentation added via `/mem add`

**What will be restored:**
- Database schema (DDL)
- Business context documentation
- Query examples from configuration

**This action cannot be undone.**

Are you sure you want to continue?""",
        actions=actions
    )


async def handle_memadd(args: str | None = None):
    """Handle /memadd command - add documentation from chat-attached files."""
    from src.utils.tag_parser import format_tags_display, parse_memadd_command

    try:
        message_files = cl.user_session.get("message_files") or []

        if not message_files:
            await send_error(
                "❌ **No files attached**\n\n"
                "Please attach .md or .txt files to your message, then use `/mem add`\n\n"
                "**Syntax:** `/mem add [category] [#tag1 #tag2 ...]`\n\n"
                "**Examples:**\n"
                "- Attach files → `/mem add business-rules #SNAP #eligibility`\n"
                "- Attach files → `/mem add glossary #codes`\n"
                "- Attach files → `/mem add #SNAP` (no category = 'general')\n"
                "- Attach files → `/mem add` (no category, no tags)"
            )
            return

        category, tags = parse_memadd_command(args or "")

        valid_files = []
        invalid_files = []

        for file in message_files:
            filename = file.name if hasattr(file, 'name') else str(file)
            if filename.endswith(('.md', '.txt')):
                valid_files.append(file)
            else:
                invalid_files.append(filename)

        if not valid_files:
            invalid_list = '\n'.join(f"  - {name}" for name in invalid_files)
            await send_error(
                f"❌ **No valid files attached**\n\n"
                f"Only .md and .txt files are allowed.\n\n"
                f"**Rejected files:**\n{invalid_list}"
            )
            return

        if invalid_files:
            invalid_list = ', '.join(f"`{name}`" for name in invalid_files)
            await send_warning(f"⚠️ Skipping invalid files: {invalid_list}")

        tags_display = format_tags_display(tags)
        tags_info = f" with tags {tags_display}" if tags else ""
        await send_message(
            f"📤 **Uploading {len(valid_files)} file(s)** to knowledge base\n\n"
            f"- **Category:** `{category}`{tags_info}\n"
            f"- **Files:** {', '.join(f'`{f.name}`' for f in valid_files)}"
        )

        # Upload files to API
        api_base_url = get_api_base_url()
        api_prefix = get_api_prefix()

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Prepare multipart form data
            files_data = []
            for file in valid_files:
                with open(file.path, 'rb') as f:
                    content = f.read()
                    files_data.append(('files', (file.name, content, 'text/plain')))

            # Prepare form fields
            form_data = {
                'category': category,
                'tags': ' '.join(f"#{tag}" for tag in tags) if tags else ''
            }

            try:
                response = await client.post(
                    f"{api_base_url}{api_prefix}/llm/memory/add",
                    files=files_data,
                    data=form_data
                )
                response.raise_for_status()
                result = response.json()

            except httpx.HTTPError as e:
                await send_error(f"❌ API Error: {str(e)}")
                return

        # Display results
        await display_upload_results(result, category, tags)

    except Exception as e:
        import traceback
        logger.error(f"Error in /memadd: {e}\n{traceback.format_exc()}")
        await send_error(f"Error adding documentation: {str(e)}")


async def display_upload_results(result: dict, category: str, tags: list):
    """Display upload results with per-file status."""
    from src.utils.tag_parser import format_tags_display

    files_processed = result.get('files_processed', 0)
    files_failed = result.get('files_failed', 0)
    total_chars = result.get('total_chars_added', 0)
    file_results = result.get('results', [])

    # Build summary message
    if files_processed > 0 and files_failed == 0:
        status_emoji = "✅"
        status_text = "**All files added successfully!**"
    elif files_processed > 0 and files_failed > 0:
        status_emoji = "⚠️"
        status_text = f"**Partial success:** {files_processed} succeeded, {files_failed} failed"
    else:
        status_emoji = "❌"
        status_text = f"**All files failed:** {files_failed} error(s)"

    # Build detailed results
    content_parts = [
        f"{status_emoji} {status_text}\n",
        f"**Category:** `{category}`"
    ]

    if tags:
        tags_display = format_tags_display(tags)
        content_parts.append(f"**Tags:** {tags_display}")

    content_parts.append(f"**Total size:** {total_chars:,} characters\n")

    # Per-file results
    if file_results:
        content_parts.append("**File Results:**")
        for file_result in file_results:
            filename = file_result.get('filename', 'unknown')
            success = file_result.get('success', False)
            chars = file_result.get('chars_added', 0)
            error = file_result.get('error')

            if success:
                content_parts.append(f"- ✅ `{filename}` ({chars:,} chars)")
            else:
                content_parts.append(f"- ❌ `{filename}` - {error}")

    content_parts.append("\n💡 **Tip:** Use `/mem list` to see all documentation in the knowledge base.")

    await send_message("\n".join(content_parts))


async def handle_memstats():
    """Handle /mem stats command - show Knowledge Base statistics."""
    try:
        await send_message("📊 Retrieving Knowledge Base statistics...")

        stats = await call_api("/llm/memory/stats")

        exists_status = "✅ Active" if stats.get('chromadb_exists') else "⚠️ Not initialized"
        size_mb = stats.get('chromadb_size_mb', 0.0)
        last_modified = stats.get('last_modified', 'Never')

        # Get document count
        training_stats = stats.get('training_stats', {})
        doc_count = training_stats.get('total_documents', 0)

        content = f"""### Knowledge Base Statistics

**Status:** {exists_status}
**Documents:** {doc_count}
**Location:** `{stats.get('chromadb_path', 'N/A')}`
**Size:** {size_mb:.2f} MB
**Last Modified:** {last_modified}

**💡 Tips:**
- Use `/mem list` to see all documentation entries
- Use `/mem add` to add custom documentation
- Use `/mem delete <id>` to remove a document
"""

        await send_message(content)

    except Exception as e:
        await send_error(f"Error fetching KB stats: {str(e)}")


async def handle_memlist():
    """Handle /mem list command - list all documentation entries."""
    try:

        result = await call_api("/llm/memory/list")

        total = result.get('total_entries', 0)
        entries = result.get('entries', [])

        if total == 0:
            await send_message(
                "**No documentation entries found.**\n\n"
                "The knowledge base is empty or not initialized.\n\n"
                "💡 Use `/mem add` to add custom documentation."
            )
            return

        content = f"### AI Knowledge Base ({total} entries)\n\n"

        for entry in entries[:20]:  # Show first 20
            doc_id = entry.get('id', 'unknown')
            doc_type = entry.get('type', 'documentation')
            preview = entry.get('content_preview', '')
            category = entry.get('category')
            tags = entry.get('tags', [])
            filename = entry.get('filename')

            # Build metadata display
            metadata_parts = []
            if category:
                metadata_parts.append(f"`[{category}]`")
            if tags:
                tags_display = " ".join(f"#{tag}" for tag in tags)
                metadata_parts.append(tags_display)

            metadata_str = " ".join(metadata_parts) if metadata_parts else ""

            content += f"**ID:** `{doc_id}` {metadata_str}\n"
            if filename:
                content += f"*File:* {filename}\n"
            content += f"*Type:* {doc_type}\n"
            content += f"```\n{preview}\n```\n\n"

        if total > 20:
            content += f"\n*Showing 20 of {total} entries*\n"

        content += """
**💡 Tips:**
- Use `/mem delete <id>` to remove an entry
- Use `/mem stats` to see overall statistics
"""

        await send_message(content)

    except Exception as e:
        await send_error(f"Error listing memory entries: {str(e)}")


async def handle_memdelete(doc_id: str | None = None):
    """Handle /memdelete command - delete a documentation entry."""
    if not doc_id or not doc_id.strip():
        await send_message(
            "**Usage:** `/mem delete <document_id>`\n\n"
            "Delete a specific documentation entry from the knowledge base.\n\n"
            "**Example:**\n"
            "- `/mem delete doc-12345`\n\n"
            "💡 Use `/mem list` to see all document IDs."
        )
        return

    try:
        doc_id = doc_id.strip()

        await send_message(f"🗑️ Deleting document: `{doc_id}`...")

        result = await call_api(f"/llm/memory/{doc_id}", method="DELETE")

        await send_message(
            f"""✅ **Document Deleted Successfully!**

**Document ID:** `{result.get('doc_id', doc_id)}`

The entry has been removed from the AI knowledge base.

💡 Use `/mem list` to see remaining documentation."""
        )

    except Exception as e:
        await send_error(f"Error deleting document: {str(e)}")
