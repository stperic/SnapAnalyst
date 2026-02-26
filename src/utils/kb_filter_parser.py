"""
Knowledge Base Filter Parser

Parse search filters from user questions.
Supports: ChromaDB paths, hashtags, categories, user scope.
"""

from __future__ import annotations

import re


def parse_kb_filters(question: str, user_id: str) -> dict:
    """
    Parse filters from question.

    Examples:
        "What are SNAP rules?"
        → {chromadb_path: 'kb', question: 'What are SNAP rules?', ...}

        "snap_qc What tables have income?"
        → {chromadb_path: 'snap_qc', collections: ['ddl', 'documentation', 'sql'], ...}

        "@me #research What did I note?"
        → {user_scope: 'private', tags: ['research'], ...}
    """
    filters = {
        "question": question,
        "chromadb_path": "kb",
        "collections": ["kb"],
        "tags": [],
        "category": None,
        "user_scope": "all",
    }

    # Extract ChromaDB path (snap_qc, state_ca, kb, all)
    path_match = re.match(r"^\s*(snap_qc|state_ca|kb|all)(?::(\w+))?\s+", question, re.I)
    if path_match:
        path = path_match.group(1).lower()
        specific_collection = path_match.group(2)

        if path == "all":
            filters["chromadb_path"] = "all"
            filters["collections"] = ["kb", "ddl", "documentation", "sql"]
        elif path == "kb":
            filters["chromadb_path"] = "kb"
            filters["collections"] = ["kb"]
        else:
            filters["chromadb_path"] = path
            filters["collections"] = (
                [specific_collection.lower()] if specific_collection else ["ddl", "documentation", "sql"]
            )

        question = re.sub(r"^\s*(snap_qc|state_ca|kb|all)(?::\w+)?\s+", "", question, flags=re.I)

    # Extract user scope (@me, @private)
    if re.search(r"(@me|@private)\b", question, re.I):
        filters["user_scope"] = "private"
        question = re.sub(r"(@me|@private)\b", "", question, flags=re.I)

    # Extract category (category:name)
    cat_match = re.search(r"\bcategory:(\w+)\b", question, re.I)
    if cat_match:
        filters["category"] = cat_match.group(1).lower()
        question = re.sub(r"\bcategory:\w+\b", "", question, flags=re.I)

    # Extract hashtags
    tags = re.findall(r"#(\w+)", question)
    if tags:
        filters["tags"] = [t.lower() for t in tags]
        question = re.sub(r"#\w+", "", question)

    # Clean question
    filters["question"] = re.sub(r"\s+", " ", question).strip()

    return filters


def format_search_scope(filters: dict) -> str:
    """Format scope for display."""
    path = filters["chromadb_path"]

    if path == "kb":
        scope = "Knowledge Base"
    elif path == "all":
        scope = "All Sources"
    else:
        dataset = path.upper().replace("_", " ")
        if len(filters["collections"]) == 1:
            col = filters["collections"][0].title()
            scope = f"🔍 {dataset} - {col}"
        else:
            scope = f"🔍 {dataset}"

    # Add filters
    parts = [scope]
    if filters["tags"]:
        parts.append(f"Tags: {' '.join('#' + t for t in filters['tags'])}")
    if filters["category"]:
        parts.append(f"Category: {filters['category']}")
    if filters["user_scope"] == "private":
        parts.append("🔒 Your Docs")

    return " | ".join(parts)


def parse_memadd_command(args: str, user_id: str) -> tuple[str, list[str], bool]:
    """
    Parse /memadd arguments.

    Examples:
        "policy #snap #eligibility" → ("policy", ["snap", "eligibility"], False)
        "@me notes #research" → ("user:eric@...", ["research"], True)
        "#snap" → ("general", ["snap"], False)
    """
    parts = args.strip().split()

    # Check privacy
    is_private = bool(parts and parts[0].lower() in ["@me", "@private"])
    if is_private:
        parts = parts[1:]

    # Extract category and tags
    category = None
    tags = []

    for part in parts:
        if part.startswith("#"):
            tags.append(part.lstrip("#").lower())
        elif not category:
            category = part.lower()

    # Set final category
    if is_private:
        category = f"user:{user_id}"
    elif not category:
        category = "general"

    return category, tags, is_private
