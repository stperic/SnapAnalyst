"""
Code Enrichment Service

Handles loading and applying code descriptions to query results.
Maps numeric codes to human-readable descriptions.

This is business/domain logic, not UI-specific.
"""

import json
from pathlib import Path

from src.core.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# CODE COLUMN MAPPINGS (loaded from active dataset)
# =============================================================================


def _get_code_column_mappings() -> dict[str, str]:
    """Get code column mappings from the active dataset configuration."""
    try:
        from datasets import get_active_dataset

        ds = get_active_dataset()
        if ds:
            return ds.get_code_column_mappings()
    except Exception:
        pass
    return {}


# Backward-compatible module-level access (lazy-evaluated)
CODE_COLUMN_MAPPINGS = _get_code_column_mappings()

# =============================================================================
# GLOBAL CACHE
# =============================================================================

_CODE_LOOKUPS_CACHE = None


def load_code_lookups() -> dict:
    """
    Load code lookups from data_mapping.json.
    Cached after first load for performance.

    Returns:
        Dictionary of all code lookups
    """
    global _CODE_LOOKUPS_CACHE

    if _CODE_LOOKUPS_CACHE is not None:
        return _CODE_LOOKUPS_CACHE

    try:
        # Try loading from active dataset first
        try:
            from datasets import get_active_dataset

            ds = get_active_dataset()
            if ds:
                _CODE_LOOKUPS_CACHE = ds.get_code_lookups()
                if _CODE_LOOKUPS_CACHE:
                    logger.info(f"Loaded {len(_CODE_LOOKUPS_CACHE)} code lookup tables from dataset '{ds.name}'")
                    return _CODE_LOOKUPS_CACHE
        except Exception as e:
            logger.debug(f"Could not load code lookups from dataset registry: {e}")

        # Fallback: search for data_mapping.json directly
        possible_paths = [
            Path(__file__).parent.parent.parent / "datasets" / "snap" / "data_mapping.json",
            Path(__file__).parent.parent.parent / "data_mapping.json",
        ]

        for data_mapping_path in possible_paths:
            if data_mapping_path.exists():
                with open(data_mapping_path) as f:
                    data = json.load(f)
                    _CODE_LOOKUPS_CACHE = data.get("code_lookups", {})
                    logger.info(f"Loaded {len(_CODE_LOOKUPS_CACHE)} code lookup tables from {data_mapping_path}")
                    return _CODE_LOOKUPS_CACHE

        logger.warning("data_mapping.json not found")
        return {}

    except Exception as e:
        logger.error(f"Error loading code lookups: {e}")
        return {}


def enrich_results_with_code_descriptions(results: list[dict]) -> dict[str, dict[str, str]]:
    """
    Find code columns in results and load their descriptions.
    Returns only the codes that actually appear in the results.

    Args:
        results: List of query result dictionaries

    Returns:
        Dictionary mapping column names to {code: description} dictionaries
        Example: {
            'element_code': {
                '311': 'Wages and salaries',
                '363': 'Shelter deduction'
            }
        }
    """
    if not results:
        return {}

    # Detect code columns in results
    code_column_mappings = _get_code_column_mappings()
    column_names = set(results[0].keys())
    code_columns = column_names & code_column_mappings.keys()

    if not code_columns:
        return {}  # No code columns found

    logger.info(f"Detected code columns in results: {code_columns}")

    # Load code lookups
    code_lookups = load_code_lookups()

    enriched = {}
    for col_name in code_columns:
        lookup_key = code_column_mappings[col_name]

        # Extract unique codes from results (convert to string for lookup)
        unique_codes = set()
        for row in results:
            code_value = row.get(col_name)
            if code_value is not None:
                unique_codes.add(str(code_value))

        if not unique_codes:
            continue

        # Load ONLY those codes that appear in results
        lookup_table = code_lookups.get(lookup_key, {})

        enriched[col_name] = {}
        for code in unique_codes:
            # Get description, skip metadata fields
            if code in lookup_table and code not in ["description", "source_field"]:
                enriched[col_name][code] = lookup_table[code]
            else:
                enriched[col_name][code] = f"Unknown code {code}"

        logger.info(f"Enriched {col_name}: {len(enriched[col_name])} codes mapped")

    return enriched


def clear_cache():
    """Clear the code lookups cache (useful for testing)."""
    global _CODE_LOOKUPS_CACHE
    _CODE_LOOKUPS_CACHE = None
