"""
Populate Reference Tables from data_mapping.json

This script reads the single source of truth (data_mapping.json) and
populates all reference/lookup tables in the database.

Usage:
    python -m src.database.populate_references

    # Or from code:
    from src.database.populate_references import populate_all_references
    populate_all_references()

Architecture:
    - data_mapping.json is the SINGLE SOURCE OF TRUTH for all code definitions
    - This script transforms JSON → database rows
    - Reference tables enable Vanna.ai to generate JOINs instead of hardcoding values
"""

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.engine import Base, engine
from src.database.reference_models import (
    ALL_REFERENCE_MODELS,
    # New reference tables
    RefAbawdStatus,
    RefActionType,
    RefAgencyResponsibility,
    RefAllotmentAdjustment,
    RefCaseClassification,
    RefCategoricalEligibility,
    RefCitizenshipStatus,
    RefDisability,
    RefDiscovery,
    RefEducationLevel,
    RefElement,
    RefEmploymentStatusType,
    RefErrorFinding,
    RefExpeditedService,
    RefHomelessness,
    RefNature,
    RefRaceEthnicity,
    RefRelationship,
    RefReportingSystem,
    RefSex,
    RefSnapAffiliation,
    RefState,
    RefStatus,
    RefWorkingIndicator,
    RefWorkRegistration,
)

logger = logging.getLogger(__name__)

# Path to the single source of truth (now in datasets/snap/)
DATA_MAPPING_PATH = Path(__file__).parent.parent.parent / "datasets" / "snap" / "data_mapping.json"


def load_data_mapping() -> dict[str, Any]:
    """Load the data mapping JSON file."""
    if not DATA_MAPPING_PATH.exists():
        raise FileNotFoundError(f"Data mapping file not found: {DATA_MAPPING_PATH}")

    with open(DATA_MAPPING_PATH) as f:
        return json.load(f)


def get_element_category(code: int, categories: dict) -> str | None:
    """Determine the category for an element code."""
    for category_name, codes in categories.items():
        # Skip non-list values (e.g., metadata fields)
        if not isinstance(codes, (list, tuple, set)):
            continue
        if code in codes:
            return category_name
    return None


def get_responsibility_type(code: int, types: dict) -> str | None:
    """Determine the responsibility type (client/agency) for a code."""
    for type_name, codes in types.items():
        # Skip non-list values (e.g., metadata fields)
        if not isinstance(codes, (list, tuple, set)):
            continue
        if code in codes:
            return type_name
    return None


def populate_simple_codes(
    session: Session,
    model_class: type,
    codes_dict: dict[str, str],
) -> int:
    """
    Populate a simple code→description reference table.

    Args:
        session: Database session
        model_class: SQLAlchemy model class
        codes_dict: Dictionary with code keys and description values

    Returns:
        Number of records inserted
    """
    count = 0
    for key, value in codes_dict.items():
        # Skip metadata keys
        if key in ("description", "source_field"):
            continue

        try:
            code = int(key)
            description = value if isinstance(value, str) else str(value)

            # Check if exists
            existing = session.get(model_class, code)
            if existing:
                existing.description = description
            else:
                record = model_class(code=code, description=description)
                session.add(record)
            count += 1
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid code '{key}': {e}")

    return count


def populate_element_codes(session: Session, data: dict) -> int:
    """Populate element codes with category information."""
    element_codes = data["code_lookups"]["element_codes"]
    categories = data["code_lookups"].get("element_categories", {})

    count = 0
    for key, description in element_codes.items():
        if key in ("description", "source_field"):
            continue

        try:
            code = int(key)
            category = get_element_category(code, categories)

            existing = session.get(RefElement, code)
            if existing:
                existing.description = description
                existing.category = category
            else:
                record = RefElement(code=code, description=description, category=category)
                session.add(record)
            count += 1
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid element code '{key}': {e}")

    return count


def populate_nature_codes(session: Session, data: dict) -> int:
    """Populate nature codes with category information."""
    nature_codes = data["code_lookups"]["nature_codes"]

    # Derive categories from the nature of each code
    def get_nature_category(code: int, desc: str) -> str | None:
        desc_lower = desc.lower()
        if "income" in desc_lower or "earnings" in desc_lower:
            return "income"
        elif "person" in desc_lower or "member" in desc_lower or "noncitizen" in desc_lower:
            return "composition"
        elif "deduction" in desc_lower:
            return "deduction"
        elif "resource" in desc_lower:
            return "resources"
        elif "computation" in desc_lower or "transcription" in desc_lower or "rounding" in desc_lower:
            return "computation"
        elif "reporting" in desc_lower or "budgeting" in desc_lower:
            return "reporting"
        elif "benefit" in desc_lower or "allotment" in desc_lower or "prorat" in desc_lower:
            return "benefits"
        return None

    count = 0
    for key, description in nature_codes.items():
        if key in ("description", "source_field"):
            continue

        try:
            code = int(key)
            category = get_nature_category(code, description)

            existing = session.get(RefNature, code)
            if existing:
                existing.description = description
                existing.category = category
            else:
                record = RefNature(code=code, description=description, category=category)
                session.add(record)
            count += 1
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid nature code '{key}': {e}")

    return count


def populate_agency_responsibility(session: Session, data: dict) -> int:
    """Populate agency responsibility codes with type classification."""
    agency_codes = data["code_lookups"]["agency_responsibility_codes"]
    types = data["code_lookups"].get("agency_responsibility_types", {})

    count = 0
    for key, description in agency_codes.items():
        if key in ("description", "source_field"):
            continue

        try:
            code = int(key)
            resp_type = get_responsibility_type(code, types)

            existing = session.get(RefAgencyResponsibility, code)
            if existing:
                existing.description = description
                existing.responsibility_type = resp_type
            else:
                record = RefAgencyResponsibility(
                    code=code,
                    description=description,
                    responsibility_type=resp_type
                )
                session.add(record)
            count += 1
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid agency code '{key}': {e}")

    return count


def populate_states(session: Session, data: dict) -> int:
    """Populate state reference table from state_codes."""
    state_codes = data["code_lookups"].get("state_codes", {})

    count = 0
    for key, value in state_codes.items():
        if key in ("description", "source_field"):
            continue

        try:
            fips_code = int(key)

            if isinstance(value, dict):
                state_name = value.get("name", "")
                abbreviation = value.get("abbr", "")
            else:
                state_name = str(value)
                abbreviation = None

            existing = session.get(RefState, fips_code)
            if existing:
                existing.state_name = state_name
                existing.abbreviation = abbreviation
            else:
                record = RefState(
                    fips_code=fips_code,
                    state_name=state_name,
                    abbreviation=abbreviation
                )
                session.add(record)
            count += 1
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid state code '{key}': {e}")

    return count


def create_reference_tables():
    """Create all reference tables if they don't exist."""
    # Import all models to register them
    from src.database import reference_models  # noqa

    # Create tables
    Base.metadata.create_all(engine, tables=[
        model.__table__ for model in ALL_REFERENCE_MODELS
    ])
    logger.info("Reference tables created/verified")


def populate_all_references(drop_existing: bool = False) -> dict[str, int]:
    """
    Populate all reference tables from data_mapping.json.

    Args:
        drop_existing: If True, truncate tables before populating

    Returns:
        Dictionary with table names and record counts
    """
    # Create tables first
    create_reference_tables()

    # Load the source of truth
    data = load_data_mapping()
    code_lookups = data["code_lookups"]

    results = {}

    with Session(engine) as session:
        if drop_existing:
            # Truncate all reference tables
            for model in ALL_REFERENCE_MODELS:
                session.execute(text(f"TRUNCATE TABLE {model.__tablename__} CASCADE"))
            session.commit()
            logger.info("Truncated existing reference tables")

        # Simple code tables (just code→description)
        simple_mappings = [
            ("status_codes", RefStatus),
            ("case_classification_codes", RefCaseClassification),
            ("categorical_eligibility_codes", RefCategoricalEligibility),
            ("expedited_service_codes", RefExpeditedService),
            ("error_finding_codes", RefErrorFinding),
            ("sex_codes", RefSex),
            ("snap_affiliation_codes", RefSnapAffiliation),
            ("discovery_method_codes", RefDiscovery),
            # New code tables for complete Vanna coverage
            ("abawd_status_codes", RefAbawdStatus),
            ("citizenship_status_codes", RefCitizenshipStatus),
            ("race_ethnicity_codes", RefRaceEthnicity),
            ("relationship_codes", RefRelationship),
            ("work_registration_codes", RefWorkRegistration),
            ("education_level_codes", RefEducationLevel),
            ("employment_status_type_codes", RefEmploymentStatusType),
            ("disability_codes", RefDisability),
            ("working_indicator_codes", RefWorkingIndicator),
            ("homelessness_codes", RefHomelessness),
            ("reporting_system_codes", RefReportingSystem),
            ("action_type_codes", RefActionType),
            ("allotment_adjustment_codes", RefAllotmentAdjustment),
        ]

        for json_key, model_class in simple_mappings:
            if json_key in code_lookups:
                count = populate_simple_codes(session, model_class, code_lookups[json_key])
                results[model_class.__tablename__] = count
                logger.info(f"Populated {model_class.__tablename__}: {count} records")

        # Element codes (with categories)
        count = populate_element_codes(session, data)
        results["ref_element"] = count
        logger.info(f"Populated ref_element: {count} records")

        # Nature codes (with derived categories)
        count = populate_nature_codes(session, data)
        results["ref_nature"] = count
        logger.info(f"Populated ref_nature: {count} records")

        # Agency responsibility (with client/agency type)
        count = populate_agency_responsibility(session, data)
        results["ref_agency_responsibility"] = count
        logger.info(f"Populated ref_agency_responsibility: {count} records")

        # States
        count = populate_states(session, data)
        results["ref_state"] = count
        logger.info(f"Populated ref_state: {count} records")

        session.commit()

    logger.info(f"Reference table population complete. Total tables: {len(results)}")
    return results


def verify_references() -> dict[str, int]:
    """Verify that all reference tables are populated."""
    results = {}

    with Session(engine) as session:
        for model in ALL_REFERENCE_MODELS:
            count = session.query(model).count()
            results[model.__tablename__] = count

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Populating reference tables from data_mapping.json...")
    print(f"Source: {DATA_MAPPING_PATH}")
    print()

    results = populate_all_references(drop_existing=True)

    print("\nResults:")
    print("-" * 40)
    for table_name, count in sorted(results.items()):
        print(f"  {table_name}: {count} records")
    print("-" * 40)
    print(f"Total: {sum(results.values())} records in {len(results)} tables")
