"""
Base Dataset Configuration

Abstract base class for dataset configurations. Each dataset (SNAP, state private, etc.)
should have a configuration that implements this interface.

This provides a uniform way to:
- Access dataset metadata
- Load models and reference tables
- Get ETL components
- Get Vanna training materials
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml


class DatasetConfig(ABC):
    """
    Abstract base configuration for a dataset.

    Each dataset implementation provides its own config subclass
    that knows how to load its specific models, mappings, and training data.
    """

    # Core identification
    name: str = ""
    display_name: str = ""
    description: str = ""
    version: str = "1.0"

    # PostgreSQL schema name (for namespace isolation)
    schema_name: str = "public"

    # Path to dataset directory
    base_path: Path = None

    def __init__(self, base_path: Path = None):
        """
        Initialize dataset configuration.

        Args:
            base_path: Path to dataset directory (auto-detected if not provided)
        """
        if base_path:
            self.base_path = Path(base_path)
        elif self.base_path is None:
            # Default to module's directory
            self.base_path = Path(__file__).parent / self.name

    # =========================================================================
    # METADATA
    # =========================================================================

    def get_info(self) -> dict[str, Any]:
        """Get dataset metadata as dictionary."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "schema": self.schema_name,
            "base_path": str(self.base_path),
        }

    # =========================================================================
    # DATA MAPPING (Code Lookups)
    # =========================================================================

    def get_data_mapping_path(self) -> Path:
        """Get path to data_mapping.json file."""
        # Check dataset-specific location first
        dataset_path = self.base_path / "data_mapping.json"
        if dataset_path.exists():
            return dataset_path
        # Fall back to root level (backward compatibility)
        root_path = Path("data_mapping.json")
        if root_path.exists():
            return root_path
        raise FileNotFoundError(f"data_mapping.json not found for dataset {self.name}")

    def load_data_mapping(self) -> dict[str, Any]:
        """Load data mapping (code lookups) from JSON."""
        path = self.get_data_mapping_path()
        with open(path) as f:
            return json.load(f)

    def get_code_lookups(self) -> dict[str, Any]:
        """Get code lookup definitions."""
        mapping = self.load_data_mapping()
        return mapping.get("code_lookups", {})

    # =========================================================================
    # QUERY EXAMPLES (Vanna Training)
    # =========================================================================

    def get_query_examples_path(self) -> Path:
        """Get path to query_examples.json file."""
        # Check dataset-specific location first
        dataset_path = self.base_path / "query_examples.json"
        if dataset_path.exists():
            return dataset_path
        # Fall back to root level
        root_path = Path("query_examples.json")
        if root_path.exists():
            return root_path
        raise FileNotFoundError(f"query_examples.json not found for dataset {self.name}")

    def load_query_examples(self) -> list[dict[str, str]]:
        """Load query examples for Vanna training."""
        path = self.get_query_examples_path()
        with open(path) as f:
            data = json.load(f)
        return data.get("example_queries", [])

    # =========================================================================
    # DATABASE MODELS (Abstract - implemented by each dataset)
    # =========================================================================

    @abstractmethod
    def get_main_table_names(self) -> list[str]:
        """Get list of main table names (e.g., ['households', 'household_members'])."""
        pass

    @abstractmethod
    def get_reference_table_names(self) -> list[str]:
        """Get list of reference/lookup table names (e.g., ['ref_status', 'ref_element'])."""
        pass

    def get_all_table_names(self) -> list[str]:
        """Get all table names (reference tables first for FK order)."""
        return self.get_reference_table_names() + self.get_main_table_names()

    @abstractmethod
    def get_models_module(self):
        """Get the module containing SQLAlchemy models."""
        pass

    @abstractmethod
    def get_reference_models_module(self):
        """Get the module containing reference table models."""
        pass

    # =========================================================================
    # ETL COMPONENTS (Abstract - implemented by each dataset)
    # =========================================================================

    @abstractmethod
    def get_column_mapping(self) -> dict[str, dict[str, str]]:
        """
        Get column mapping for ETL.

        Returns dict with keys like 'household', 'person', 'error'
        mapping source columns to target columns.
        """
        pass

    @abstractmethod
    def get_transformer_class(self) -> type:
        """Get the DataTransformer class for this dataset."""
        pass

    # =========================================================================
    # BUSINESS CONTEXT (Vanna Training)
    # =========================================================================

    @abstractmethod
    def get_business_context(self) -> str:
        """Get business context documentation for Vanna training."""
        pass

    # =========================================================================
    # SCHEMA OPERATIONS
    # =========================================================================

    def get_schema_prefix(self) -> str:
        """Get SQL prefix for schema-qualified table names."""
        if self.schema_name and self.schema_name != "public":
            return f"{self.schema_name}."
        return ""

    def qualify_table_name(self, table_name: str) -> str:
        """Get fully qualified table name with schema prefix."""
        return f"{self.get_schema_prefix()}{table_name}"


class DatasetConfigFromYAML(DatasetConfig):
    """
    Dataset configuration loaded from YAML file.

    This allows defining new datasets without writing Python code
    (though they still need models and transformers).
    """

    def __init__(self, config_path: Path):
        """
        Load dataset configuration from YAML file.

        Args:
            config_path: Path to config.yaml file
        """
        self.config_path = Path(config_path)
        self.base_path = self.config_path.parent

        with open(config_path) as f:
            self._config = yaml.safe_load(f)

        # Set core attributes from YAML
        self.name = self._config.get("name", self.base_path.name)
        self.display_name = self._config.get("display_name", self.name)
        self.description = self._config.get("description", "")
        self.version = self._config.get("version", "1.0")
        self.schema_name = self._config.get("schema", "public")

    def get_main_table_names(self) -> list[str]:
        tables = self._config.get("tables", {})
        main_tables = [tables.get("primary", "")]
        main_tables.extend(tables.get("related", []))
        return [t for t in main_tables if t]

    def get_reference_table_names(self) -> list[str]:
        return self._config.get("reference_tables", [])

    def get_models_module(self):
        # Import dynamically based on dataset name
        import importlib
        try:
            return importlib.import_module(f"datasets.{self.name}.models")
        except ImportError:
            # Fall back to src.database.models for backward compatibility
            return importlib.import_module("src.database.models")

    def get_reference_models_module(self):
        import importlib
        try:
            return importlib.import_module(f"datasets.{self.name}.reference_models")
        except ImportError:
            return importlib.import_module("src.database.reference_models")

    def get_column_mapping(self) -> dict[str, dict[str, str]]:
        import importlib
        try:
            mapping_module = importlib.import_module(f"datasets.{self.name}.column_mapping")
            return {
                "household": getattr(mapping_module, "HOUSEHOLD_LEVEL_VARIABLES", {}),
                "person": getattr(mapping_module, "PERSON_LEVEL_VARIABLES", {}),
                "error": getattr(mapping_module, "ERROR_LEVEL_VARIABLES", {}),
            }
        except ImportError:
            from src.utils.column_mapping import (
                ERROR_LEVEL_VARIABLES,
                HOUSEHOLD_LEVEL_VARIABLES,
                PERSON_LEVEL_VARIABLES,
            )
            return {
                "household": HOUSEHOLD_LEVEL_VARIABLES,
                "person": PERSON_LEVEL_VARIABLES,
                "error": ERROR_LEVEL_VARIABLES,
            }

    def get_transformer_class(self) -> type:
        import importlib
        try:
            transformer_module = importlib.import_module(f"datasets.{self.name}.transformer")
            return transformer_module.DataTransformer
        except ImportError:
            from src.etl.transformer import DataTransformer
            return DataTransformer

    def get_business_context(self) -> str:
        import importlib
        try:
            prompts_module = importlib.import_module(f"datasets.{self.name}.prompts")
            return prompts_module.BUSINESS_CONTEXT_DOCUMENTATION
        except ImportError:
            from src.core.prompts import BUSINESS_CONTEXT_DOCUMENTATION
            return BUSINESS_CONTEXT_DOCUMENTATION
