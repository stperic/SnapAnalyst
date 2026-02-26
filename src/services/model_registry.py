"""
Model Registry Service

Loads LiteLLM's model_prices_and_context_window.json to provide
context window and max output token info for any model.

Singleton: call get_model_info() / get_context_window() / get_max_output_tokens() directly.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

REGISTRY_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
REGISTRY_PATH = Path("datasets/snap/model_registry.json")
# In Docker the datasets live under /app
REGISTRY_PATH_DOCKER = Path("/app/datasets/snap/model_registry.json")
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60  # 24 hours

_registry: dict | None = None


def _resolve_path() -> Path:
    """Return the registry file path, preferring Docker path if it exists."""
    if REGISTRY_PATH_DOCKER.parent.exists():
        return REGISTRY_PATH_DOCKER
    return REGISTRY_PATH


def _is_stale(path: Path) -> bool:
    """Check if the registry file is missing or older than 24 hours."""
    if not path.exists():
        return True
    age = time.time() - path.stat().st_mtime
    return age > CACHE_MAX_AGE_SECONDS


def download_model_registry(force: bool = False) -> bool:
    """
    Download the LiteLLM model registry JSON.

    Args:
        force: Download even if cache is fresh

    Returns:
        True if download succeeded or file is already fresh
    """
    path = _resolve_path()

    if not force and not _is_stale(path):
        logger.debug("Model registry cache is fresh, skipping download")
        return True

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Downloading model registry from {REGISTRY_URL}")
        urllib.request.urlretrieve(REGISTRY_URL, str(path))
        size_kb = path.stat().st_size / 1024
        logger.debug(f"Model registry downloaded ({size_kb:.0f} KB)")
        # Invalidate in-memory cache
        global _registry
        _registry = None
        return True
    except Exception as e:
        logger.warning(f"Failed to download model registry: {e}")
        return False


def load_registry() -> dict:
    """
    Load the model registry into memory (singleton).

    Auto-downloads if file is missing or stale.
    """
    global _registry
    if _registry is not None:
        return _registry

    path = _resolve_path()

    # Auto-download if missing or stale
    if _is_stale(path):
        download_model_registry()

    if not path.exists():
        logger.warning("Model registry file not available")
        _registry = {}
        return _registry

    try:
        with open(path) as f:
            _registry = json.load(f)
        logger.debug(f"Loaded model registry with {len(_registry)} entries")
    except Exception as e:
        logger.warning(f"Failed to load model registry: {e}")
        _registry = {}

    return _registry


def get_model_info(model_name: str) -> dict | None:
    """
    Look up model info by name.

    Tries exact match first, then common provider/model variants.

    Args:
        model_name: Model name (e.g. "gpt-4.1", "claude-sonnet-4-20250514")

    Returns:
        Model info dict or None if not found
    """
    registry = load_registry()
    if not registry:
        return None

    # Exact match
    if model_name in registry:
        return registry[model_name]

    # Try common provider prefixes
    prefixes = ["openai/", "anthropic/", "azure/", "ollama/", "azure_ai/"]
    for prefix in prefixes:
        key = f"{prefix}{model_name}"
        if key in registry:
            return registry[key]

    # Try without provider prefix (if model_name has one)
    if "/" in model_name:
        bare = model_name.split("/", 1)[1]
        if bare in registry:
            return registry[bare]

    # Ollama fallback: query the Ollama API
    if settings.llm_provider == "ollama" or model_name.startswith("ollama/"):
        return _ollama_model_info(model_name.replace("ollama/", ""))

    return None


def get_context_window(model_name: str) -> int | None:
    """Get the max input tokens (context window) for a model."""
    info = get_model_info(model_name)
    if info is None:
        return None
    return info.get("max_input_tokens") or info.get("max_tokens")


def get_max_output_tokens(model_name: str) -> int | None:
    """Get the max output tokens for a model."""
    info = get_model_info(model_name)
    if info is None:
        return None
    return info.get("max_output_tokens")


def _ollama_model_info(model_name: str) -> dict | None:
    """
    Query Ollama's /api/show endpoint for model info.

    Returns a dict compatible with the LiteLLM registry format.
    """
    try:
        url = f"{settings.ollama_base_url}/api/show"
        data = json.dumps({"name": model_name}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())

        # Extract context length from model info
        params = result.get("model_info", {})
        # Ollama returns various parameter keys
        context_length = None
        for key in params:
            if "context_length" in key:
                context_length = params[key]
                break

        if context_length:
            return {
                "max_input_tokens": context_length,
                "max_output_tokens": context_length,
                "source": "ollama",
            }
    except Exception as e:
        logger.debug(f"Ollama model info lookup failed for {model_name}: {e}")

    return None
