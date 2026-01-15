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
    Check LLM service health.
    
    Returns:
        Tuple of (is_available, provider_name)
    """
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT_HEALTH) as client:
            response = await client.get(f"{API_BASE_URL}/api/v1/chat/provider")
            provider_info = response.json()
            llm_provider = provider_info.get('provider', 'Unknown').upper()
            
            if llm_provider and llm_provider != 'UNKNOWN':
                return True, llm_provider
            return False, "unknown"
    except Exception as e:
        logger.error(f"LLM service check failed: {e}")
        return False, "unknown"


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
    """Get the API base URL."""
    return API_BASE_URL


def get_api_prefix() -> str:
    """Get the API prefix."""
    return API_PREFIX
