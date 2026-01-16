"""
API Client

Handles all communication with the SnapAnalyst backend API.
This is a generic HTTP client that can be used by any frontend.
"""

import httpx
from typing import Dict, Optional
import logging
import os

from ..core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# API CONFIGURATION
# =============================================================================

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
# External URL for download links (browser-accessible)
# Options:
#   - "relative" or "" → Use relative URLs (for production behind reverse proxy)
#   - "http://localhost:8000" → Explicit URL (for local development)
#   - "https://api.example.com" → Custom domain
API_EXTERNAL_URL = os.getenv("API_EXTERNAL_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"

# Timeout configuration (seconds)
API_TIMEOUT_DEFAULT = 30.0
API_TIMEOUT_HEALTH = 5.0
API_TIMEOUT_UPLOAD = 120.0


# =============================================================================
# API CLIENT FUNCTIONS
# =============================================================================

class APIError(Exception):
    """Custom exception for API errors with user-friendly messages."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def call_api(
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict] = None,
    timeout: float = API_TIMEOUT_DEFAULT
) -> Dict:
    """
    Make API call to SnapAnalyst backend.
    
    Args:
        endpoint: API endpoint (e.g., "/chat/query")
        method: HTTP method (GET or POST)
        data: Request body for POST requests
        timeout: Request timeout in seconds
        
    Returns:
        Response JSON as dictionary
        
    Raises:
        APIError: If request fails with a user-friendly message
        httpx.HTTPError: For network/connection errors
    """
    url = f"{API_BASE_URL}{API_PREFIX}{endpoint}"
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            response = await client.get(url)
        elif method == "POST":
            response = await client.post(url, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        # Handle error responses with user-friendly messages
        if response.status_code >= 400:
            try:
                error_body = response.json()
                detail = error_body.get("detail", "An error occurred")
            except Exception:
                detail = f"Request failed with status {response.status_code}"
            
            logger.warning(f"API error {response.status_code}: {detail}")
            raise APIError(detail, response.status_code)
        
        return response.json()


async def check_api_health() -> tuple[bool, str]:
    """
    Check API service health.
    
    Returns:
        Tuple of (is_healthy, version_string)
    """
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT_HEALTH) as client:
            response = await client.get(f"{API_BASE_URL}/health")
            health = response.json()
            return True, health.get("version", "unknown")
    except Exception as e:
        logger.error(f"API health check failed: {e}")
        return False, "unknown"


async def check_database_health() -> tuple[bool, str]:
    """
    Check database connection health.
    
    Returns:
        Tuple of (is_connected, database_name)
    """
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT_HEALTH) as client:
            response = await client.get(f"{API_BASE_URL}/api/v1/data/health")
            health = response.json()
            db_info = health.get("database", {})
            if db_info.get('connected', False):
                return True, db_info.get('name', 'snapanalyst_db')
            return False, "unknown"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False, "unknown"


async def check_llm_health() -> tuple[bool, str]:
    """
    Check LLM service health and availability.
    
    Performs actual connectivity check:
    - OpenAI: Verifies API key is set and valid
    - Anthropic: Verifies API key is configured
    - Ollama: Verifies server is reachable and model available
    
    Returns:
        Tuple of (is_healthy, provider_name_with_status)
        - provider_name_with_status includes error info if unhealthy
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:  # Longer timeout for Ollama check
            response = await client.get(f"{API_BASE_URL}/api/v1/chat/health")
            health = response.json()
            
            is_healthy = health.get('healthy', False)
            provider = health.get('provider', 'Unknown')
            status = health.get('status', 'unknown')
            error = health.get('error', '')
            
            if is_healthy:
                return True, provider
            else:
                # Return provider with status for display
                if status == "not_configured":
                    return False, f"{provider} (not configured)"
                elif status == "not_reachable":
                    return False, f"{provider} (not reachable)"
                elif status == "model_not_found":
                    return False, f"{provider} (model not found)"
                elif status == "connection_failed":
                    return False, f"{provider} (connection failed)"
                else:
                    return False, f"{provider} ({status})"
                    
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        return False, "unknown (API error)"


async def upload_file(file_path: str, filename: str) -> Dict:
    """
    Upload a file to the API.
    
    Args:
        file_path: Local path to the file
        filename: Name for the uploaded file
        
    Returns:
        Upload response from API
    """
    async with httpx.AsyncClient(timeout=API_TIMEOUT_UPLOAD) as client:
        with open(file_path, 'rb') as f:
            files_data = {'file': (filename, f, 'text/csv')}
            response = await client.post(
                f"{API_BASE_URL}{API_PREFIX}/data/upload",
                files=files_data
            )
            response.raise_for_status()
            return response.json()


def get_api_base_url() -> str:
    """Get the API base URL (for internal API calls)."""
    return API_BASE_URL


def get_api_external_url() -> str:
    """
    Get the external API URL (for browser download links).
    
    Returns:
        - Empty string if set to "relative" or "" (for use behind reverse proxy)
        - Full URL otherwise (e.g., "http://localhost:8000")
    """
    if API_EXTERNAL_URL.lower() in ("relative", ""):
        return ""  # Use relative URLs
    return API_EXTERNAL_URL


def get_api_prefix() -> str:
    """Get the API prefix."""
    return API_PREFIX
