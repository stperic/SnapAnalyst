"""
Dataset Registry

Central registry for discovering and managing available datasets.
Provides singleton access to dataset configurations.

DESIGN PRINCIPLES:
- Auto-discovery: Scans datasets/ directory for config.yaml files
- Singleton: One registry instance shared across the application
- Backward Compatible: Default dataset is 'snap' if not specified
- Lazy Loading: Datasets are loaded on first access

Usage:
    from datasets import get_registry, get_dataset, get_active_dataset

    # Get all available datasets
    registry = get_registry()
    for name in registry.list_datasets():
        print(f"Available: {name}")

    # Get specific dataset config
    snap = get_dataset('snap')

    # Get currently active dataset (from settings or default)
    active = get_active_dataset()
"""

import os
from pathlib import Path
from typing import Optional

from datasets.base import DatasetConfig, DatasetConfigFromYAML

# Module-level singleton
_registry: Optional["DatasetRegistry"] = None

# Default dataset when none specified
DEFAULT_DATASET = "snap"


class DatasetRegistry:
    """
    Registry for managing available datasets.

    Discovers datasets by scanning for config.yaml files in the datasets directory.
    Each dataset with a valid config.yaml is registered automatically.
    """

    def __init__(self, datasets_dir: Path = None, auto_discover: bool = True):
        """
        Initialize the registry.

        Args:
            datasets_dir: Base directory containing dataset folders
            auto_discover: Automatically scan for datasets (default True)
        """
        if datasets_dir is None:
            # Default to datasets/ relative to this file
            datasets_dir = Path(__file__).parent

        self.datasets_dir = Path(datasets_dir)
        self._datasets: dict[str, DatasetConfig] = {}
        self._active_dataset: str | None = None

        if auto_discover:
            self._discover_datasets()

    def _discover_datasets(self) -> None:
        """
        Auto-discover datasets by scanning for Python modules and config.yaml files.

        Priority: Python modules (DATASET_CONFIG) > YAML config files
        Python modules have more functionality and should take precedence.

        Skips directories starting with underscore (e.g., _template, __pycache__).
        """
        # Method 1: Look for Python modules with DATASET_CONFIG (preferred)
        for init_file in self.datasets_dir.glob("*/__init__.py"):
            dataset_name = init_file.parent.name
            if dataset_name.startswith("_"):
                continue  # Skip __pycache__, _template, etc.

            try:
                import importlib
                module = importlib.import_module(f"datasets.{dataset_name}")
                if hasattr(module, "DATASET_CONFIG"):
                    config = module.DATASET_CONFIG
                    if isinstance(config, DatasetConfig):
                        self._datasets[config.name] = config
            except ImportError:
                pass  # Module may not define DATASET_CONFIG

        # Method 2: Look for config.yaml files (fallback for datasets without Python code)
        for config_file in self.datasets_dir.glob("*/config.yaml"):
            # Skip template and private directories
            if config_file.parent.name.startswith("_"):
                continue

            # Skip if already loaded from Python module
            dataset_name = config_file.parent.name
            if dataset_name in self._datasets:
                continue

            try:
                dataset = DatasetConfigFromYAML(config_file)
                self._datasets[dataset.name] = dataset
            except Exception as e:
                # Log but don't fail - some configs may be invalid
                import logging
                logging.getLogger(__name__).warning(
                    f"Failed to load dataset from {config_file}: {e}"
                )

    def register(self, config: DatasetConfig) -> None:
        """
        Manually register a dataset configuration.

        Args:
            config: DatasetConfig instance to register
        """
        self._datasets[config.name] = config

    def get(self, name: str) -> DatasetConfig | None:
        """
        Get a dataset configuration by name.

        Args:
            name: Dataset name (e.g., 'snap')

        Returns:
            DatasetConfig or None if not found
        """
        return self._datasets.get(name)

    def list_datasets(self) -> list[str]:
        """
        List all registered dataset names.

        Returns:
            List of dataset names
        """
        return list(self._datasets.keys())

    def get_all(self) -> dict[str, DatasetConfig]:
        """
        Get all registered datasets.

        Returns:
            Dict mapping names to DatasetConfig instances
        """
        return dict(self._datasets)

    @property
    def active_dataset(self) -> str:
        """
        Get the currently active dataset name.

        Falls back to DEFAULT_DATASET if not explicitly set.
        Can be overridden by ACTIVE_DATASET environment variable.
        """
        # Check for override from environment
        env_dataset = os.environ.get("ACTIVE_DATASET")
        if env_dataset and env_dataset in self._datasets:
            return env_dataset

        # Use explicitly set dataset or default
        if self._active_dataset and self._active_dataset in self._datasets:
            return self._active_dataset

        return DEFAULT_DATASET

    @active_dataset.setter
    def active_dataset(self, name: str) -> None:
        """Set the active dataset."""
        if name not in self._datasets:
            raise ValueError(f"Unknown dataset: {name}. Available: {self.list_datasets()}")
        self._active_dataset = name

    def get_active(self) -> DatasetConfig | None:
        """
        Get the currently active dataset configuration.

        Returns:
            Active DatasetConfig or None
        """
        return self.get(self.active_dataset)


# =============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# =============================================================================

def get_registry() -> DatasetRegistry:
    """
    Get the singleton DatasetRegistry instance.

    Creates the registry on first call, reuses on subsequent calls.

    Returns:
        DatasetRegistry singleton
    """
    global _registry
    if _registry is None:
        _registry = DatasetRegistry()
    return _registry


def get_dataset(name: str) -> DatasetConfig | None:
    """
    Get a dataset configuration by name.

    Args:
        name: Dataset name (e.g., 'snap')

    Returns:
        DatasetConfig or None if not found
    """
    return get_registry().get(name)


def get_active_dataset() -> DatasetConfig | None:
    """
    Get the currently active dataset configuration.

    Returns:
        Active DatasetConfig (defaults to 'snap')
    """
    return get_registry().get_active()


def set_active_dataset(name: str) -> None:
    """
    Set the active dataset.

    Args:
        name: Dataset name to activate

    Raises:
        ValueError: If dataset not found
    """
    get_registry().active_dataset = name


def list_datasets() -> list[str]:
    """
    List all available dataset names.

    Returns:
        List of dataset names
    """
    return get_registry().list_datasets()
