"""
Code Enrichment Service

Handles loading and applying code descriptions to query results.
Maps numeric codes to human-readable descriptions.

This is business/domain logic, not UI-specific.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# =============================================================================
# CODE COLUMN MAPPINGS
# =============================================================================

# Maps column names to lookup keys in data_mapping.json
CODE_COLUMN_MAPPINGS = {
    'element_code': 'element_codes',
    'nature_code': 'nature_codes',
    'status': 'status_codes',
    'error_finding': 'error_finding_codes',
    'case_classification': 'case_classification_codes',
    'expedited_service': 'expedited_service_codes',
    'categorical_eligibility': 'categorical_eligibility_codes',
    'sex': 'sex_codes',
    'snap_affiliation_code': 'snap_affiliation_codes',
    'agency_responsibility': 'agency_responsibility_codes',
    'discovery_method': 'discovery_method_codes',
}

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
        # Look for data_mapping.json in datasets/snap/ (primary) or project root (fallback)
        possible_paths = [
            Path(__file__).parent.parent.parent / "datasets" / "snap" / "data_mapping.json",  # Primary location
            Path("./datasets/snap/data_mapping.json"),  # Current directory
            Path(__file__).parent.parent.parent / "data_mapping.json",  # Legacy root location
        ]

        for data_mapping_path in possible_paths:
            if data_mapping_path.exists():
                with open(data_mapping_path) as f:
                    data = json.load(f)
                    _CODE_LOOKUPS_CACHE = data.get('code_lookups', {})
                    logger.info(f"Loaded {len(_CODE_LOOKUPS_CACHE)} code lookup tables from {data_mapping_path}")
                    return _CODE_LOOKUPS_CACHE

        logger.warning("data_mapping.json not found in datasets/snap/ or root")
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
    column_names = set(results[0].keys())
    code_columns = column_names & CODE_COLUMN_MAPPINGS.keys()

    if not code_columns:
        return {}  # No code columns found

    logger.info(f"Detected code columns in results: {code_columns}")

    # Load code lookups
    code_lookups = load_code_lookups()

    enriched = {}
    for col_name in code_columns:
        lookup_key = CODE_COLUMN_MAPPINGS[col_name]

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
            if code in lookup_table and code not in ['description', 'source_field']:
                enriched[col_name][code] = lookup_table[code]
            else:
                enriched[col_name][code] = f"Unknown code {code}"

        logger.info(f"Enriched {col_name}: {len(enriched[col_name])} codes mapped")

    return enriched


def clear_cache():
    """Clear the code lookups cache (useful for testing)."""
    global _CODE_LOOKUPS_CACHE
    _CODE_LOOKUPS_CACHE = None
