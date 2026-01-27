"""
SnapAnalyst Database Package

GOLD STANDARD ARCHITECTURE for Vanna.ai:
-----------------------------------------
This package implements the "Gold Standard" pattern where:

1. DATABASE IS THE SOURCE OF TRUTH:
   - PostgreSQL schema is THE source of truth for all DDL
   - DDL is extracted from database (not maintained in code)
   - Use ddl_extractor.get_all_ddl_statements() for Vanna training

2. FOREIGN KEY CONSTRAINTS:
   - Main tables (households, household_members, qc_errors) have FK constraints
   - FK constraints point to reference tables (ref_*)
   - Vanna sees these FKs and generates proper JOINs automatically

3. REFERENCE TABLES:
   - data_mapping.json is the source of truth for code definitions
   - Reference tables (ref_*) store code→description mappings
   - Populated from JSON using populate_references.py

4. INITIALIZATION ORDER (CRITICAL):
   - Reference tables MUST be created and populated FIRST
   - Then main tables can be created (they reference ref_* tables)
   - Use init_database.initialize_database() for correct order

MULTI-DATASET ARCHITECTURE:
---------------------------
This package supports multiple datasets with schema isolation:

1. Each dataset can have its own PostgreSQL schema (namespace)
2. Dataset configurations live in the datasets/ package
3. Use get_engine_for_dataset() for dataset-specific connections
4. DDL extraction supports dataset-aware table lists

Usage:
    # Initialize database with reference data
    from src.database.init_database import initialize_database
    initialize_database()

    # Get DDL for Vanna training (from actual database)
    from src.database.ddl_extractor import get_all_ddl_statements
    ddl_statements = get_all_ddl_statements()

    # Get DDL for specific dataset
    ddl_statements = get_all_ddl_statements(dataset_name='snap')

    # Access models
    from src.database.models import Household, HouseholdMember, QCError
    from src.database.reference_models import RefElement, RefNature

    # Get database engine/session (default)
    from src.database.engine import engine, get_db_context

    # Get engine for specific dataset
    from src.database.engine import get_engine_for_dataset
    snap_engine = get_engine_for_dataset('snap')
"""

from src.database.engine import (
    Base,
    engine,
    get_active_engine,
    get_engine_for_dataset,
    get_session_for_dataset,
)

__all__ = [
    "engine",
    "Base",
    "get_engine_for_dataset",
    "get_active_engine",
    "get_session_for_dataset",
]
