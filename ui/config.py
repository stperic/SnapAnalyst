"""
UI Configuration

Configuration specific to the Chainlit UI layer.
Contains only UI-related constants like persona and display settings.

For API configuration, see src/core/config.py
For API client, see src/clients/api_client.py
"""

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

# Supported fiscal years for display/validation
SUPPORTED_FISCAL_YEARS = [2021, 2022, 2023]

# Default fiscal year when not detected from filename
DEFAULT_FISCAL_YEAR = 2023

# Maximum file upload size (MB) - for UI validation
MAX_UPLOAD_SIZE_MB = 100

# Upload timeout (seconds) - for UI display
UPLOAD_TIMEOUT_SECONDS = 180
