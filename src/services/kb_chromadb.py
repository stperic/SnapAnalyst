"""
Knowledge Base ChromaDB Module

Simple, clean interface for KB ChromaDB operations.
Path: ./chromadb/kb/ | Collection: "kb"
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime

# Configure ONNX Runtime before any ChromaDB imports
# CRITICAL: Explicitly set thread count to prevent CPU affinity errors in LXC containers
# When thread count is explicit, ONNX Runtime skips automatic CPU affinity (which fails in LXC)
# See: https://github.com/chroma-core/chroma/issues/1420
if not os.environ.get('OMP_NUM_THREADS') or os.environ.get('OMP_NUM_THREADS') == '0':
    os.environ['OMP_NUM_THREADS'] = '4'

import chromadb

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_kb_client = None


def get_kb_collection():
    """Get or create KB collection."""
    global _kb_client

    if _kb_client is None:
        kb_path = f"{settings.vanna_chromadb_path}/kb"
        # Create ChromaDB client with telemetry explicitly disabled
        client_settings = chromadb.config.Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
        _kb_client = chromadb.PersistentClient(path=kb_path, settings=client_settings)
        logger.info(f"Initialized KB ChromaDB at {kb_path}")

    return _kb_client.get_or_create_collection(
        name="user_kb",
        metadata={"description": "User knowledge base"}
    )


def add_document(
    text: str,
    filename: str,
    category: str = "general",
    tags: list[str] | None = None,
    user_id: str = "anonymous@snapanalyst.com",
    is_private: bool = False
) -> str:
    """
    Add document to KB.

    Returns: document ID
    """
    collection = get_kb_collection()

    # Set category for private docs
    if is_private:
        category = f"user:{user_id}"

    # Build metadata
    metadata = {
        "category": category,
        "tags": ",".join(tags) if tags else "",
        "filename": filename,
        "user_id": user_id,
        "visibility": "private" if is_private else "shared",
        "char_count": len(text),
        "created_at": datetime.utcnow().isoformat()
    }

    # Add to ChromaDB
    doc_id = f"kb_{uuid.uuid4().hex[:12]}"
    collection.add(
        ids=[doc_id],
        documents=[text],
        metadatas=[metadata]
    )

    logger.info(f"Added to KB: {filename} ({category}, {metadata['visibility']})")
    return doc_id


def query_documents(
    question: str,
    user_id: str = "anonymous@snapanalyst.com",
    tags: list[str] | None = None,
    category: str | None = None,
    user_scope: str = "all",
    n_results: int = 10
) -> list[dict]:
    """
    Query KB with filtering and access control.

    Returns: List of {document, metadata, relevance, source_display}
    """
    collection = get_kb_collection()

    # Build WHERE filter
    where_filter = _build_where_filter(user_id, tags, category, user_scope)

    try:
        results = collection.query(
            query_texts=[question],
            n_results=n_results * 2,  # Get extra for filtering
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        # Format results
        formatted = []
        for doc, meta, dist in zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0],
            strict=False,
        ):
            formatted.append({
                'document': doc,
                'metadata': meta,
                'relevance': 1 - dist,
                'source_display': _format_source(meta)
            })

        return formatted[:n_results]

    except Exception as e:
        logger.error(f"KB query error: {e}")
        return []


def query_dataset(
    question: str,
    dataset_path: str,
    collections: list[str],
    n_results: int = 5
) -> list[dict]:
    """
    Query Vanna dataset ChromaDB collections.

    Args:
        question: Search query
        dataset_path: Dataset name (e.g., 'snap_qc', 'state_ca')
        collections: Collections to search (['ddl'], ['documentation'], ['sql'], or multiple)
        n_results: Number of results per collection

    Returns: List of {document, metadata, relevance, source_display}
    """
    from src.services.llm_service import get_llm_service

    try:
        llm_service = get_llm_service()
        vanna = llm_service.get_vanna_for_dataset(dataset_path)

        results = []

        # Query DDL collection
        if 'ddl' in collections:
            try:
                ddl_docs = vanna.get_related_ddl(question, n_results=n_results)
                for doc in ddl_docs:
                    results.append({
                        'document': doc,
                        'metadata': {'collection': 'ddl', 'dataset': dataset_path},
                        'relevance': 0.9,
                        'source_display': f'🗄️ {dataset_path.upper()} Schema'
                    })
            except Exception as e:
                logger.warning(f"Error querying DDL: {e}")

        # Query documentation collection
        if 'documentation' in collections:
            try:
                doc_docs = vanna.get_related_documentation(question, n_results=n_results)
                for doc in doc_docs:
                    results.append({
                        'document': doc,
                        'metadata': {'collection': 'documentation', 'dataset': dataset_path},
                        'relevance': 0.85,
                        'source_display': f'📖 {dataset_path.upper()} Context'
                    })
            except Exception as e:
                logger.warning(f"Error querying documentation: {e}")

        # Query SQL collection
        if 'sql' in collections:
            try:
                sql_pairs = vanna.get_similar_question_sql(question, n_results=n_results)
                for q, sql in sql_pairs:
                    results.append({
                        'document': f"**Question:** {q}\n\n**SQL:**\n```sql\n{sql}\n```",
                        'metadata': {
                            'collection': 'sql',
                            'dataset': dataset_path,
                            'question': q,
                            'sql': sql
                        },
                        'relevance': 0.8,
                        'source_display': f'💡 {dataset_path.upper()} Examples'
                    })
            except Exception as e:
                logger.warning(f"Error querying SQL: {e}")

        logger.info(f"Dataset query ({dataset_path}) returned {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"Error querying dataset {dataset_path}: {e}")
        return []


def query_all(
    question: str,
    user_id: str,
    n_results: int = 10
) -> list[dict]:
    """
    Query KB + all datasets.

    Returns combined results from KB and all available datasets.
    """
    all_results = []

    # Query KB
    kb_results = query_documents(
        question=question,
        user_id=user_id,
        n_results=n_results
    )
    all_results.extend(kb_results)

    # Query all datasets (discover dynamically)
    datasets = ['snap_qc']  # TODO: Make this dynamic by discovering schemas

    for dataset in datasets:
        dataset_results = query_dataset(
            question=question,
            dataset_path=dataset,
            collections=['ddl', 'documentation', 'sql'],
            n_results=3  # Fewer per dataset when querying all
        )
        all_results.extend(dataset_results)

    # Sort by relevance
    all_results.sort(key=lambda x: x['relevance'], reverse=True)

    return all_results[:n_results]


def _build_where_filter(
    user_id: str,
    tags: list[str] | None,
    category: str | None,
    user_scope: str
) -> dict:
    """Build ChromaDB WHERE filter."""
    filters = []

    # Access control
    if user_scope == "private":
        filters.append({"user_id": user_id})
    else:
        # Shared OR user's private
        filters.append({
            "$or": [
                {"visibility": "shared"},
                {"user_id": user_id}
            ]
        })

    # Category filter
    if category:
        filters.append({"category": category})

    # Tag filter (match any)
    if tags:
        if len(tags) == 1:
            filters.append({"tags": {"$contains": tags[0]}})
        else:
            filters.append({
                "$or": [{"tags": {"$contains": tag}} for tag in tags]
            })

    # Combine with AND
    if not filters:
        return {}
    elif len(filters) == 1:
        return filters[0]
    else:
        return {"$and": filters}


def list_documents(limit: int = 50) -> list[dict]:
    """
    List all documents in KB.

    Returns: List of {id, metadata, content_preview}
    """
    collection = get_kb_collection()

    try:
        results = collection.get(
            include=["documents", "metadatas"],
            limit=limit
        )

        documents = []
        ids = results.get('ids', [])
        docs = results.get('documents', [])
        metas = results.get('metadatas', [])

        for i, doc_id in enumerate(ids):
            doc_content = docs[i] if i < len(docs) else ""
            metadata = metas[i] if i < len(metas) else {}

            documents.append({
                'id': doc_id,
                'metadata': metadata,
                'content_preview': doc_content[:200] + "..." if len(doc_content) > 200 else doc_content
            })

        return documents

    except Exception as e:
        logger.error(f"Error listing KB documents: {e}")
        return []


def delete_document(doc_id: str) -> bool:
    """
    Delete a document from KB.

    Returns: True if deleted, False otherwise
    """
    collection = get_kb_collection()

    try:
        collection.delete(ids=[doc_id])
        logger.info(f"Deleted KB document: {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting KB document {doc_id}: {e}")
        return False


def get_stats() -> dict:
    """Get KB statistics."""
    collection = get_kb_collection()

    try:
        count = collection.count()
        return {
            'total_documents': count,
            'collection_name': 'kb',
            'path': f"{settings.vanna_chromadb_path}/kb"
        }
    except Exception as e:
        logger.error(f"Error getting KB stats: {e}")
        return {'total_documents': 0, 'error': str(e)}


def _format_source(metadata: dict) -> str:
    """Format source display string."""
    category = metadata.get('category', 'general')
    filename = metadata.get('filename', 'Unknown')

    # Format category
    cat_display = "🔒 Private" if category.startswith('user:') else f"📘 {category.title()}"

    # Format tags
    tags = metadata.get('tags', '')
    tags_display = f" #{tags.replace(',', ' #')}" if tags else ""

    return f"{cat_display} - {filename}{tags_display}"
