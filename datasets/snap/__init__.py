"""
SNAP QC Dataset Configuration

Self-contained dataset package for SNAP Quality Control public use data.

DATASET STRUCTURE:
    datasets/snap/
    ├── __init__.py           # This file - dataset configuration
    ├── config.yaml           # Dataset metadata
    ├── data_mapping.json     # Code lookups for Vanna training
    ├── query_examples.json   # Example queries for Vanna training
    ├── reference.txt         # Source documentation (FNS codebook)
    └── data/                 # CSV data files
        └── qc_pub_fy2023.csv

The SNAP dataset includes:
- Household-level data (households table)
- Person-level data (household_members table)
- QC error findings (qc_errors table)
- 25+ reference/lookup tables (ref_* tables)
"""

from pathlib import Path

from datasets.base import DatasetConfig


class SnapDatasetConfig(DatasetConfig):
    """
    Configuration for the SNAP QC public use dataset.

    This wraps all existing SNAP-specific code without modification.
    Models, transformers, and mappings are imported from their
    current locations in src/.
    """

    # Core identification
    name = "snap"
    display_name = "SNAP QC Public Data"
    description = (
        "FNS SNAP Quality Control public use file. Contains household-level "
        "data, person-level data, and QC error findings for analyzing "
        "SNAP benefit accuracy."
    )
    version = "1.0"

    # PostgreSQL schema name
    # Currently uses 'public' for backward compatibility
    # Can be changed to 'snap' for schema isolation
    schema_name = "public"

    def __init__(self):
        """Initialize SNAP dataset configuration."""
        # Set base path to this module's directory
        super().__init__(base_path=Path(__file__).parent)

    # =========================================================================
    # TABLE NAMES (from existing ddl_extractor.py)
    # =========================================================================

    def get_main_table_names(self) -> list[str]:
        """Get SNAP main table names."""
        return [
            "households",
            "household_members",
            "qc_errors",
        ]

    def get_reference_table_names(self) -> list[str]:
        """Get SNAP reference/lookup table names."""
        # Dynamically discover reference tables using naming convention
        from src.database.ddl_extractor import discover_tables_and_views
        from src.database.engine import engine

        all_tables, _ = discover_tables_and_views(self.schema_name, engine)
        # Reference tables follow ref_* naming convention
        return [t for t in all_tables if t.startswith('ref_')]

    # =========================================================================
    # MODELS (from existing src/database/)
    # =========================================================================

    def get_models_module(self):
        """Get the existing models module."""
        from src.database import models
        return models

    def get_reference_models_module(self):
        """Get the existing reference models module."""
        from src.database import reference_models
        return reference_models

    def get_all_models(self) -> list:
        """Get all SQLAlchemy model classes."""
        models = self.get_models_module()
        ref_models = self.get_reference_models_module()

        return [
            models.Household,
            models.HouseholdMember,
            models.QCError,
            models.DataLoadHistory,
        ] + ref_models.ALL_REFERENCE_MODELS

    # =========================================================================
    # ETL COMPONENTS (from existing src/etl/ and src/utils/)
    # =========================================================================

    def get_column_mapping(self) -> dict[str, dict[str, str]]:
        """Get SNAP column mappings from existing module."""
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
        """Get the existing SNAP DataTransformer class."""
        from src.etl.transformer import DataTransformer
        return DataTransformer

    def get_loader_class(self) -> type:
        """Get the existing ETL loader class."""
        from src.etl.loader import ETLLoader
        return ETLLoader

    # =========================================================================
    # VANNA TRAINING (from existing modules)
    # =========================================================================

    def get_business_context(self) -> str:
        """Get SNAP business context from existing prompts module."""
        from src.core.prompts import BUSINESS_CONTEXT_DOCUMENTATION
        return BUSINESS_CONTEXT_DOCUMENTATION

    def get_data_mapping_path(self) -> Path:
        """
        Get path to data_mapping.json.

        Checks dataset-specific location first, falls back to root.
        """
        # Check dataset-specific location
        dataset_path = self.base_path / "data_mapping.json"
        if dataset_path.exists():
            return dataset_path

        # Fall back to root level (current location)
        root_path = Path("data_mapping.json")
        if root_path.exists():
            return root_path

        raise FileNotFoundError("data_mapping.json not found")

    def get_query_examples_path(self) -> Path:
        """
        Get path to query_examples.json.

        Checks dataset-specific location first, falls back to root.
        """
        # Check dataset-specific location
        dataset_path = self.base_path / "query_examples.json"
        if dataset_path.exists():
            return dataset_path

        # Fall back to root level
        root_path = Path("query_examples.json")
        if root_path.exists():
            return root_path

        raise FileNotFoundError("query_examples.json not found")

    # =========================================================================
    # DDL EXTRACTION (from existing ddl_extractor)
    # =========================================================================

    def get_ddl_statements(self, include_samples: bool = True) -> list[str]:
        """
        Get DDL statements for Vanna training.

        Uses the existing ddl_extractor module.
        """
        from src.database.ddl_extractor import get_all_ddl_statements
        return get_all_ddl_statements(include_samples=include_samples)

    # =========================================================================
    # DATA PATHS
    # =========================================================================

    def get_data_path(self) -> Path:
        """
        Get path to data directory containing CSV files.

        Returns:
            Path to datasets/snap/data/
        """
        return self.base_path / "data"

    def get_reference_doc_path(self) -> Path:
        """
        Get path to reference documentation (FNS codebook).

        Returns:
            Path to datasets/snap/reference.txt
        """
        return self.base_path / "reference.txt"

    def list_data_files(self) -> list[Path]:
        """
        List all CSV data files in the data directory.

        Returns:
            List of paths to CSV files
        """
        data_path = self.get_data_path()
        if data_path.exists():
            return list(data_path.glob("*.csv"))
        return []

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def get_fiscal_years(self) -> list[int]:
        """Get available fiscal years (from config.yaml data_files keys, with data_mapping fallback)."""
        try:
            config_path = self.base_path / "config.yaml"
            if config_path.exists():
                import yaml

                with open(config_path) as f:
                    config = yaml.safe_load(f)
                data_files = config.get("data_files", {})
                if data_files:
                    return sorted(int(y) for y in data_files)
            # Fall back to data_mapping metadata
            mapping = self.load_data_mapping()
            return mapping.get("database", {}).get("fiscal_years_available", [])
        except Exception:
            return []


# Singleton instance for easy access
DATASET_CONFIG = SnapDatasetConfig()


# Convenience exports
def get_config() -> SnapDatasetConfig:
    """Get the SNAP dataset configuration."""
    return DATASET_CONFIG
