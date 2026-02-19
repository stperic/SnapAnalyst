"""
UI Configuration

Configuration specific to the Chainlit UI layer.
Contains only UI-related constants like persona and display settings.

For API configuration, see src/core/config.py
For API client, see src/clients/api_client.py
"""

from pathlib import Path

import yaml

# =============================================================================
# PERSONA CONFIGURATION
# =============================================================================

# The name for system/app messages (commands, status, errors)
APP_PERSONA = "SnapAnalyst"

# The name for AI-generated responses (query answers, analysis)
AI_PERSONA = "SnapAnalyst AI"

# =============================================================================
# DISPLAY CONFIGURATION
# =============================================================================

# Maximum rows to display in HTML table (full data available in CSV)
MAX_DISPLAY_ROWS = 50

# =============================================================================
# FILE CONFIGURATION (UI-specific defaults)
# =============================================================================

# Supported fiscal years for display/validation (loaded from config.yaml)
def _load_fiscal_years() -> list[int]:
    """Load fiscal years from datasets/snap/config.yaml."""
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
