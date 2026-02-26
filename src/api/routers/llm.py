"""
LLM Training Management API Router

Endpoints for managing Vanna 0.x ChromaDB training data and configuration.
Training data (DDL, documentation, query examples) is stored in ChromaDB
and used for RAG-based SQL generation.
"""

import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logging import get_logger
from src.services.llm_service import get_llm_service, initialize_llm_service
from src.utils.tag_parser import validate_file_extension, validate_file_size, validate_tags

logger = get_logger(__name__)

router = APIRouter(tags=["llm"])

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


class ModelInfoResponse(BaseModel):
    """Response for model info lookup."""

    model_name: str
    found: bool
    context_window: int | None = None
    max_output_tokens: int | None = None
    source: str | None = None


class ModelTestRequest(BaseModel):
    """Request for testing a model."""

    model: str = Field(..., description="Model name to test")
    mode: str = Field(
        default="sql",
        pattern="^(sql|insights|knowledge|summary)$",
        description="Mode: sql, insights, knowledge, or summary",
    )


class ModelTestResponse(BaseModel):
    """Response for model test."""

    success: bool
    model: str
    message: str
    context_window: int | None = None
    max_output_tokens: int | None = None


@router.get("/model-info/{model_name:path}", response_model=ModelInfoResponse)
async def get_model_info_endpoint(model_name: str) -> ModelInfoResponse:
    """
    Look up model info from the LiteLLM model registry.

    Returns context window and max output tokens for the given model.
    """
    from src.services.model_registry import get_context_window, get_max_output_tokens, get_model_info

    info = get_model_info(model_name)
    if info is None:
        return ModelInfoResponse(model_name=model_name, found=False)

    return ModelInfoResponse(
        model_name=model_name,
        found=True,
        context_window=get_context_window(model_name),
        max_output_tokens=get_max_output_tokens(model_name),
        source=info.get("source", "litellm"),
    )


@router.post("/model-test", response_model=ModelTestResponse)
async def test_model(request: ModelTestRequest) -> ModelTestResponse:
    """
    Test that a model is reachable by sending a minimal prompt.

    Returns success/failure plus model info from the registry.
    """
    import asyncio

    from src.services.model_registry import get_context_window, get_max_output_tokens

    model = request.model

    try:
        # Send a minimal prompt to validate the model works
        def _test():
            provider = settings.llm_provider

            if provider == "openai":
                from openai import OpenAI

                client = OpenAI(api_key=settings.openai_api_key)
                client.chat.completions.create(
                    model=model,
                    max_tokens=5,
                    messages=[{"role": "user", "content": "Say OK"}],
                )
            elif provider == "anthropic":
                from anthropic import Anthropic

                client = Anthropic(api_key=settings.anthropic_api_key)
                client.messages.create(
                    model=model,
                    max_tokens=5,
                    messages=[{"role": "user", "content": "Say OK"}],
                )
            elif provider == "azure_openai":
                from openai import OpenAI

                client = OpenAI(
                    base_url=settings.azure_openai_endpoint,
                    api_key=settings.azure_openai_api_key,
                )
                client.chat.completions.create(
                    model=model,
                    max_tokens=5,
                    messages=[{"role": "user", "content": "Say OK"}],
                )
            elif provider == "ollama":
                import ollama

                client = ollama.Client(host=settings.ollama_base_url)
                client.chat(model=model, messages=[{"role": "user", "content": "Say OK"}])
            else:
                raise ValueError(f"Unsupported provider: {provider}")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _test)

        return ModelTestResponse(
            success=True,
            model=model,
            message=f"Model '{model}' is reachable and working",
            context_window=get_context_window(model),
            max_output_tokens=get_max_output_tokens(model),
        )

    except Exception as e:
        logger.warning(f"Model test failed for {model}: {e}")
        return ModelTestResponse(
            success=False,
            model=model,
            message=f"Model test failed: {str(e)}",
            context_window=get_context_window(model),
            max_output_tokens=get_max_output_tokens(model),
        )


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
        return LLMHealthResponse(healthy=False, provider="UNKNOWN", model="unknown", status="error", error=str(e))


@router.post("/train", response_model=TrainingStatusResponse)
async def retrain_service() -> TrainingStatusResponse:
    """
    Force retrain the LLM service on schema and example queries.

    This will:
    1. Reload the database schema from data_mapping.json
    2. Reload query examples from datasets/snap/training/
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
            message="LLM service retrained successfully",
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
            total_size = sum(f.stat().st_size for f in chromadb_path.rglob("*") if f.is_file())
            size_mb = total_size / (1024 * 1024)  # Convert to MB

        return TrainingStatusResponse(
            enabled=True,  # Always enabled (required for Vanna)
            chromadb_path=str(chromadb_path),
            chromadb_exists=chromadb_exists,
            chromadb_size_mb=round(size_mb, 2),
            message="Initial training always enabled (required for Vanna to work)",
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
            chromadb_cleaned=False,
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

        # Clean ChromaDB training data
        if llm_service._initialized:
            try:
                from src.services.llm_providers import _get_vanna_instance

                vn = _get_vanna_instance()
                existing_data = vn.get_training_data()
                if not existing_data.empty:
                    ids_to_remove = existing_data["id"].tolist()
                    for training_id in ids_to_remove:
                        try:
                            vn.remove_training_data(id=training_id)
                            deleted_count += 1
                        except Exception:
                            pass
                    cleaned = True
                    logger.info(f"Cleaned {deleted_count} ChromaDB training entries")
            except Exception as e:
                logger.warning(f"Could not clean ChromaDB: {e}")

        return TrainingToggleResponse(
            success=True,
            enabled=False,
            message=f"Training disabled and {deleted_count} documents cleaned"
            if cleaned
            else "Training disabled (ChromaDB was already empty)",
            chromadb_cleaned=cleaned,
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

        # Clean ChromaDB training data via Vanna instance
        try:
            from src.services.llm_providers import _get_vanna_instance

            vn = _get_vanna_instance()
            existing_data = vn.get_training_data()
            if not existing_data.empty:
                ids_to_remove = existing_data["id"].tolist()
                for training_id in ids_to_remove:
                    try:
                        vn.remove_training_data(id=training_id)
                        deleted_count += 1
                    except Exception:
                        pass
                logger.info(f"Cleaned {deleted_count} ChromaDB training entries")

            return TrainingToggleResponse(
                success=True,
                enabled=True,
                message=f"Cleaned {deleted_count} training entries from ChromaDB",
                chromadb_cleaned=deleted_count > 0,
            )
        except Exception as e:
            logger.warning(f"Could not clean ChromaDB: {e}")
            raise

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
    Clear the Knowledge Base ChromaDB only.

    This resets user-uploaded documentation and insights data.
    It does NOT touch Vanna SQL training data (use /vanna/reset for that).
    """
    import asyncio

    from src.services.kb_chromadb import reset_kb

    try:
        loop = asyncio.get_running_loop()
        deleted_count = await loop.run_in_executor(None, reset_kb)

        return MemoryResetResponse(
            success=True,
            message=f"Knowledge Base reset. Deleted {deleted_count} document(s).",
            chromadb_size_mb=0.0,
            training_time_seconds=0.0,
            entries_trained=0,
        )

    except Exception as e:
        logger.error(f"Error resetting KB: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/add", response_model=MemoryAddResponse)
async def add_memory_documentation(
    files: list[UploadFile] = File(...),
    category: str | None = Form(None),
    tags: str | None = Form(None),
    user_id: str | None = Form(None),
    is_private: bool = Form(False),
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
    # Resolve anonymous email default
    if user_id is None:
        from datasets import get_active_dataset

        ds = get_active_dataset()
        user_id = ds.get_anonymous_email() if ds else "anonymous@app.com"

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
                file=file, category=category_name, tags=tags_list, user_id=user_id, is_private=is_private
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
            results=results,
        )

    except Exception as e:
        logger.error(f"Error in add_memory_documentation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _parse_tags_from_string(tags: str) -> list[str]:
    """Parse and validate tags from string input."""
    import re

    tags_clean = re.sub(r"[,\s]+", " ", tags).strip()
    raw_tags = [t.lstrip("#") for t in tags_clean.split() if t]
    return validate_tags(raw_tags)


def _clean_category(category: str | None) -> str:
    """Clean and validate category name."""
    if not category or not category.strip():
        return "general"
    return category.strip().lower()


async def _process_single_file_kb(
    file: UploadFile, category: str, tags: list[str], user_id: str, is_private: bool
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
        "visibility": "private" if is_private else "shared",
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
        text = content.decode("utf-8")

        if not text or not text.strip():
            file_result["error"] = "File is empty"
            return file_result

        # Add to KB ChromaDB (NOT Vanna)
        doc_id = add_document(
            text=text, filename=file.filename, category=category, tags=tags, user_id=user_id, is_private=is_private
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
        kb_path = Path(kb_stats.get("path", f"{settings.vanna_chromadb_path}/kb"))
        kb_exists = kb_path.exists()

        # Calculate size (run in thread pool to avoid blocking)
        size_mb = 0.0
        last_modified = None

        if kb_exists:
            import asyncio

            def get_dir_size():
                """Calculate directory size synchronously."""
                return sum(f.stat().st_size for f in kb_path.rglob("*") if f.is_file())

            def get_last_modified():
                """Get last modified time synchronously."""
                try:
                    latest_file = max(kb_path.rglob("*"), key=lambda f: f.stat().st_mtime if f.is_file() else 0)
                    if latest_file.is_file():
                        return latest_file.stat().st_mtime
                except Exception:
                    pass
                return None

            # Run blocking I/O in thread pool
            loop = asyncio.get_running_loop()
            total_size = await loop.run_in_executor(None, get_dir_size)
            size_mb = total_size / (1024 * 1024)

            timestamp = await loop.run_in_executor(None, get_last_modified)
            if timestamp:
                last_modified = datetime.fromtimestamp(timestamp).isoformat()

        # Include document count in training_stats for display
        total_documents = kb_stats.get("total_documents", 0)
        total_chunks = kb_stats.get("total_chunks", 0)
        training_stats = {
            "total_documents": total_documents,
            "total_chunks": total_chunks,
        }

        # Show 0 MB when KB is empty (ChromaDB keeps index files on disk even after reset)
        display_size_mb = 0.0 if total_documents == 0 else round(size_mb, 2)

        return MemoryStatsResponse(
            chromadb_path=str(kb_path),
            chromadb_exists=kb_exists,
            chromadb_size_mb=display_size_mb,
            last_modified=last_modified,
            training_stats=training_stats,
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
            metadata = doc.get("metadata", {})
            tags_str = metadata.get("tags", "")
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

            entries.append(
                DocumentEntry(
                    id=doc["id"],
                    type="documentation",
                    content_preview=doc["content_preview"],
                    category=metadata.get("category", "general"),
                    tags=tags,
                    filename=metadata.get("filename"),
                )
            )

        return MemoryListResponse(
            total_entries=len(entries), entries=entries, message=f"Showing {len(entries)} documents from Knowledge Base"
        )

    except Exception as e:
        logger.error(f"Error listing KB documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory/{doc_id}", response_model=MemoryDeleteResponse)
async def delete_memory_entry(doc_id: str):
    """
    Delete a document from the User Knowledge Base.

    Args:
        doc_id: Document ID to delete (from Knowledge Base panel or /mem list)

    Returns:
        Deletion status
    """
    try:
        from src.services.kb_chromadb import delete_document

        success = delete_document(doc_id)

        if success:
            return MemoryDeleteResponse(
                success=True, message=f"Document '{doc_id}' deleted from Knowledge Base", doc_id=doc_id
            )
        else:
            return MemoryDeleteResponse(
                success=False,
                message=f"Could not delete document '{doc_id}' - not found or error occurred",
                doc_id=doc_id,
            )

    except Exception as e:
        logger.error(f"Error deleting KB document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PROMPT MANAGEMENT ENDPOINTS
# =============================================================================


class PromptGetResponse(BaseModel):
    """Response for getting a prompt."""

    prompt_text: str
    is_custom: bool
    char_count: int
    prompt_type: str


class PromptSetRequest(BaseModel):
    """Request body for setting a prompt."""

    prompt_text: str = Field(..., min_length=20, max_length=5000)


class PromptSetResponse(BaseModel):
    """Response for setting a prompt."""

    success: bool
    message: str
    char_count: int


class PromptResetResponse(BaseModel):
    """Response for resetting a prompt."""

    success: bool
    message: str


def _get_user_id(request: Request) -> str:
    """Extract user ID from X-User-ID header or fall back to 'default'."""
    return request.headers.get("X-User-ID", "default")


@router.get("/prompt/{prompt_type}", response_model=PromptGetResponse)
async def get_prompt(prompt_type: str, request: Request) -> PromptGetResponse:
    """
    Get current prompt (custom or default) for a user.

    Args:
        prompt_type: 'sql' or 'kb'
    """
    if prompt_type not in ("sql", "kb", "summary"):
        raise HTTPException(status_code=400, detail=f"Invalid prompt_type: {prompt_type}. Use 'sql', 'kb', or 'summary'.")

    from src.database.prompt_manager import get_user_prompt, has_custom_prompt

    user_id = _get_user_id(request)
    try:
        prompt_text = get_user_prompt(user_id, prompt_type)
        is_custom = has_custom_prompt(user_id, prompt_type)
        return PromptGetResponse(
            prompt_text=prompt_text,
            is_custom=is_custom,
            char_count=len(prompt_text),
            prompt_type=prompt_type,
        )
    except Exception as e:
        logger.error(f"Error getting prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/prompt/{prompt_type}", response_model=PromptSetResponse)
async def set_prompt(prompt_type: str, body: PromptSetRequest, request: Request) -> PromptSetResponse:
    """
    Set or update a custom prompt for a user.

    Args:
        prompt_type: 'sql' or 'kb'
        body: JSON body with prompt_text (20-5000 chars)
    """
    if prompt_type not in ("sql", "kb", "summary"):
        raise HTTPException(status_code=400, detail=f"Invalid prompt_type: {prompt_type}. Use 'sql', 'kb', or 'summary'.")

    from src.database.prompt_manager import set_user_prompt

    user_id = _get_user_id(request)
    try:
        success = set_user_prompt(user_id, prompt_type, body.prompt_text)
        if success:
            prompt_name = {"sql": "SQL generation", "kb": "KB insight", "summary": "Results summary"}[prompt_type]
            return PromptSetResponse(
                success=True,
                message=f"{prompt_name} prompt updated successfully",
                char_count=len(body.prompt_text),
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to save prompt")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/prompt/{prompt_type}", response_model=PromptResetResponse)
async def reset_prompt(prompt_type: str, request: Request) -> PromptResetResponse:
    """
    Reset prompt to system default for a user.

    Args:
        prompt_type: 'sql' or 'kb'
    """
    if prompt_type not in ("sql", "kb", "summary"):
        raise HTTPException(status_code=400, detail=f"Invalid prompt_type: {prompt_type}. Use 'sql', 'kb', or 'summary'.")

    from src.database.prompt_manager import reset_user_prompt

    user_id = _get_user_id(request)
    try:
        success = reset_user_prompt(user_id, prompt_type)
        if success:
            prompt_name = {"sql": "SQL generation", "kb": "KB insight", "summary": "Results summary"}[prompt_type]
            return PromptResetResponse(
                success=True,
                message=f"{prompt_name} prompt reset to default",
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to reset prompt")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# VANNA SQL TRAINING MANAGEMENT ENDPOINTS
# =============================================================================


class VannaTrainingEntry(BaseModel):
    """Single entry from Vanna training data."""

    id: str
    training_data_type: str
    question: str | None = None
    content: str | None = None


class VannaStatsResponse(BaseModel):
    """Vanna ChromaDB per-collection statistics."""

    success: bool
    ddl_count: int = 0
    documentation_count: int = 0
    sql_count: int = 0
    total_count: int = 0


class VannaListResponse(BaseModel):
    """Vanna training data list grouped by type."""

    success: bool
    ddl: list[VannaTrainingEntry] = Field(default_factory=list)
    documentation: list[VannaTrainingEntry] = Field(default_factory=list)
    sql: list[VannaTrainingEntry] = Field(default_factory=list)
    total_count: int = 0


class VannaAddResponse(BaseModel):
    """Response from adding training data to Vanna."""

    success: bool
    message: str
    files_processed: int = 0
    files_failed: int = 0
    entries_added: int = 0
    results: list[dict] = Field(default_factory=list)


class VannaDeleteResponse(BaseModel):
    """Response from deleting a single Vanna training entry."""

    success: bool
    message: str
    entry_id: str


class VannaResetRequest(BaseModel):
    """Request body for Vanna reset."""

    reload_training_data: bool = True  # Whether to reload docs + examples from training folder


class VannaResetResponse(BaseModel):
    """Response from Vanna reset operation."""

    success: bool
    message: str
    reload_training_data: bool = True
    training_time_seconds: float = 0.0
    counts: dict = Field(default_factory=dict)


def _get_vanna_training_data():
    """Get Vanna training data DataFrame (sync helper)."""
    from src.services.llm_providers import _get_vanna_instance

    vn = _get_vanna_instance()
    return vn.get_training_data()


@router.get("/vanna/stats", response_model=VannaStatsResponse)
async def get_vanna_stats():
    """Get per-collection counts from Vanna's ChromaDB."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, _get_vanna_training_data)

        if df.empty:
            return VannaStatsResponse(success=True)

        ddl_count = int((df["training_data_type"] == "ddl").sum())
        doc_count = int((df["training_data_type"] == "documentation").sum())
        sql_count = int((df["training_data_type"] == "sql").sum())

        return VannaStatsResponse(
            success=True,
            ddl_count=ddl_count,
            documentation_count=doc_count,
            sql_count=sql_count,
            total_count=len(df),
        )

    except Exception as e:
        logger.error(f"Error getting Vanna stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vanna/list", response_model=VannaListResponse)
async def list_vanna_training_data():
    """List Vanna training data grouped by type (first 20 per type)."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, _get_vanna_training_data)

        if df.empty:
            return VannaListResponse(success=True)

        result = {"ddl": [], "documentation": [], "sql": []}

        for dtype in ["ddl", "documentation", "sql"]:
            subset = df[df["training_data_type"] == dtype].head(20)
            for _, row in subset.iterrows():
                content = row.get("content", "")
                # Truncate long content for display
                preview = content[:200] + "..." if content and len(content) > 200 else content
                entry = VannaTrainingEntry(
                    id=row["id"],
                    training_data_type=dtype,
                    question=row.get("question") if dtype == "sql" else None,
                    content=preview,
                )
                result[dtype].append(entry)

        return VannaListResponse(
            success=True,
            ddl=result["ddl"],
            documentation=result["documentation"],
            sql=result["sql"],
            total_count=len(df),
        )

    except Exception as e:
        logger.error(f"Error listing Vanna training data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/vanna/{entry_id}", response_model=VannaDeleteResponse)
async def delete_vanna_entry(entry_id: str):
    """
    Delete a single training entry from Vanna's ChromaDB.

    Args:
        entry_id: The training data ID to delete (from /vanna/list)

    Returns:
        Deletion status
    """
    import asyncio

    def _do_delete():
        from src.services.llm_providers import _get_vanna_instance

        vn = _get_vanna_instance()
        vn.remove_training_data(id=entry_id)

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _do_delete)

        return VannaDeleteResponse(
            success=True,
            message=f"Training entry '{entry_id}' deleted from Vanna",
            entry_id=entry_id,
        )

    except Exception as e:
        logger.error(f"Error deleting Vanna entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vanna/add", response_model=VannaAddResponse)
async def add_vanna_training_data(
    files: list[UploadFile] = File(...),
):
    """
    Add training data to Vanna's ChromaDB.

    - .md/.txt files → vn.train(documentation=content)
    - .json files → parse {"example_queries": [{question, sql}...]}, train each pair
    """
    import asyncio
    import json

    results = []
    files_processed = 0
    files_failed = 0
    entries_added = 0

    for file in files:
        file_result = {"filename": file.filename, "success": False, "entries": 0, "error": None}

        try:
            content = await file.read()
            text = content.decode("utf-8")

            if not text.strip():
                file_result["error"] = "File is empty"
                files_failed += 1
                results.append(file_result)
                continue

            if file.filename.endswith(".json"):
                # Parse as question-SQL pairs
                data = json.loads(text)
                examples = data.get("example_queries", [])
                if not examples:
                    file_result["error"] = "No 'example_queries' key found in JSON"
                    files_failed += 1
                    results.append(file_result)
                    continue

                def _train_json_examples(ex_list):
                    from src.services.llm_providers import _get_vanna_instance

                    vn = _get_vanna_instance()
                    count = 0
                    for ex in ex_list:
                        q = ex.get("question", "")
                        s = ex.get("sql", "")
                        explanation = ex.get("explanation", "")
                        if q and s:
                            train_q = f"{q} ({explanation})" if explanation else q
                            vn.train(question=train_q, sql=s)
                            count += 1
                    return count

                loop = asyncio.get_running_loop()
                count = await loop.run_in_executor(None, _train_json_examples, examples)
                file_result["success"] = True
                file_result["entries"] = count
                entries_added += count
                files_processed += 1

            elif file.filename.endswith((".md", ".txt")):
                # Train as documentation — chunk large docs for better retrieval
                def _train_doc_chunked(doc_text, fname):
                    from src.services.kb_chromadb import _chunk_text
                    from src.services.llm_providers import _get_vanna_instance

                    vn = _get_vanna_instance()
                    chunks = _chunk_text(doc_text, filename=fname)
                    for chunk in chunks:
                        vn.train(documentation=chunk)
                    return len(chunks)

                loop = asyncio.get_running_loop()
                count = await loop.run_in_executor(None, _train_doc_chunked, text, file.filename)
                file_result["success"] = True
                file_result["entries"] = count
                entries_added += count
                files_processed += 1

            else:
                file_result["error"] = "Unsupported file type. Use .md, .txt, or .json"
                files_failed += 1

        except json.JSONDecodeError as e:
            file_result["error"] = f"Invalid JSON: {e}"
            files_failed += 1
        except Exception as e:
            file_result["error"] = str(e)
            files_failed += 1

        results.append(file_result)

    message = f"Processed {files_processed} file(s), added {entries_added} training entries"
    if files_failed:
        message += f", {files_failed} file(s) failed"

    return VannaAddResponse(
        success=files_processed > 0,
        message=message,
        files_processed=files_processed,
        files_failed=files_failed,
        entries_added=entries_added,
        results=results,
    )


@router.post("/vanna/reset", response_model=VannaResetResponse)
async def reset_vanna_training(request: VannaResetRequest):
    """
    Reset Vanna's ChromaDB and retrain.

    Clears all training data and retrains DDL from the database schema.
    If reload_training_data is True, also reloads documentation and query
    examples from the training data folder (datasets/snap/training/).
    """
    import asyncio

    reload = request.reload_training_data

    def _do_reset():
        from src.services.llm_providers import train_vanna

        return train_vanna(force_retrain=True, reload_training_data=reload)

    try:
        loop = asyncio.get_running_loop()
        start_time = time.time()
        counts = await loop.run_in_executor(None, _do_reset)
        training_time = time.time() - start_time

        total = sum(counts.values())
        label = "DDL + training data" if reload else "DDL only"

        return VannaResetResponse(
            success=True,
            message=f"Vanna reset complete ({label}). Trained {total} entries in {training_time:.1f}s.",
            reload_training_data=reload,
            training_time_seconds=round(training_time, 2),
            counts=counts,
        )

    except Exception as e:
        logger.error(f"Error resetting Vanna: {e}")
        raise HTTPException(status_code=500, detail=str(e))
