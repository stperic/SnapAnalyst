"""
Training Data Utilities for Vanna 2.x

In Vanna 2.x, training is automatic through agent memory.
This module provides utilities for loading schema and examples
that can be used for reference or seeding agent memory if needed.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.config import settings
from src.core.logging import get_logger
from src.core.prompts import BUSINESS_CONTEXT_DOCUMENTATION

logger = get_logger(__name__)


def load_schema() -> dict:
    """
    Load database schema documentation from JSON file.

    Returns:
        Schema dictionary

    Note:
        Vanna 2.x agents learn schema automatically by executing queries.
        This is provided for reference or documentation purposes.
    """
    schema_path = Path(settings.vanna_schema_path)

    if not schema_path.exists():
        logger.warning(f"Schema file not found: {schema_path}")
        return {}

    try:
        with open(schema_path) as f:
            schema = json.load(f)
        logger.info(f"Loaded schema from {schema_path}")
        return schema
    except Exception as e:
        logger.error(f"Error loading schema: {e}")
        return {}


def load_training_examples() -> list[dict]:
    """
    Load SQL query examples from JSON file.

    Returns:
        List of example queries with 'question' and 'sql' keys

    Note:
        Vanna 2.x agents learn from actual usage automatically.
        These examples can be used for documentation or testing.
    """
    examples_path = Path(settings.vanna_training_data_path)

    if not examples_path.exists():
        logger.warning(f"Examples file not found: {examples_path}")
        return []

    try:
        with open(examples_path) as f:
            data = json.load(f)

        examples = data.get("example_queries", [])
        logger.info(f"Loaded {len(examples)} examples from {examples_path}")
        return examples
    except Exception as e:
        logger.error(f"Error loading examples: {e}")
        return []


def get_ddl_statements(dataset: str | None = None) -> list[str]:
    """
    Get DDL statements from database.

    Extracts CREATE TABLE and other DDL from information_schema.

    Args:
        dataset: Optional dataset name for filtering

    Returns:
        List of DDL statements

    Note:
        Vanna 2.x agents learn schema by executing queries.
        DDL extraction is for reference/documentation.
    """
    try:
        from src.database.ddl_extractor import get_all_ddl_statements

        ddl_statements = get_all_ddl_statements(
            include_samples=True,
            dataset_name=dataset,
        )
        logger.info(f"Extracted {len(ddl_statements)} DDL statements")
        return ddl_statements
    except Exception as e:
        logger.error(f"Failed to extract DDL: {e}")
        return []


def get_business_context(dataset: str | None = None) -> str:
    """
    Get business terminology and context documentation.

    Args:
        dataset: Optional dataset name (for future dataset-specific docs)

    Returns:
        Business context documentation text
    """
    # Currently returns global documentation
    # Future: Could load dataset-specific documentation
    return BUSINESS_CONTEXT_DOCUMENTATION
