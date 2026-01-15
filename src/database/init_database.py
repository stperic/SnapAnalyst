"""
Database Initialization Script

GOLD STANDARD ARCHITECTURE:
---------------------------
Creates all tables with proper FK constraints and populates reference data
from data_mapping.json (single source of truth).

CRITICAL: Reference tables MUST be populated BEFORE loading main data!
Main tables have FK constraints to reference tables. If a code value
doesn't exist in the reference table, data loading will fail.

Usage:
    # From command line:
    python -m src.database.init_database
    
    # With options:
    python -m src.database.init_database --reset  # Drop and recreate all tables
    python -m src.database.init_database --refs-only  # Only populate reference tables
    
    # From code:
    from src.database.init_database import initialize_database
    initialize_database()

Architecture:
    1. Creates reference tables first (ref_*) 
    2. Creates main tables with FK constraints pointing to ref_* tables
    3. Populates reference tables from data_mapping.json
    4. Creates enriched views for common query patterns
    
    Order is enforced by SQLAlchemy metadata ordering.
"""

import argparse
import logging
import sys
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.engine import engine, Base

logger = logging.getLogger(__name__)


def create_all_tables(drop_existing: bool = False) -> None:
    """
    Create all database tables.
    
    Args:
        drop_existing: If True, drop all existing tables first
    """
    # Import all models to register them with Base
    from src.database import models  # noqa - registers main tables
    from src.database import reference_models  # noqa - registers reference tables
    
    if drop_existing:
        logger.warning("Dropping all existing tables...")
        Base.metadata.drop_all(engine)
        logger.info("All tables dropped")
    
    # Create all tables
    Base.metadata.create_all(engine)
    logger.info("All tables created/verified")


def create_enriched_views() -> None:
    """
    Create SQL views that JOIN main tables with reference tables
    for convenient querying with human-readable labels.
    """
    views = {
        # Enriched errors view - includes all human-readable labels
        "v_qc_errors_enriched": """
            CREATE OR REPLACE VIEW v_qc_errors_enriched AS
            SELECT 
                e.case_id,
                e.fiscal_year,
                e.error_number,
                e.element_code,
                re.description AS element_description,
                re.category AS element_category,
                e.nature_code,
                rn.description AS nature_description,
                rn.category AS nature_category,
                e.responsible_agency,
                ra.description AS responsibility_description,
                ra.responsibility_type,
                e.error_finding,
                rf.description AS finding_description,
                e.error_amount,
                h.state_name,
                h.snap_benefit,
                h.gross_income
            FROM qc_errors e
            LEFT JOIN ref_element re ON e.element_code = re.code
            LEFT JOIN ref_nature rn ON e.nature_code = rn.code
            LEFT JOIN ref_agency_responsibility ra ON e.responsible_agency = ra.code
            LEFT JOIN ref_error_finding rf ON e.error_finding = rf.code
            LEFT JOIN households h ON e.case_id = h.case_id AND e.fiscal_year = h.fiscal_year
        """,
        
        # Enriched households view - includes status descriptions
        "v_households_enriched": """
            CREATE OR REPLACE VIEW v_households_enriched AS
            SELECT 
                h.*,
                rs.description AS status_description,
                rce.description AS cat_elig_description,
                res.description AS expedited_description
            FROM households h
            LEFT JOIN ref_status rs ON h.status = rs.code
            LEFT JOIN ref_categorical_eligibility rce ON h.categorical_eligibility = rce.code
            LEFT JOIN ref_expedited_service res ON h.expedited_service = res.code
        """,
        
        # Enriched members view - includes demographic descriptions
        "v_members_enriched": """
            CREATE OR REPLACE VIEW v_members_enriched AS
            SELECT 
                m.*,
                h.state_name,
                rsex.description AS sex_description,
                rsa.description AS affiliation_description
            FROM household_members m
            LEFT JOIN households h ON m.case_id = h.case_id AND m.fiscal_year = h.fiscal_year
            LEFT JOIN ref_sex rsex ON m.sex = rsex.code
            LEFT JOIN ref_snap_affiliation rsa ON m.snap_affiliation_code = rsa.code
        """,
        
        # Error summary by type - aggregated view
        "v_error_summary_by_type": """
            CREATE OR REPLACE VIEW v_error_summary_by_type AS
            SELECT 
                e.fiscal_year,
                re.category AS error_category,
                re.description AS error_type,
                COUNT(*) AS error_count,
                SUM(e.error_amount) AS total_error_amount,
                AVG(e.error_amount) AS avg_error_amount
            FROM qc_errors e
            LEFT JOIN ref_element re ON e.element_code = re.code
            GROUP BY e.fiscal_year, re.category, re.description
        """,
        
        # Error summary by responsibility - client vs agency
        "v_error_summary_by_responsibility": """
            CREATE OR REPLACE VIEW v_error_summary_by_responsibility AS
            SELECT 
                e.fiscal_year,
                h.state_name,
                ra.responsibility_type,
                ra.description AS responsibility_detail,
                COUNT(*) AS error_count,
                SUM(e.error_amount) AS total_error_amount
            FROM qc_errors e
            LEFT JOIN ref_agency_responsibility ra ON e.responsible_agency = ra.code
            LEFT JOIN households h ON e.case_id = h.case_id AND e.fiscal_year = h.fiscal_year
            GROUP BY e.fiscal_year, h.state_name, ra.responsibility_type, ra.description
        """,
    }
    
    with Session(engine) as session:
        for view_name, view_sql in views.items():
            try:
                session.execute(text(view_sql))
                logger.info(f"Created view: {view_name}")
            except Exception as e:
                logger.warning(f"Could not create view {view_name}: {e}")
        
        session.commit()
    
    logger.info(f"Created {len(views)} enriched views")


def populate_references(drop_existing: bool = False) -> dict[str, int]:
    """
    Populate reference tables from data_mapping.json.
    
    Args:
        drop_existing: If True, truncate tables before populating
        
    Returns:
        Dictionary with table names and record counts
    """
    from src.database.populate_references import populate_all_references
    return populate_all_references(drop_existing=drop_existing)


def verify_database() -> dict[str, int]:
    """
    Verify database state by counting records in all tables.
    
    Returns:
        Dictionary with table names and record counts
    """
    from src.database.reference_models import ALL_REFERENCE_MODELS
    from src.database.models import Household, HouseholdMember, QCError
    
    results = {}
    
    with Session(engine) as session:
        # Reference tables
        for model in ALL_REFERENCE_MODELS:
            try:
                count = session.query(model).count()
                results[model.__tablename__] = count
            except Exception:
                results[model.__tablename__] = -1  # Table doesn't exist
        
        # Main tables
        for model in [Household, HouseholdMember, QCError]:
            try:
                count = session.query(model).count()
                results[model.__tablename__] = count
            except Exception:
                results[model.__tablename__] = -1
    
    return results


def check_references_populated() -> tuple[bool, list[str]]:
    """
    Check if reference tables are populated.
    
    CRITICAL: Reference tables MUST be populated before loading main data
    because main tables have FK constraints to reference tables.
    
    Returns:
        Tuple of (all_populated: bool, empty_tables: list[str])
    """
    from src.database.reference_models import ALL_REFERENCE_MODELS
    
    empty_tables = []
    
    with Session(engine) as session:
        for model in ALL_REFERENCE_MODELS:
            try:
                count = session.query(model).count()
                if count == 0:
                    empty_tables.append(model.__tablename__)
            except Exception:
                empty_tables.append(model.__tablename__)
    
    return len(empty_tables) == 0, empty_tables


def ensure_references_populated() -> None:
    """
    Ensure reference tables are populated. Raises error if not.
    
    Call this before loading main data to prevent FK constraint violations.
    
    Raises:
        RuntimeError: If reference tables are empty
    """
    all_populated, empty_tables = check_references_populated()
    
    if not all_populated:
        msg = (
            "Reference tables must be populated before loading main data!\n"
            f"Empty tables: {', '.join(empty_tables)}\n"
            "Run: python -m src.database.init_database --refs-only"
        )
        logger.error(msg)
        raise RuntimeError(msg)


def initialize_database(
    reset: bool = False,
    refs_only: bool = False,
    create_views: bool = True,
) -> dict[str, int]:
    """
    Initialize the complete database.
    
    Args:
        reset: If True, drop and recreate all tables
        refs_only: If True, only populate reference tables (skip table creation)
        create_views: If True, create enriched views
        
    Returns:
        Dictionary with table names and record counts
    """
    logger.info("=" * 60)
    logger.info("SNAP QC Database Initialization")
    logger.info("=" * 60)
    
    if not refs_only:
        # Step 1: Create tables
        logger.info("\n[Step 1/3] Creating database tables...")
        create_all_tables(drop_existing=reset)
    
    # Step 2: Populate reference tables
    logger.info("\n[Step 2/3] Populating reference tables from data_mapping.json...")
    ref_results = populate_references(drop_existing=reset or refs_only)
    
    if create_views and not refs_only:
        # Step 3: Create views
        logger.info("\n[Step 3/3] Creating enriched views...")
        try:
            create_enriched_views()
        except Exception as e:
            logger.warning(f"Could not create views (non-fatal): {e}")
    
    # Verify
    logger.info("\n" + "=" * 60)
    logger.info("Verification")
    logger.info("=" * 60)
    
    all_results = verify_database()
    
    # Log results
    ref_total = sum(v for k, v in all_results.items() if k.startswith("ref_") and v > 0)
    main_total = sum(v for k, v in all_results.items() if not k.startswith("ref_") and v > 0)
    
    logger.info(f"Reference tables: {ref_total} records")
    logger.info(f"Main data tables: {main_total} records")
    
    return all_results


def main():
    """Command-line interface for database initialization."""
    parser = argparse.ArgumentParser(
        description="Initialize SNAP QC database with reference tables"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables (WARNING: destroys data)"
    )
    parser.add_argument(
        "--refs-only",
        action="store_true",
        help="Only populate reference tables (skip table creation)"
    )
    parser.add_argument(
        "--no-views",
        action="store_true",
        help="Skip creating enriched views"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s"
    )
    
    # Confirm reset
    if args.reset:
        print("\n" + "!" * 60)
        print("WARNING: This will DELETE ALL DATA in the database!")
        print("!" * 60)
        response = input("\nType 'yes' to confirm: ")
        if response.lower() != "yes":
            print("Aborted.")
            sys.exit(0)
    
    # Run initialization
    results = initialize_database(
        reset=args.reset,
        refs_only=args.refs_only,
        create_views=not args.no_views,
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("Database Initialization Complete")
    print("=" * 60)
    print("\nTable Record Counts:")
    print("-" * 40)
    
    for table_name in sorted(results.keys()):
        count = results[table_name]
        status = "✓" if count >= 0 else "✗"
        print(f"  {status} {table_name}: {count if count >= 0 else 'N/A'}")
    
    print("-" * 40)
    print(f"Total reference records: {sum(v for k, v in results.items() if k.startswith('ref_') and v > 0)}")
    print(f"Total data records: {sum(v for k, v in results.items() if not k.startswith('ref_') and v > 0)}")


if __name__ == "__main__":
    main()
