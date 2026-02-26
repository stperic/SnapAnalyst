"""
Tag Parser and Validator

Utilities for parsing and validating tags in /memadd commands.
Supports hashtag syntax and enforces consistent formatting.
"""

import re

from src.core.logging import get_logger

logger = get_logger(__name__)


def parse_memadd_command(args: str) -> tuple[str, list[str]]:
    """
    Parse /memadd command arguments to extract category and tags.

    Syntax: /memadd [category] [#tag1 #tag2 ...]

    Examples:
        "business-rules #SNAP #eligibility" → ("business-rules", ["snap", "eligibility"])
        "#SNAP #policy" → ("general", ["snap", "policy"])
        "glossary" → ("glossary", [])
        "" → ("general", [])

    Args:
        args: Command arguments after /memadd

    Returns:
        Tuple of (category, tags_list)
    """
    if not args or not args.strip():
        return ("general", [])

    args = args.strip()

    # Extract all hashtags
    hashtag_pattern = r"#([a-zA-Z0-9_-]+)"
    tags_raw = re.findall(hashtag_pattern, args)

    # Normalize tags: lowercase
    tags = [tag.lower() for tag in tags_raw]

    # Remove hashtags from args to get category
    category_text = re.sub(hashtag_pattern, "", args).strip()

    # If no category text, use "general"
    category = category_text if category_text else "general"

    # Validate category (alphanumeric, hyphens, underscores only)
    category = validate_category(category)

    # Validate tags
    tags = validate_tags(tags)

    logger.info(f"Parsed /memadd: category='{category}', tags={tags}")

    return (category, tags)


def validate_category(category: str) -> str:
    """
    Validate and clean category name.

    Rules:
    - Lowercase
    - Alphanumeric + hyphens + underscores
    - No spaces
    - Max 50 chars

    Args:
        category: Category string

    Returns:
        Validated category (or "general" if invalid)
    """
    if not category:
        return "general"

    # Remove invalid characters
    cleaned = re.sub(r"[^a-z0-9_-]", "", category.lower())

    # Truncate if too long
    if len(cleaned) > 50:
        cleaned = cleaned[:50]
        logger.warning(f"Category truncated to 50 chars: {cleaned}")

    # Return "general" if nothing left
    return cleaned if cleaned else "general"


def validate_tags(tags: list[str]) -> list[str]:
    """
    Validate and deduplicate tags.

    Rules:
    - Lowercase
    - Alphanumeric + hyphens + underscores
    - No duplicates
    - Warn if > 10 tags
    - Max 30 chars per tag

    Args:
        tags: List of tag strings

    Returns:
        Validated list of unique tags
    """
    if not tags:
        return []

    validated = []
    seen = set()

    for tag in tags:
        # Clean tag
        cleaned = re.sub(r"[^a-z0-9_-]", "", tag.lower())

        # Truncate if too long
        if len(cleaned) > 30:
            cleaned = cleaned[:30]

        # Skip if empty or duplicate
        if not cleaned or cleaned in seen:
            continue

        validated.append(cleaned)
        seen.add(cleaned)

    # Warn if too many tags
    if len(validated) > 10:
        logger.warning(f"More than 10 tags ({len(validated)}): {validated}")

    return validated


def validate_file_extension(filename: str, allowed: list[str] | None = None) -> bool:
    """
    Validate file extension.

    Args:
        filename: Filename to check
        allowed: List of allowed extensions (with dots)

    Returns:
        True if valid, False otherwise
    """
    from pathlib import Path

    if allowed is None:
        allowed = [".md", ".txt"]

    ext = Path(filename).suffix.lower()
    return ext in allowed


def validate_file_size(size_bytes: int, max_mb: int = 10) -> bool:
    """
    Validate file size.

    Args:
        size_bytes: File size in bytes
        max_mb: Maximum allowed size in MB

    Returns:
        True if valid, False otherwise
    """
    max_bytes = max_mb * 1024 * 1024
    return size_bytes <= max_bytes


def format_tags_display(tags: list[str]) -> str:
    """
    Format tags for display.

    Args:
        tags: List of tags

    Returns:
        Formatted string like "#tag1 #tag2"
    """
    if not tags:
        return ""
    return " ".join(f"#{tag}" for tag in tags)
