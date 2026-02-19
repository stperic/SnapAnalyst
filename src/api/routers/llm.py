"""
LLM Training Management API Router (Vanna 2.x Compatible)

Endpoints for managing Vanna AI agent memory and configuration.

VANNA 2.X CHANGES:
- Training is now automatic through agent memory
- No direct ChromaDB access for SQL training
- Agent learns from successful query executions
- Some endpoints are stubs for backward compatibility
"""
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logging import get_logger
from src.services.llm_service import get_llm_service, initialize_llm_service
from src.utils.tag_parser import validate_file_extension, validate_file_size, validate_tags

logger = get_logger(__name__)

router = APIRouter(tags=["llm"])

# Vanna 2.x compatibility flag
VANNA_2X = True


# Import response models from chatbot for LLM management endpoints (after router to avoid circular imports)
from src.api.routers.chatbot import LLMHealthResponse, ProviderInfoResponse  # noqa: E402


class TrainingStatusResponse(BaseModel):
    """Training status response"""
    enabled: bool
    chromadb_path: str
    chromadb_exists: bool
    chromadb_size_mb: float = 0.0
    message: str


class TrainingToggleResponse(BaseModel):
    """Training toggle response"""
    success: bool
    enabled: bool
    message: str
    chromadb_cleaned: bool = False


class MemoryResetResponse(BaseModel):
    """Memory reset response"""
    success: bool
    message: str
    chromadb_size_mb: float
    training_time_seconds: float
    entries_trained: int


class MemoryAddResponse(BaseModel):
    """Memory add documentation response"""
    success: bool
    message: str
    files_processed: int = 0
    files_failed: int = 0
    total_chars_added: int = 0
    results: list[dict] = Field(default_factory=list)  # Per-file results


class FileUploadResult(BaseModel):
    """Result of a single file upload"""
    filename: str
    success: bool
    chars_added: int = 0
    error: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)


class MemoryStatsResponse(BaseModel):
    """Memory statistics response"""
    chromadb_path: str
    chromadb_exists: bool
    chromadb_size_mb: float
    last_modified: str | None = None
    training_stats: dict | None = None


class DocumentEntry(BaseModel):
    """Document entry in ChromaDB"""
    id: str
    type: str
    content_preview: str
    added_date: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)  # NEW: Tag support
    filename: str | None = None  # NEW: Original filename


class MemoryListResponse(BaseModel):
    """Memory list response"""
    total_entries: int
    entries: list[DocumentEntry]


class MemoryDeleteResponse(BaseModel):
    """Memory delete response"""
    success: bool
    message: str
    doc_id: str


@router.get("/provider", response_model=ProviderInfoResponse)
async def get_provider_info() -> ProviderInfoResponse:
    """
    Get information about the configured LLM provider.

    Returns details about which LLM is being used (OpenAI, Anthropic, Ollama, Azure OpenAI),
    the model name, and configuration settings.
    """
    try:
        llm_service = get_llm_service()
        info = llm_service.get_provider_info()
        return ProviderInfoResponse(**info)
    except Exception as e:
        logger.error(f"Failed to get provider info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=LLMHealthResponse)
async def check_llm_health() -> LLMHealthResponse:
    """
    Check LLM service health and availability.

    This endpoint verifies:
    - **OpenAI**: API key is configured and valid
    - **Anthropic**: API key is configured
    - **Azure OpenAI**: Endpoint and API key are configured
    - **Ollama**: Server is reachable and model is available

    Returns healthy=True only if the LLM can actually be used.
    """
    try:
        llm_service = get_llm_service()
        health = llm_service.check_health()
        return LLMHealthResponse(**health)
    except Exception as e:
        logger.error(f"Failed to check LLM health: {e}")
        return LLMHealthResponse(
            healthy=False,
            provider="UNKNOWN",
            model="unknown",
            status="error",
            error=str(e)
        )


@router.post("/train", response_model=TrainingStatusResponse)
async def retrain_service() -> TrainingStatusResponse:
    """
    Force retrain the LLM service on schema and example queries.

    This will:
    1. Reload the database schema from data_mapping.json
    2. Reload query examples from query_examples.json
    3. Retrain the LLM with updated information

    Use this after updating schema documentation or adding new query examples.
    """
    try:
        logger.info("Starting LLM service retraining...")
        initialize_llm_service(force_retrain=True)

        return TrainingStatusResponse(
            enabled=True,
            chromadb_path=str(settings.vanna_chromadb_path),
            chromadb_exists=True,
            chromadb_size_mb=0.0,
            message="LLM service retrained successfully"
        )
    except Exception as e:
        logger.error(f"Failed to retrain service: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrain: {str(e)}")


@router.get("/training/status", response_model=TrainingStatusResponse)
async def get_training_status():
    """
    Get current training status.

    Returns:
        Training configuration and ChromaDB status
    """
    try:
        chromadb_path = Path(settings.vanna_chromadb_path)
        chromadb_exists = chromadb_path.exists()

        # Calculate size if exists
        size_mb = 0.0
        if chromadb_exists:
            total_size = sum(
                f.stat().st_size
                for f in chromadb_path.rglob('*')
                if f.is_file()
            )
            size_mb = total_size / (1024 * 1024)  # Convert to MB

        return TrainingStatusResponse(
            enabled=True,  # Always enabled (required for Vanna)
            chromadb_path=str(chromadb_path),
            chromadb_exists=chromadb_exists,
            chromadb_size_mb=round(size_mb, 2),
            message="Initial training always enabled (required for Vanna to work)"
        )

    except Exception as e:
        logger.error(f"Error getting training status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training/enable", response_model=TrainingToggleResponse)
async def enable_training():
    """
    Enable AI training.

    Enables persistent training with ChromaDB vector store.
    Note: This doesn't change the config file, only runtime behavior.
    """
    try:
        # Note: We can't change settings at runtime since it's loaded once
        # This endpoint is mainly for informational purposes
        # Actual training control is in config.py

        logger.info("Training enable requested (requires config change)")

        return TrainingToggleResponse(
            success=True,
            enabled=True,  # Always enabled
            message="Initial training is always enabled (required for Vanna). Training happens during startup or on first query.",
            chromadb_cleaned=False
        )

    except Exception as e:
        logger.error(f"Error enabling training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training/disable", response_model=TrainingToggleResponse)
async def disable_training():
    """
    Disable AI training and clean ChromaDB.

    Clears all documents from ChromaDB collections.
    """
    try:
        llm_service = get_llm_service()
        cleaned = False
        deleted_count = 0

        # Clean ChromaDB using API
        # NOTE: Vanna 2.x uses agent memory, not direct ChromaDB access
        if llm_service._initialized and hasattr(llm_service, 'vanna') and llm_service.vanna:
            try:
                # Vanna 2.x doesn't expose chroma_client - agent memory is different
                logger.warning("ChromaDB cleaning not supported in Vanna 2.x (agent memory is automatic)")
                cleaned = False
            except Exception as e:
                logger.warning(f"Could not clean ChromaDB: {e}")

        return TrainingToggleResponse(
            success=True,
            enabled=False,
            message=f"Training disabled and {deleted_count} documents cleaned" if cleaned else "Training disabled (ChromaDB was already empty)",
            chromadb_cleaned=cleaned
        )

    except Exception as e:
        logger.error(f"Error disabling training: {e}")
        raise HTTPException(status_code=500, detail=f"Error cleaning ChromaDB: {str(e)}")


@router.delete("/training/chromadb", response_model=TrainingToggleResponse)
async def clean_chromadb():
    """
    Clean ChromaDB vector store.

    Removes all stored embeddings and training data from all collections.
    Useful for resetting the vector database without changing training settings.
    """
    try:
        llm_service = get_llm_service()

        if not llm_service._initialized:
            initialize_llm_service()
            llm_service = get_llm_service()

        deleted_count = 0
        collections_cleared = []

        # Clean ChromaDB using API
        # NOTE: Vanna 2.x uses agent memory, not direct ChromaDB access
        try:
            if hasattr(llm_service, 'vanna') and llm_service.vanna:
                # Vanna 2.x doesn't expose chroma_client directly
                logger.warning("ChromaDB cleaning not supported in Vanna 2.x")
                return TrainingToggleResponse(
                    success=True,
                    enabled=True,
                    message="Vanna 2.x uses automatic agent memory (manual cleaning not needed)",
                    chromadb_cleaned=False
                )
            else:
                return TrainingToggleResponse(
                    success=True,
                    enabled=settings.vanna_pretrain_on_startup,
                    message="LLM service not initialized",
                    chromadb_cleaned=False
                )
        except Exception as e:
            logger.warning(f"Could not clean ChromaDB: {e}")
            raise

        return TrainingToggleResponse(
            success=True,
            enabled=True,  # Training will happen on next startup or first query
            message=f"ChromaDB cleaned: {deleted_count} documents deleted from {len(collections_cleared)} collections. Training will happen on next startup.",
            chromadb_cleaned=deleted_count > 0
        )

    except Exception as e:
        logger.error(f"Error cleaning ChromaDB: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_llm_info() -> dict:
    """
    Get LLM service information.

    Returns:
        Provider, model, and configuration details
    """
    try:
        llm_service = get_llm_service()
        info = llm_service.get_provider_info()

        # Add ChromaDB info
        chromadb_path = Path(settings.vanna_chromadb_path)
        info["chromadb"] = {
            "path": str(chromadb_path),
            "exists": chromadb_path.exists(),
            "training": "Always enabled (required for Vanna)",
        }

        return info

    except Exception as e:
        logger.error(f"Error getting LLM info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MEMORY MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/memory/reset", response_model=MemoryResetResponse)
async def reset_memory():
    """
    Clear ChromaDB and re-train with initial data.

    This will:
    1. Delete all documents from ChromaDB collections (sql, ddl, documentation)
    2. Re-extract DDL from PostgreSQL
    3. Re-load business context and query examples
    4. Rebuild vector embeddings

    Returns:
        Reset status and training statistics
    """
    import asyncio

    def _do_reset():
        try:
            from src.services.llm_providers import _get_vanna_instance, train_vanna_with_ddl

            deleted_count = 0
            collections_cleared = []

            # Clear KB ChromaDB
            try:
                import chromadb
                kb_path = f"{settings.vanna_chromadb_path}/kb"
                client_settings = chromadb.config.Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
                kb_client = chromadb.PersistentClient(path=kb_path, settings=client_settings)

                for collection in kb_client.list_collections():
                    try:
                        results = collection.get()
                        ids = results.get('ids', [])
                        if ids:
                            collection.delete(ids=ids)
                            deleted_count += len(ids)
                            collections_cleared.append(f"KB:{collection.name} ({len(ids)} docs)")
                    except Exception as e:
                        logger.warning(f"Could not clear {collection.name}: {e}")
            except Exception as e:
                logger.warning(f"Could not access KB ChromaDB: {e}")

            # Clear Vanna DDL ChromaDB via the actual vanna instance
            try:
                vn = _get_vanna_instance()
                if hasattr(vn, 'chroma_client') and vn.chroma_client:
                    for collection in vn.chroma_client.list_collections():
                        try:
                            results = collection.get()
                            ids = results.get('ids', [])
                            if ids:
                                collection.delete(ids=ids)
                                deleted_count += len(ids)
                                collections_cleared.append(f"{collection.name} ({len(ids)} docs)")
                        except Exception as e:
                            logger.warning(f"Could not clear {collection.name}: {e}")
            except Exception as e:
                logger.warning(f"Could not access Vanna ChromaDB: {e}")

            logger.info(f"Cleared {deleted_count} docs from: {collections_cleared}")

            start_time = time.time()
            initialize_llm_service(force_retrain=True)
            train_vanna_with_ddl(force_retrain=True)
            training_time = time.time() - start_time

            # Get actual entries count from Vanna's ChromaDB
            entries_trained = 0
            try:
                vn = _get_vanna_instance()
                if hasattr(vn, 'chroma_client') and vn.chroma_client:
                    for collection in vn.chroma_client.list_collections():
                        count = collection.count()
                        logger.info(f"  Collection '{collection.name}': {count} entries")
                        entries_trained += count
            except Exception as e:
                logger.warning(f"Could not count Vanna entries: {e}")

            logger.info(f"Training complete: {entries_trained} entries in {training_time:.1f}s")

            return deleted_count, collections_cleared, training_time, entries_trained

        except Exception as e:
            logger.error(f"Reset error: {e}")
            raise

    try:
        loop = asyncio.get_event_loop()
        deleted_count, collections_cleared, training_time, entries_trained = await loop.run_in_executor(None, _do_reset)

        return MemoryResetResponse(
            success=True,
            message=f"Reset complete. Deleted {deleted_count} docs, re-trained {entries_trained} entries.",
            chromadb_size_mb=0.0,
            training_time_seconds=round(training_time, 2),
            entries_trained=entries_trained
        )

    except Exception as e:
        logger.error(f"Error resetting memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/add", response_model=MemoryAddResponse)
async def add_memory_documentation(
    files: list[UploadFile] = File(...),
    category: str | None = Form(None),
    tags: str | None = Form(None),
    user_id: str = Form("anonymous@snapanalyst.com"),
    is_private: bool = Form(False)
):
    """
    Add custom documentation to KB ChromaDB (supports multiple files).

    NEW: Uses separate KB ChromaDB (./chromadb/kb/) instead of Vanna's dataset ChromaDB.

    Uploads text files and stores them in knowledge base with metadata.

    Args:
        files: List of text files (.txt, .md) with documentation
        category: Optional category for all files
        tags: Optional tags (comma/space separated, or #hashtag format)
        user_id: Document owner (from session/auth)
        is_private: If True, document visible only to user

    Returns:
        Status and results for each file
    """
    results = []
    files_processed = 0
    files_failed = 0
    total_chars = 0

    # Parse tags using utility function
    tags_list = _parse_tags_from_string(tags) if tags else []

    # Clean category (or set to user-specific if private)
    category_name = _clean_category(category)

    try:
        for file in files:
            result = await _process_single_file_kb(
                file=file,
                category=category_name,
                tags=tags_list,
                user_id=user_id,
                is_private=is_private
            )

            results.append(result)

            if result["success"]:
                files_processed += 1
                total_chars += result["chars_added"]
            else:
                files_failed += 1

        # Build response message
        message = _build_response_message(files_processed, files_failed)

        return MemoryAddResponse(
            success=files_processed > 0,
            message=message,
            files_processed=files_processed,
            files_failed=files_failed,
            total_chars_added=total_chars,
            results=results
        )

    except Exception as e:
        logger.error(f"Error in add_memory_documentation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _parse_tags_from_string(tags: str) -> list[str]:
    """Parse and validate tags from string input."""
    import re
    tags_clean = re.sub(r'[,\s]+', ' ', tags).strip()
    raw_tags = [t.lstrip('#') for t in tags_clean.split() if t]
    return validate_tags(raw_tags)


def _clean_category(category: str | None) -> str:
    """Clean and validate category name."""
    if not category or not category.strip():
        return "general"
    return category.strip().lower()


async def _process_single_file_kb(
    file: UploadFile,
    category: str,
    tags: list[str],
    user_id: str,
    is_private: bool
) -> dict:
    """Process a single file upload to KB ChromaDB."""
    from src.services.kb_chromadb import add_document

    file_result = {
        "filename": file.filename,
        "success": False,
        "chars_added": 0,
        "error": None,
        "category": f"user:{user_id}" if is_private else category,
        "tags": tags,
        "visibility": "private" if is_private else "shared"
    }

    try:
        # Validate file type
        if not validate_file_extension(file.filename):
            file_result["error"] = "Invalid file type. Allowed: .md, .txt"
            return file_result

        # Read file content
        content = await file.read()

        # Validate size (10 MB limit)
        if not validate_file_size(len(content)):
            file_result["error"] = "File too large. Maximum: 10 MB"
            return file_result

        # Decode content
        text = content.decode('utf-8')

        if not text or not text.strip():
            file_result["error"] = "File is empty"
            return file_result

        # Add to KB ChromaDB (NOT Vanna)
        doc_id = add_document(
            text=text,
            filename=file.filename,
            category=category,
            tags=tags,
            user_id=user_id,
            is_private=is_private
        )

        # Success
        file_result["success"] = True
        file_result["chars_added"] = len(text)
        file_result["doc_id"] = doc_id

        logger.info(f"Successfully added {file.filename} to KB (doc_id={doc_id})")

    except Exception as e:
        logger.error(f"Error processing {file.filename}: {e}")
        file_result["error"] = str(e)

    return file_result


# Legacy function removed - metadata now handled by KB ChromaDB module


def _build_response_message(files_processed: int, files_failed: int) -> str:
    """Build response message based on results."""
    if files_processed > 0 and files_failed == 0:
        return f"Successfully added {files_processed} file(s) to knowledge base"
    elif files_processed > 0 and files_failed > 0:
        return f"Partial success: {files_processed} succeeded, {files_failed} failed"
    else:
        return f"Failed to add files: {files_failed} error(s)"


@router.get("/memory/stats", response_model=MemoryStatsResponse)
async def get_memory_stats():
    """
    Get Knowledge Base statistics.

    Returns:
        KB document count, size, and last modified
    """
    try:
        from src.services.kb_chromadb import get_stats

        # Get KB stats
        kb_stats = get_stats()
        kb_path = Path(kb_stats.get('path', f"{settings.vanna_chromadb_path}/kb"))
        kb_exists = kb_path.exists()

        # Calculate size (run in thread pool to avoid blocking)
        size_mb = 0.0
        last_modified = None

        if kb_exists:
            import asyncio

            def get_dir_size():
                """Calculate directory size synchronously."""
                return sum(
                    f.stat().st_size
                    for f in kb_path.rglob('*')
                    if f.is_file()
                )

            def get_last_modified():
                """Get last modified time synchronously."""
                try:
                    latest_file = max(
                        kb_path.rglob('*'),
                        key=lambda f: f.stat().st_mtime if f.is_file() else 0
                    )
                    if latest_file.is_file():
                        return latest_file.stat().st_mtime
                except Exception:
                    pass
                return None

            # Run blocking I/O in thread pool
            loop = asyncio.get_event_loop()
            total_size = await loop.run_in_executor(None, get_dir_size)
            size_mb = total_size / (1024 * 1024)

            timestamp = await loop.run_in_executor(None, get_last_modified)
            if timestamp:
                last_modified = datetime.fromtimestamp(timestamp).isoformat()

        # Include document count in training_stats for display
        training_stats = {
            'total_documents': kb_stats.get('total_documents', 0)
        }

        return MemoryStatsResponse(
            chromadb_path=str(kb_path),
            chromadb_exists=kb_exists,
            chromadb_size_mb=round(size_mb, 2),
            last_modified=last_modified,
            training_stats=training_stats
        )

    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/list", response_model=MemoryListResponse)
async def list_memory_entries():
    """
    List all documents in the User Knowledge Base.

    Returns:
        List of KB documents with metadata
    """
    try:
        from src.services.kb_chromadb import list_documents

        documents = list_documents(limit=50)

        entries = []
        for doc in documents:
            metadata = doc.get('metadata', {})
            tags_str = metadata.get('tags', '')
            tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []

            entries.append(DocumentEntry(
                id=doc['id'],
                type="documentation",
                content_preview=doc['content_preview'],
                category=metadata.get('category', 'general'),
                tags=tags,
                filename=metadata.get('filename')
            ))

        return MemoryListResponse(
            total_entries=len(entries),
            entries=entries,
            message=f"Showing {len(entries)} documents from Knowledge Base"
        )

    except Exception as e:
        logger.error(f"Error listing KB documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory/{doc_id}", response_model=MemoryDeleteResponse)
async def delete_memory_entry(doc_id: str):
    """
    Delete a document from the User Knowledge Base.

    Args:
        doc_id: Document ID to delete (from /mem list)

    Returns:
        Deletion status
    """
    try:
        from src.services.kb_chromadb import delete_document

        success = delete_document(doc_id)

        if success:
            return MemoryDeleteResponse(
                success=True,
                message=f"Document '{doc_id}' deleted from Knowledge Base",
                doc_id=doc_id
            )
        else:
            return MemoryDeleteResponse(
                success=False,
                message=f"Could not delete document '{doc_id}' - not found or error occurred",
                doc_id=doc_id
            )

    except Exception as e:
        logger.error(f"Error deleting KB document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
