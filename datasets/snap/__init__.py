"""
SNAP QC Dataset Configuration

Self-contained dataset package for SNAP Quality Control public use data.

DATASET STRUCTURE:
    datasets/snap/
    ├── __init__.py           # This file - dataset configuration
    ├── config.yaml           # Dataset metadata
    ├── data_mapping.json     # Code lookups for enrichment (numeric codes → descriptions)
    ├── training/             # Training data (configurable via SQL_TRAINING_DATA_PATH)
    │   ├── business_context.md   # Business terms, query patterns, table relationships
    │   └── query_examples.json   # Example question/SQL pairs ({example_queries: [...]})
    ├── prompts/              # System prompts (configurable via SYSTEM_PROMPTS_PATH)
    │   ├── sql_system_prompt.txt # SQL generation system prompt (domain-specific)
    │   └── kb_system_prompt.txt  # KB insight system prompt (domain-specific)
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
    # EXPORT / IDENTITY
    # =========================================================================

    def get_anonymous_email(self) -> str:
        return "anonymous@snapanalyst.com"

    def get_export_prefix(self) -> str:
        return "snapanalyst"

    def get_code_lookup_names(self) -> list[str]:
        return [
            "case_classification_codes",
            "status_codes",
            "expedited_service_codes",
            "categorical_eligibility_codes",
            "error_finding_codes",
            "sex_codes",
            "snap_affiliation_codes",
            "element_codes",
            "nature_codes",
            "agency_responsibility_codes",
            "discovery_method_codes",
        ]

    def get_table_descriptions(self) -> dict[str, str]:
        return {
            "households": "Household case data (~50k rows per year)",
            "household_members": "Individual household member data (~120k rows)",
            "qc_errors": "Quality control errors/variances (~20k rows)",
        }

    def get_starter_prompts(self) -> list[dict[str, str]]:
        return [
            {
                "label": "Payment Error Rates",
                "message": "What is the payment error rate by state for FY2023, including overpayment and underpayment rates?",
            },
            {
                "label": "Top Overpayment Drivers",
                "message": (
                    "Which error elements drive the most overpayment dollars in FY2023? "
                    "Rank by weighted dollar impact for corrective action prioritization."
                ),
            },
            {
                "label": "Year-over-Year Trends",
                "message": "Which states improved their payment error rate from FY2022 to FY2023, and by how much?",
            },
            {
                "label": "Corrective Action ROI",
                "message": (
                    "Rank each error element by its contribution to the FY2023 overpayment rate "
                    "with cumulative impact, so I can see which errors to fix first."
                ),
            },
        ]

    def get_filter_dimensions(self) -> list[dict]:
        return [
            {"name": "state", "column": "state_name", "table": "households", "join_column": "case_id", "type": "string"},
            {"name": "fiscal_year", "column": "fiscal_year", "table": "*", "type": "integer"},
        ]

    def get_model_classes(self) -> dict[str, type]:
        from src.database.models import Household, HouseholdMember, QCError

        return {"households": Household, "household_members": HouseholdMember, "qc_errors": QCError}

    # =========================================================================
    # UI / PRESENTATION
    # =========================================================================

    def get_personas(self) -> dict[str, str]:
        """Get SNAP-specific persona names."""
        return {"app": "SnapAnalyst", "ai": "SnapAnalyst AI"}

    def get_example_questions(self) -> list[str]:
        """Get SNAP-specific example questions."""
        return [
            "How many households received SNAP benefits in 2023?",
            "What is the average SNAP benefit amount by state?",
            "Show me the top 10 states by total SNAP recipients",
            "How many households have children under 5?",
            "What percentage of households are elderly?",
            "What are the most common error types in QC reviews?",
            "Show me households with income between $1000 and $2000",
            "How many households received expedited service?",
            "What is the average household size by region?",
            "Show me error rates by state",
            "How many households have disabled members?",
            "What is the distribution of SNAP benefits by household composition?",
            "Show me households with overissuance errors",
            "What percentage of households pass all income tests?",
            "How many households receive the minimum benefit?",
        ]

    def get_no_results_message(self) -> str:
        """Get SNAP-specific no-results message."""
        return "No matching SNAP QC records found. Try adjusting your filters or rephrasing your question."

    # =========================================================================
    # CODE ENRICHMENT
    # =========================================================================

    def get_code_column_mappings(self) -> dict[str, str]:
        """Map SNAP result column names to lookup keys in data_mapping.json."""
        return {
            "element_code": "element_codes",
            "nature_code": "nature_codes",
            "status": "status_codes",
            "error_finding": "error_finding_codes",
            "case_classification": "case_classification_codes",
            "expedited_service": "expedited_service_codes",
            "categorical_eligibility": "categorical_eligibility_codes",
            "sex": "sex_codes",
            "snap_affiliation_code": "snap_affiliation_codes",
            "agency_responsibility": "agency_responsibility_codes",
            "discovery_method": "discovery_method_codes",
        }

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
        return [t for t in all_tables if t.startswith("ref_")]

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
        """Get SNAP business context from the training data folder."""
        doc_path = self.base_path / "training" / "business_context.md"
        if doc_path.exists():
            return doc_path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Business context not found: {doc_path}")

    def get_documentation_files(self) -> list[Path]:
        """
        Get all documentation files for Vanna training.

        Scans the training/ subfolder for .md and .txt files.
        """
        training_dir = self.base_path / "training"
        if not training_dir.exists():
            return []
        return sorted(training_dir.glob("*.md")) + sorted(training_dir.glob("*.txt"))

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

        Checks training/ subfolder first, then dataset root, then project root.
        """
        # Check training subfolder first (new canonical location)
        training_path = self.base_path / "training" / "query_examples.json"
        if training_path.exists():
            return training_path

        # Fall back to dataset root (backward compatibility)
        dataset_path = self.base_path / "query_examples.json"
        if dataset_path.exists():
            return dataset_path

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
