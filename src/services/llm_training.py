"""
Vanna Training Data Loader

Scans SQL_TRAINING_DATA_PATH folder for training files:
- .md/.txt files → loaded as documentation (chunked for better retrieval)
- .json files → parsed for question/SQL pairs ({"example_queries": [...]})
- DDL comes from the live database, not from files

Default folder: ./datasets/snap/training/
Override via env: SQL_TRAINING_DATA_PATH=./my_dataset/training
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


def get_training_data_path() -> Path:
    """Get the Vanna training data folder from settings."""
    return Path(settings.resolved_training_path)


def get_documentation_files() -> list[Path]:
    """
    Discover all documentation files (.md, .txt) in the training data folder.

    No naming convention required — all .md and .txt files are loaded.
    """
    folder = get_training_data_path()
    if not folder.exists():
        logger.warning(f"Training data folder not found: {folder}")
        return []

    doc_files = sorted(folder.glob("*.md")) + sorted(folder.glob("*.txt"))
    logger.debug(f"Found {len(doc_files)} documentation files in {folder}")
    return doc_files


def load_training_examples() -> list[dict]:
    """
    Load question/SQL pairs from all .json files in the training data folder.

    Each JSON file should contain: {"example_queries": [{"question": "...", "sql": "..."}]}
    Files without an "example_queries" key are skipped.

    Returns: Combined list of example dicts with 'question' and 'sql' keys.
    """
    folder = get_training_data_path()
    if not folder.exists():
        logger.warning(f"Training data folder not found: {folder}")
        return []

    all_examples = []
    for json_path in sorted(folder.glob("*.json")):
        try:
            with open(json_path) as f:
                data = json.load(f)

            examples = data.get("example_queries", [])
            if examples:
                all_examples.extend(examples)
                logger.debug(f"Loaded {len(examples)} examples from {json_path.name}")
            else:
                logger.debug(f"No 'example_queries' key in {json_path.name}, skipping")
        except Exception as e:
            logger.error(f"Error loading {json_path.name}: {e}")

    return all_examples


def get_ddl_statements(dataset: str | None = None) -> list[str]:
    """
    Get DDL statements from the live database.

    DDL is always extracted from the running database, not from files.
    """
    try:
        from src.database.ddl_extractor import get_all_ddl_statements

        ddl_statements = get_all_ddl_statements(
            include_samples=True,
            dataset_name=dataset,
        )
        logger.debug(f"Extracted {len(ddl_statements)} DDL statements")
        return ddl_statements
    except Exception as e:
        logger.error(f"Failed to extract DDL: {e}")
        return []
