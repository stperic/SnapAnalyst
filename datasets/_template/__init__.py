"""
Dataset Configuration Template

Copy this file and customize for your dataset.
Update the class name, attributes, and method implementations.

MINIMAL REQUIREMENTS:
- name: Unique dataset identifier
- schema_name: PostgreSQL schema (use 'public' or custom)
- get_main_table_names(): List of main table names
- get_reference_table_names(): List of reference table names
- get_models_module(): Module containing SQLAlchemy models
- get_column_mapping(): ETL column mappings
- get_transformer_class(): ETL transformer class
- get_business_context(): Business context for Vanna
"""

from pathlib import Path

from datasets.base import DatasetConfig


class YourDatasetConfig(DatasetConfig):
    """
    Configuration for your dataset.

    Replace 'YourDatasetConfig' with your dataset name (e.g., StatePrivateConfig).
    """

    # =========================================================================
    # CORE IDENTIFICATION
    # =========================================================================

    name = "your_dataset_name"  # Must match directory name
    display_name = "Your Dataset Display Name"
    description = "Brief description of the dataset"
    version = "1.0"

    # PostgreSQL schema name ('public' for shared, or custom for isolation)
    schema_name = "public"

    def __init__(self):
        """Initialize dataset configuration."""
        super().__init__(base_path=Path(__file__).parent)

    # =========================================================================
    # TABLE NAMES
    # =========================================================================

    def get_main_table_names(self) -> list[str]:
        """List of main data table names."""
        return [
            "your_main_table",
            # Add more tables...
        ]

    def get_reference_table_names(self) -> list[str]:
        """List of reference/lookup table names."""
        return [
            "ref_your_lookup_1",
            # Add more reference tables...
        ]

    # =========================================================================
    # MODELS
    # =========================================================================

    def get_models_module(self):
        """Get the module containing SQLAlchemy models."""
        # Option 1: Use models in this dataset directory
        # from datasets.your_dataset_name import models
        # return models

        # Option 2: Reuse existing models (if schema matches)
        from src.database import models

        return models

    def get_reference_models_module(self):
        """Get the module containing reference table models."""
        # Option 1: Dataset-specific reference models
        # from datasets.your_dataset_name import reference_models
        # return reference_models

        # Option 2: Reuse existing reference models
        from src.database import reference_models

        return reference_models

    # =========================================================================
    # ETL COMPONENTS
    # =========================================================================

    def get_column_mapping(self) -> dict[str, dict[str, str]]:
        """
        Get column mapping for ETL.

        Maps source CSV columns to database columns.
        """
        # Option 1: Dataset-specific mappings
        # from datasets.your_dataset_name.column_mapping import (
        #     MAIN_VARIABLES,
        #     RELATED_VARIABLES,
        # )
        # return {
        #     "main": MAIN_VARIABLES,
        #     "related": RELATED_VARIABLES,
        # }

        # Option 2: Reuse existing mappings
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
        """Get the DataTransformer class for ETL."""
        # Option 1: Dataset-specific transformer
        # from datasets.your_dataset_name.transformer import DataTransformer
        # return DataTransformer

        # Option 2: Reuse existing transformer
        from src.etl.transformer import DataTransformer

        return DataTransformer

    # =========================================================================
    # VANNA TRAINING
    # =========================================================================

    def get_business_context(self) -> str:
        """
        Get business context documentation for Vanna training.

        Describe your data's business meaning, terminology, and query patterns.
        """
        return """
Your Dataset - Business Context

TERMINOLOGY:
- TERM1: Definition of term 1
- TERM2: Definition of term 2

TABLE STRUCTURE:
- your_main_table: Description of main table
- ref_your_lookup_1: Lookup table for XYZ codes

COMMON QUERY PATTERNS:
1. Query pattern 1:
   SELECT ... FROM your_main_table WHERE ...

2. Query pattern 2:
   SELECT ... FROM your_main_table
   JOIN ref_your_lookup_1 ON ...
"""


# Singleton instance for easy access
DATASET_CONFIG = YourDatasetConfig()


def get_config() -> YourDatasetConfig:
    """Get the dataset configuration."""
    return DATASET_CONFIG
