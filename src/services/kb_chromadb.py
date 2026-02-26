"""
Knowledge Base ChromaDB Module

Simple, clean interface for KB ChromaDB operations.
Path: ./chromadb/kb/ | Collection: "kb"
"""

from __future__ import annotations

import os
import threading
import uuid
from collections import defaultdict
from datetime import UTC, datetime

# Configure ONNX Runtime before any ChromaDB imports
# CRITICAL: Explicitly set thread count to prevent CPU affinity errors in LXC containers
# When thread count is explicit, ONNX Runtime skips automatic CPU affinity (which fails in LXC)
# See: https://github.com/chroma-core/chroma/issues/1420
if not os.environ.get("OMP_NUM_THREADS") or os.environ.get("OMP_NUM_THREADS") == "0":
    os.environ["OMP_NUM_THREADS"] = "4"

import chromadb

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_kb_client = None
_kb_lock = threading.Lock()


def get_kb_collection():
    """Get or create KB collection."""
    global _kb_client

    if _kb_client is None:
        with _kb_lock:
            if _kb_client is None:
                kb_path = f"{settings.vanna_chromadb_path}/kb"
                # Create ChromaDB client with telemetry explicitly disabled
                client_settings = chromadb.config.Settings(anonymized_telemetry=False, allow_reset=True)
                _kb_client = chromadb.PersistentClient(path=kb_path, settings=client_settings)
                logger.info(f"Initialized KB ChromaDB at {kb_path}")

    collection = _kb_client.get_or_create_collection(
        name="user_kb",
        metadata={
            "description": "User knowledge base",
            # all-MiniLM-L6-v2 was trained with cosine similarity and outputs
            # L2-normalized unit vectors. Cosine is the correct distance metric.
            "hnsw:space": "cosine",
        },
    )

    # Warn if persisted collection is still using L2 (pre-migration)
    actual_space = collection.metadata.get("hnsw:space", "l2")
    if actual_space != "cosine":
        logger.warning(
            "KB collection using '%s' distance (not cosine). Reset via Settings > Knowledge and re-upload documents to migrate.",
            actual_space,
        )

    return collection


def _get_text_splitter(chunk_size: int = 500, chunk_overlap: int = 50):
    """Get a RecursiveCharacterTextSplitter with the given parameters."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )


def _get_markdown_splitter(chunk_size: int = 500, chunk_overlap: int = 50):
    """Get a MarkdownTextSplitter for .md files."""
    from langchain_text_splitters import MarkdownTextSplitter

    return MarkdownTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


# Module-level singletons for default parameters
_default_text_splitter = None
_default_md_splitter = None


def _chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50, filename: str = "") -> list[str]:
    """
    Split text into overlapping chunks for ChromaDB storage.

    Uses langchain RecursiveCharacterTextSplitter which tries separators in
    priority order (paragraph -> line -> sentence -> word -> character) until
    chunks fit within chunk_size. For .md files, uses MarkdownTextSplitter
    which additionally respects headings, code fences, and horizontal rules.

    chunk_overlap characters are repeated between consecutive chunks for
    retrieval continuity.
    """
    if len(text) <= chunk_size:
        return [text]

    global _default_text_splitter, _default_md_splitter

    is_markdown = filename.endswith(".md")
    use_defaults = chunk_size == 500 and chunk_overlap == 50

    if use_defaults:
        if is_markdown:
            if _default_md_splitter is None:
                _default_md_splitter = _get_markdown_splitter()
            splitter = _default_md_splitter
        else:
            if _default_text_splitter is None:
                _default_text_splitter = _get_text_splitter()
            splitter = _default_text_splitter
    else:
        if is_markdown:
            splitter = _get_markdown_splitter(chunk_size, chunk_overlap)
        else:
            splitter = _get_text_splitter(chunk_size, chunk_overlap)

    return splitter.split_text(text)


def _get_anonymous_email() -> str:
    """Get anonymous email from active dataset config."""
    from datasets import get_active_dataset

    ds = get_active_dataset()
    return ds.get_anonymous_email() if ds else "anonymous@app.com"


def add_document(
    text: str,
    filename: str,
    category: str = "general",
    tags: list[str] | None = None,
    user_id: str | None = None,
    is_private: bool = False,
) -> str:
    """
    Add document to KB with automatic chunking.

    Returns: document ID (parent_id for chunked documents)
    """
    if user_id is None:
        user_id = _get_anonymous_email()
    collection = get_kb_collection()

    # Set category for private docs
    if is_private:
        category = f"user:{user_id}"

    # Delete existing entries for this filename (handles both single and chunked docs)
    existing = collection.get(where={"filename": filename})
    if existing and existing["ids"]:
        collection.delete(ids=existing["ids"])
        logger.info(f"Removed {len(existing['ids'])} existing entries for {filename}")

    # Chunk the text (markdown-aware for .md files)
    chunks = _chunk_text(text, filename=filename)
    parent_id = f"kb_{uuid.uuid4().hex}"
    now = datetime.now(UTC).isoformat()

    if len(chunks) == 1:
        # Single chunk — simple entry, no chunk metadata
        metadata = {
            "category": category,
            "tags": ",".join(tags) if tags else "",
            "filename": filename,
            "user_id": user_id,
            "visibility": "private" if is_private else "shared",
            "char_count": len(text),
            "created_at": now,
        }
        collection.add(ids=[parent_id], documents=[text], metadatas=[metadata])
        logger.info(f"Added to KB: {filename} ({category}, {metadata['visibility']})")
    else:
        # Multi-chunk — store each chunk with parent linkage
        ids = []
        documents = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{parent_id}_chunk{i}"
            metadata = {
                "category": category,
                "tags": ",".join(tags) if tags else "",
                "filename": filename,
                "user_id": user_id,
                "visibility": "private" if is_private else "shared",
                "char_count": len(chunk),
                "created_at": now,
                "parent_id": parent_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(metadata)

        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f"Added to KB: {filename} as {len(chunks)} chunks ({category})")

    return parent_id


# Cosine distances above this threshold are discarded as noise.
# For all-MiniLM-L6-v2: 0 = identical, ~0.3 = strong match, ~0.6 = weak, >0.6 = noise.
_KB_DISTANCE_THRESHOLD = 0.60


def query_documents(
    question: str,
    user_id: str | None = None,
    tags: list[str] | None = None,
    category: str | None = None,
    user_scope: str = "all",
    n_results: int = 10,
    distance_threshold: float = _KB_DISTANCE_THRESHOLD,
) -> list[dict]:
    """
    Query KB with filtering, relevance threshold, and per-document deduplication.

    Fetches extra candidates, filters by distance threshold, deduplicates to
    the best chunk per source document, then returns up to n_results.

    Relevance: 1.0 - (cosine_distance / 2.0), mapping [0, 2] -> [1.0, 0.0].

    Returns: List of {document, metadata, relevance, source_display}
    """
    if user_id is None:
        user_id = _get_anonymous_email()
    collection = get_kb_collection()
    where_filter = _build_where_filter(user_id, tags, category, user_scope)

    # Over-fetch to allow for threshold filtering and chunk deduplication
    fetch_n = n_results * 3

    try:
        results = collection.query(
            query_texts=[question],
            n_results=fetch_n,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # Collect raw hits
        raw = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
            strict=False,
        ):
            raw.append(
                {
                    "document": doc,
                    "metadata": meta,
                    "distance": dist,
                    "relevance": 1.0 - (dist / 2.0),
                    "source_display": _format_source(meta),
                }
            )

        # 1. Filter by relevance threshold
        filtered = [r for r in raw if r["distance"] <= distance_threshold]
        if not filtered:
            logger.debug(f"KB query: all {len(raw)} results exceeded threshold {distance_threshold}")
            return []

        # 2. Deduplicate: keep best chunk per source document (lowest distance)
        seen_docs: dict[str, dict] = {}
        for result in filtered:
            meta = result["metadata"]
            doc_key = meta.get("parent_id") or meta.get("filename", result["document"][:64])
            if doc_key not in seen_docs or result["distance"] < seen_docs[doc_key]["distance"]:
                seen_docs[doc_key] = result

        deduplicated = sorted(seen_docs.values(), key=lambda r: r["distance"])

        logger.debug(
            f"KB query: {len(raw)} fetched, {len(filtered)} passed threshold, "
            f"{len(deduplicated)} after dedup, returning {min(len(deduplicated), n_results)}"
        )

        # Return without internal 'distance' key
        return [{k: v for k, v in r.items() if k != "distance"} for r in deduplicated[:n_results]]

    except Exception as e:
        logger.error(f"KB query error: {e}")
        return []


def query_dataset(question: str, dataset_path: str, collections: list[str], n_results: int = 5) -> list[dict]:
    """
    Query Vanna dataset ChromaDB collections.

    Args:
        question: Search query
        dataset_path: Dataset name (e.g., 'snap_qc', 'state_ca')
        collections: Collections to search (['ddl'], ['documentation'], ['sql'], or multiple)
        n_results: Number of results per collection

    Returns: List of {document, metadata, relevance, source_display}
    """
    from src.services.llm_providers import _get_vanna_instance

    try:
        vanna = _get_vanna_instance()

        results = []

        # Query DDL collection
        if "ddl" in collections:
            try:
                ddl_docs = vanna.get_related_ddl(question, n_results=n_results)
                for doc in ddl_docs:
                    results.append(
                        {
                            "document": doc,
                            "metadata": {"collection": "ddl", "dataset": dataset_path},
                            "relevance": 0.9,
                            "source_display": f"🗄️ {dataset_path.upper()} Schema",
                        }
                    )
            except Exception as e:
                logger.warning(f"Error querying DDL: {e}")

        # Query documentation collection
        if "documentation" in collections:
            try:
                doc_docs = vanna.get_related_documentation(question, n_results=n_results)
                for doc in doc_docs:
                    results.append(
                        {
                            "document": doc,
                            "metadata": {"collection": "documentation", "dataset": dataset_path},
                            "relevance": 0.85,
                            "source_display": f"📖 {dataset_path.upper()} Context",
                        }
                    )
            except Exception as e:
                logger.warning(f"Error querying documentation: {e}")

        # Query SQL collection
        if "sql" in collections:
            try:
                sql_pairs = vanna.get_similar_question_sql(question, n_results=n_results)
                for q, sql in sql_pairs:
                    results.append(
                        {
                            "document": f"**Question:** {q}\n\n**SQL:**\n```sql\n{sql}\n```",
                            "metadata": {"collection": "sql", "dataset": dataset_path, "question": q, "sql": sql},
                            "relevance": 0.8,
                            "source_display": f"💡 {dataset_path.upper()} Examples",
                        }
                    )
            except Exception as e:
                logger.warning(f"Error querying SQL: {e}")

        logger.info(f"Dataset query ({dataset_path}) returned {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"Error querying dataset {dataset_path}: {e}")
        return []


def query_all(question: str, user_id: str, n_results: int = 10) -> list[dict]:
    """
    Query KB + all datasets.

    Returns combined results from KB and all available datasets.
    """
    all_results = []

    # Query KB
    kb_results = query_documents(question=question, user_id=user_id, n_results=n_results)
    all_results.extend(kb_results)

    # Query all datasets (derive from active dataset)
    try:
        from datasets import get_active_dataset

        ds = get_active_dataset()
        dataset_name = f"{ds.name}_qc" if ds else "snap_qc"
    except Exception:
        dataset_name = "snap_qc"
    datasets = [dataset_name]

    for dataset in datasets:
        dataset_results = query_dataset(
            question=question,
            dataset_path=dataset,
            collections=["ddl", "documentation", "sql"],
            n_results=3,  # Fewer per dataset when querying all
        )
        all_results.extend(dataset_results)

    # Sort by relevance
    all_results.sort(key=lambda x: x["relevance"], reverse=True)

    return all_results[:n_results]


def _build_where_filter(user_id: str, tags: list[str] | None, category: str | None, user_scope: str) -> dict:
    """Build ChromaDB WHERE filter."""
    filters = []

    # Access control
    if user_scope == "private":
        filters.append({"user_id": user_id})
    else:
        # Shared OR user's private
        filters.append({"$or": [{"visibility": "shared"}, {"user_id": user_id}]})

    # Category filter
    if category:
        filters.append({"category": category})

    # Tag filter (match any)
    if tags:
        if len(tags) == 1:
            filters.append({"tags": {"$contains": tags[0]}})
        else:
            filters.append({"$or": [{"tags": {"$contains": tag}} for tag in tags]})

    # Combine with AND
    if not filters:
        return {}
    elif len(filters) == 1:
        return filters[0]
    else:
        return {"$and": filters}


def list_documents(limit: int = 50) -> list[dict]:
    """
    List all documents in KB, grouping chunks into single entries.

    Returns: List of {id, metadata, content_preview}
    """
    collection = get_kb_collection()

    try:
        results = collection.get(
            include=["documents", "metadatas"],
            limit=limit * 5,  # Fetch extra since chunks inflate count
        )

        ids = results.get("ids", [])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])

        # Group by parent_id (chunked docs) or by id (single docs)
        groups: dict[str, dict] = {}
        for i, doc_id in enumerate(ids):
            doc_content = docs[i] if i < len(docs) else ""
            metadata = metas[i] if i < len(metas) else {}

            parent_id = metadata.get("parent_id")
            chunk_index = metadata.get("chunk_index")

            if parent_id:
                # This is a chunk — group under parent_id
                if parent_id not in groups:
                    groups[parent_id] = {
                        "id": parent_id,
                        "metadata": {k: v for k, v in metadata.items() if k not in ("chunk_index", "parent_id")},
                        "chunks": defaultdict(str),
                    }
                groups[parent_id]["chunks"][chunk_index] = doc_content
            else:
                # Single (non-chunked) document
                groups[doc_id] = {
                    "id": doc_id,
                    "metadata": metadata,
                    "chunks": None,
                    "content": doc_content,
                }

        # Build final list
        documents = []
        for group in groups.values():
            if group.get("chunks") is not None:
                # Chunked doc — preview from chunk 0
                first_chunk = group["chunks"].get(0, "")
                preview = first_chunk[:200] + "..." if len(first_chunk) > 200 else first_chunk
                total_chunks = group["metadata"].get("total_chunks", len(group["chunks"]))
                meta = dict(group["metadata"])
                meta["total_chunks"] = total_chunks
            else:
                content = group.get("content", "")
                preview = content[:200] + "..." if len(content) > 200 else content
                meta = group["metadata"]

            documents.append(
                {
                    "id": group["id"],
                    "metadata": meta,
                    "content_preview": preview,
                }
            )

        return documents[:limit]

    except Exception as e:
        logger.error(f"Error listing KB documents: {e}")
        return []


def delete_document(doc_id: str) -> bool:
    """
    Delete a document (and all its chunks) from KB.

    Returns: True if deleted, False otherwise
    """
    collection = get_kb_collection()

    try:
        # Delete the exact id
        collection.delete(ids=[doc_id])

        # Also delete any chunks that reference this id as parent_id
        try:
            chunked = collection.get(where={"parent_id": doc_id})
            if chunked and chunked["ids"]:
                collection.delete(ids=chunked["ids"])
                logger.info(f"Deleted {len(chunked['ids'])} chunks for parent {doc_id}")
        except Exception:
            pass  # No chunks found or where filter not supported — that's fine

        logger.info(f"Deleted KB document: {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting KB document {doc_id}: {e}")
        return False


def reset_kb() -> int:
    """
    Reset KB by deleting all entries using the existing singleton client.

    Returns: number of deleted entries
    """
    # Ensure client is initialized
    get_kb_collection()

    deleted_count = 0
    for collection in _kb_client.list_collections():
        try:
            results = collection.get()
            ids = results.get("ids", [])
            if ids:
                collection.delete(ids=ids)
                deleted_count += len(ids)
        except Exception as e:
            logger.warning(f"Could not clear {collection.name}: {e}")

    logger.info(f"KB reset: cleared {deleted_count} entries")
    return deleted_count


def get_stats() -> dict:
    """Get KB statistics (logical document count, not raw chunk count)."""
    collection = get_kb_collection()

    try:
        raw_count = collection.count()

        # Count logical documents by deduplicating on parent_id
        if raw_count == 0:
            doc_count = 0
        else:
            results = collection.get(include=["metadatas"])
            seen_parents: set[str] = set()
            doc_count = 0
            for meta in results.get("metadatas", []):
                parent_id = meta.get("parent_id") if meta else None
                if parent_id:
                    if parent_id not in seen_parents:
                        seen_parents.add(parent_id)
                        doc_count += 1
                else:
                    # Non-chunked document
                    doc_count += 1

        return {
            "total_documents": doc_count,
            "total_chunks": raw_count,
            "collection_name": "kb",
            "path": f"{settings.vanna_chromadb_path}/kb",
        }
    except Exception as e:
        logger.error(f"Error getting KB stats: {e}")
        return {"total_documents": 0, "error": str(e)}


def _format_source(metadata: dict) -> str:
    """Format source display string."""
    category = metadata.get("category", "general")
    filename = metadata.get("filename", "Unknown")

    # Format category
    cat_display = "🔒 Private" if category.startswith("user:") else f"📘 {category.title()}"

    # Format tags
    tags = metadata.get("tags", "")
    tags_display = f" #{tags.replace(',', ' #')}" if tags else ""

    return f"{cat_display} - {filename}{tags_display}"
