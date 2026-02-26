"""
UI Configuration

Configuration specific to the Chainlit UI layer.
Contains only UI-related constants like persona and display settings.

For API configuration, see src/core/config.py
For API client, see src/clients/api_client.py
"""

from pathlib import Path

import yaml


def _get_personas() -> tuple[str, str]:
    """Get persona names from active dataset, with defaults."""
    try:
        from datasets import get_active_dataset

        ds = get_active_dataset()
        if ds:
            personas = ds.get_personas()
            return personas.get("app", "SnapAnalyst"), personas.get("ai", "SnapAnalyst AI")
    except Exception:
        pass
    return "SnapAnalyst", "SnapAnalyst AI"


# =============================================================================
# PERSONA CONFIGURATION
# =============================================================================

# The name for system/app messages (commands, status, errors)
APP_PERSONA, AI_PERSONA = _get_personas()

# =============================================================================
# DISPLAY CONFIGURATION
# =============================================================================

# Maximum rows to display in HTML table (full data available in CSV)
MAX_DISPLAY_ROWS = 50

# =============================================================================
# FILE CONFIGURATION (UI-specific defaults)
# =============================================================================


# Supported fiscal years for display/validation (loaded from active dataset)
def _load_fiscal_years() -> list[int]:
    """Load fiscal years from active dataset configuration."""
    try:
        from datasets import get_active_dataset

        ds = get_active_dataset()
        if ds and hasattr(ds, "get_fiscal_years"):
            years = ds.get_fiscal_years()
            if years:
                return years
    except Exception:
        pass
    # Fallback: try datasets/snap/config.yaml directly
    config_path = Path(__file__).resolve().parent.parent / "datasets" / "snap" / "config.yaml"
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        data_files = config.get("data_files", {})
        if data_files:
            return sorted(int(y) for y in data_files)
    except Exception:
        pass
    return []


SUPPORTED_FISCAL_YEARS = _load_fiscal_years()

# Default fiscal year when not detected from filename
DEFAULT_FISCAL_YEAR = 2023

# Maximum file upload size (MB) - for UI validation
MAX_UPLOAD_SIZE_MB = 100

# Upload timeout (seconds) - for UI display
UPLOAD_TIMEOUT_SECONDS = 180
