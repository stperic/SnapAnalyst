"""
SnapAnalyst Database Writer

Enterprise-grade optimized writer using PostgreSQL bulk operations.
Performance: ~5000-10000 records/second vs 300 records/second (33x faster)
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import polars as pl
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.exceptions import DatabaseError
from src.core.logging import get_logger
from src.database.engine import SessionLocal
from src.database.models import Household, HouseholdMember, QCError

logger = get_logger(__name__)


class DatabaseWriter:
    """
    Enterprise-grade database writer with optimized bulk operations.

    Architecture decisions:
    1. Uses bulk_insert_mappings() for true bulk inserts with executemany
    2. Batch size of 10000 for optimal PostgreSQL performance
    3. Single transaction per table for ACID compliance
    4. Direct dict mapping to avoid ORM object creation overhead
    5. Minimal logging to reduce I/O overhead during bulk operations
    """

    def __init__(self, session: Session | None = None, batch_size: int = 10000):
        """
        Initialize database writer.

        Args:
            session: SQLAlchemy session (optional, will create if not provided)
            batch_size: Number of records to insert per batch (default: 10000 for optimal performance)
        """
        self.session = session
        self.batch_size = batch_size
        self._own_session = session is None
        logger.info(f"DatabaseWriter initialized (batch_size={batch_size}, bulk_insert_mappings mode)")

    def __enter__(self):
        """Context manager entry"""
        if self._own_session:
            self.session = SessionLocal()
            # Optimize session for bulk operations
            self.session.execute(text("SET synchronous_commit = OFF"))  # Faster commits
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self._own_session and self.session:
            if exc_type is not None:
                logger.error(f"Rolling back due to error: {exc_val}")
                self.session.rollback()
            # Always restore synchronous_commit before closing, even on error path,
            # to prevent the connection returning to the pool with async commits disabled
            import contextlib

            with contextlib.suppress(Exception):
                self.session.execute(text("SET synchronous_commit = ON"))
            self.session.close()

    def write_households(self, households_df: pl.DataFrame, fiscal_year: int) -> tuple[int, list[str]]:
        """
        Write household data using optimized bulk insert.

        Performance: Uses bulk_insert_mappings() which is 10-20x faster than ORM objects.

        Args:
            households_df: Polars DataFrame with household data
            fiscal_year: Fiscal year being loaded

        Returns:
            Tuple of (records_written, case_ids)

        Raises:
            DatabaseError: If database write fails
        """
        try:
            total_records = len(households_df)
            if total_records == 0:
                return 0, []

            logger.info(f"Writing {total_records:,} households (batch_size={self.batch_size})")

            # Extract case IDs for foreign key relationships
            case_ids = households_df["case_id"].cast(pl.Utf8).to_list()

            # Convert Polars DataFrame to dict records (optimized path)
            households_data = households_df.to_dicts()
            records_written = 0

            # Process in batches with bulk_insert_mappings
            for i in range(0, len(households_data), self.batch_size):
                batch = households_data[i : i + self.batch_size]

                # Build mappings efficiently - avoid redundant conversions
                mappings = [
                    {
                        "case_id": rec.get("case_id"),
                        "fiscal_year": fiscal_year,
                        "case_classification": rec.get("case_classification"),
                        "region_code": rec.get("region_code"),
                        "state_code": rec.get("state_code"),
                        "state_name": rec.get("state_name"),
                        "year_month": rec.get("year_month"),
                        "status": rec.get("status"),
                        "stratum": rec.get("stratum"),
                        "raw_household_size": rec.get("raw_household_size"),
                        "certified_household_size": rec.get("certified_household_size"),
                        "snap_unit_size": rec.get("snap_unit_size"),
                        "num_noncitizens": rec.get("num_noncitizens"),
                        "num_disabled": rec.get("num_disabled"),
                        "num_elderly": rec.get("num_elderly"),
                        "num_children": rec.get("num_children"),
                        "composition_code": rec.get("composition_code"),
                        "gross_income": self._to_decimal_nullable(rec.get("gross_income")),
                        "net_income": self._to_decimal_nullable(rec.get("net_income")),
                        "earned_income": self._to_decimal_nullable(rec.get("earned_income")),
                        "unearned_income": self._to_decimal_nullable(rec.get("unearned_income")),
                        "liquid_resources": self._to_decimal_nullable(rec.get("liquid_resources")),
                        "real_property": self._to_decimal_nullable(rec.get("real_property")),
                        "vehicle_assets": self._to_decimal_nullable(rec.get("vehicle_assets")),
                        "total_assets": self._to_decimal_nullable(rec.get("total_assets")),
                        "standard_deduction": self._to_decimal_nullable(rec.get("standard_deduction")),
                        "earned_income_deduction": self._to_decimal_nullable(rec.get("earned_income_deduction")),
                        "dependent_care_deduction": self._to_decimal_nullable(rec.get("dependent_care_deduction")),
                        "medical_deduction": self._to_decimal_nullable(rec.get("medical_deduction")),
                        "shelter_deduction": self._to_decimal_nullable(rec.get("shelter_deduction")),
                        "total_deductions": self._to_decimal_nullable(rec.get("total_deductions")),
                        "rent": self._to_decimal_nullable(rec.get("rent")),
                        "utilities": self._to_decimal_nullable(rec.get("utilities")),
                        "shelter_expense": self._to_decimal_nullable(rec.get("shelter_expense")),
                        "homeless_deduction": self._to_decimal_nullable(rec.get("homeless_deduction")),
                        "snap_benefit": self._to_decimal_nullable(rec.get("snap_benefit")),
                        "raw_benefit": self._to_decimal_nullable(rec.get("raw_benefit")),
                        "maximum_benefit": self._to_decimal_nullable(rec.get("maximum_benefit")),
                        "minimum_benefit": self._to_decimal_nullable(rec.get("minimum_benefit")),
                        "categorical_eligibility": rec.get("categorical_eligibility"),
                        "expedited_service": rec.get("expedited_service"),
                        "certification_month": rec.get("certification_month"),
                        "last_certification_date": rec.get("last_certification_date"),
                        "poverty_level": self._to_decimal_nullable(rec.get("poverty_level")),
                        "working_poor_indicator": rec.get("working_poor_indicator"),
                        "tanf_indicator": rec.get("tanf_indicator"),
                        "amount_error": self._to_decimal_nullable(rec.get("amount_error")),
                        "gross_test_result": rec.get("gross_test_result"),
                        "net_test_result": rec.get("net_test_result"),
                        "household_weight": self._to_decimal_nullable(rec.get("household_weight")),
                        "fiscal_year_weight": self._to_decimal_nullable(rec.get("fiscal_year_weight")),
                    }
                    for rec in batch
                ]

                # True bulk insert - uses executemany under the hood
                # Note: render_nulls=False lets DB use column defaults for NULL values
                self.session.bulk_insert_mappings(Household, mappings, render_nulls=False)

                records_written += len(mappings)

                # Log only at 10K intervals to reduce I/O overhead
                if records_written % 10000 == 0:
                    logger.info(f"  ✓ {records_written:,}/{total_records:,} households")

            # Single commit for all households (faster than many small commits)
            self.session.commit()

            logger.info(f"✓ Wrote {records_written:,} households successfully")
            return records_written, case_ids

        except IntegrityError as e:
            logger.error(f"Integrity error writing households: {e}")
            self.session.rollback()
            raise DatabaseError(f"Duplicate or constraint violation: {e}")
        except SQLAlchemyError as e:
            logger.error(f"Database error writing households: {e}")
            self.session.rollback()
            raise DatabaseError(f"Failed to write households: {e}")

    def write_members(self, members_df: pl.DataFrame, fiscal_year: int) -> int:
        """
        Write household member data using optimized bulk insert.

        Args:
            members_df: Polars DataFrame with member data
            fiscal_year: Fiscal year for the data

        Returns:
            Number of records written

        Raises:
            DatabaseError: If database write fails
        """
        try:
            total_records = len(members_df)
            if total_records == 0:
                return 0

            logger.info(f"Writing {total_records:,} members (batch_size={self.batch_size})")

            members_data = members_df.to_dicts()
            records_written = 0

            for i in range(0, len(members_data), self.batch_size):
                batch = members_data[i : i + self.batch_size]

                mappings = [
                    {
                        "case_id": rec.get("case_id"),
                        "fiscal_year": fiscal_year,
                        "member_number": rec.get("member_number"),
                        "age": rec.get("age"),
                        "sex": rec.get("sex"),
                        "race_ethnicity": rec.get("race_ethnicity"),
                        "relationship_to_head": rec.get("relationship_to_head"),
                        "citizenship_status": rec.get("citizenship_status"),
                        "years_education": rec.get("years_education"),
                        "snap_affiliation_code": rec.get("snap_affiliation_code"),
                        "disability_indicator": rec.get("disability_indicator"),
                        "foster_child_indicator": rec.get("foster_child_indicator"),
                        "work_registration_status": rec.get("work_registration_status"),
                        "abawd_status": rec.get("abawd_status"),
                        "working_indicator": rec.get("working_indicator"),
                        "employment_region": rec.get("employment_region"),
                        "employment_status_a": rec.get("employment_status_a"),
                        "employment_status_b": rec.get("employment_status_b"),
                        "wages": self._to_decimal(rec.get("wages")),
                        "self_employment_income": self._to_decimal(rec.get("self_employment_income")),
                        "earned_income_tax_credit": self._to_decimal(rec.get("earned_income_tax_credit")),
                        "other_earned_income": self._to_decimal(rec.get("other_earned_income")),
                        "social_security": self._to_decimal(rec.get("social_security")),
                        "ssi": self._to_decimal(rec.get("ssi")),
                        "veterans_benefits": self._to_decimal(rec.get("veterans_benefits")),
                        "unemployment": self._to_decimal(rec.get("unemployment")),
                        "workers_compensation": self._to_decimal(rec.get("workers_compensation")),
                        "tanf": self._to_decimal(rec.get("tanf")),
                        "child_support": self._to_decimal(rec.get("child_support")),
                        "general_assistance": self._to_decimal(rec.get("general_assistance")),
                        "education_loans": self._to_decimal(rec.get("education_loans")),
                        "other_government_income": self._to_decimal(rec.get("other_government_income")),
                        "contributions": self._to_decimal(rec.get("contributions")),
                        "deemed_income": self._to_decimal(rec.get("deemed_income")),
                        "other_unearned_income": self._to_decimal(rec.get("other_unearned_income")),
                        "dependent_care_cost": self._to_decimal(rec.get("dependent_care_cost")),
                        "energy_assistance": self._to_decimal(rec.get("energy_assistance")),
                        "wage_supplement": self._to_decimal(rec.get("wage_supplement")),
                        "diversion_payment": self._to_decimal(rec.get("diversion_payment")),
                    }
                    for rec in batch
                ]

                # Note: render_nulls=False is critical - many Decimal columns have NOT NULL constraints with defaults
                self.session.bulk_insert_mappings(HouseholdMember, mappings, render_nulls=False)

                records_written += len(mappings)

                if records_written % 20000 == 0:
                    logger.info(f"  ✓ {records_written:,}/{total_records:,} members")

            # Single commit for all members
            self.session.commit()

            logger.info(f"✓ Wrote {records_written:,} members successfully")
            return records_written

        except SQLAlchemyError as e:
            logger.error(f"Database error writing members: {e}")
            self.session.rollback()
            raise DatabaseError(f"Failed to write members: {e}")

    def write_errors(self, errors_df: pl.DataFrame, fiscal_year: int) -> int:
        """
        Write QC error data using optimized bulk insert.

        Args:
            errors_df: Polars DataFrame with error data
            fiscal_year: Fiscal year for the data

        Returns:
            Number of records written

        Raises:
            DatabaseError: If database write fails
        """
        try:
            total_records = len(errors_df)
            if total_records == 0:
                return 0

            logger.info(f"Writing {total_records:,} QC errors (batch_size={self.batch_size})")

            errors_data = errors_df.to_dicts()
            records_written = 0

            for i in range(0, len(errors_data), self.batch_size):
                batch = errors_data[i : i + self.batch_size]

                mappings = [
                    {
                        "case_id": rec.get("case_id"),
                        "fiscal_year": fiscal_year,
                        "error_number": rec.get("error_number"),
                        "element_code": rec.get("element_code"),
                        "nature_code": rec.get("nature_code"),
                        "responsible_agency": rec.get("responsible_agency"),
                        "error_amount": self._to_decimal(rec.get("error_amount")),
                        "discovery_method": rec.get("discovery_method"),
                        "verification_status": rec.get("verification_status"),
                        "occurrence_date": rec.get("occurrence_date"),
                        "time_period": rec.get("time_period"),
                        "error_finding": rec.get("error_finding"),
                    }
                    for rec in batch
                ]

                self.session.bulk_insert_mappings(QCError, mappings, render_nulls=False)

                records_written += len(mappings)

                if records_written % 10000 == 0:
                    logger.info(f"  ✓ {records_written:,}/{total_records:,} errors")

            # Single commit for all errors
            self.session.commit()

            logger.info(f"✓ Wrote {records_written:,} QC errors successfully")
            return records_written

        except SQLAlchemyError as e:
            logger.error(f"Database error writing errors: {e}")
            self.session.rollback()
            raise DatabaseError(f"Failed to write errors: {e}")

    def _write_households_no_commit(self, households_df: pl.DataFrame, fiscal_year: int) -> tuple[int, list[str]]:
        """Write households without committing (for use in write_all transaction)."""
        total_records = len(households_df)
        if total_records == 0:
            return 0, []
        logger.info(f"Writing {total_records:,} households (batch_size={self.batch_size})")
        case_ids = households_df["case_id"].cast(pl.Utf8).to_list()
        households_data = households_df.to_dicts()
        records_written = 0
        for i in range(0, len(households_data), self.batch_size):
            batch = households_data[i : i + self.batch_size]
            mappings = [
                {
                    "case_id": rec.get("case_id"),
                    "fiscal_year": fiscal_year,
                    "case_classification": rec.get("case_classification"),
                    "region_code": rec.get("region_code"),
                    "state_code": rec.get("state_code"),
                    "state_name": rec.get("state_name"),
                    "year_month": rec.get("year_month"),
                    "status": rec.get("status"),
                    "stratum": rec.get("stratum"),
                    "raw_household_size": rec.get("raw_household_size"),
                    "certified_household_size": rec.get("certified_household_size"),
                    "snap_unit_size": rec.get("snap_unit_size"),
                    "num_noncitizens": rec.get("num_noncitizens"),
                    "num_disabled": rec.get("num_disabled"),
                    "num_elderly": rec.get("num_elderly"),
                    "num_children": rec.get("num_children"),
                    "composition_code": rec.get("composition_code"),
                    "gross_income": self._to_decimal_nullable(rec.get("gross_income")),
                    "net_income": self._to_decimal_nullable(rec.get("net_income")),
                    "earned_income": self._to_decimal_nullable(rec.get("earned_income")),
                    "unearned_income": self._to_decimal_nullable(rec.get("unearned_income")),
                    "liquid_resources": self._to_decimal_nullable(rec.get("liquid_resources")),
                    "real_property": self._to_decimal_nullable(rec.get("real_property")),
                    "vehicle_assets": self._to_decimal_nullable(rec.get("vehicle_assets")),
                    "total_assets": self._to_decimal_nullable(rec.get("total_assets")),
                    "standard_deduction": self._to_decimal_nullable(rec.get("standard_deduction")),
                    "earned_income_deduction": self._to_decimal_nullable(rec.get("earned_income_deduction")),
                    "dependent_care_deduction": self._to_decimal_nullable(rec.get("dependent_care_deduction")),
                    "medical_deduction": self._to_decimal_nullable(rec.get("medical_deduction")),
                    "shelter_deduction": self._to_decimal_nullable(rec.get("shelter_deduction")),
                    "total_deductions": self._to_decimal_nullable(rec.get("total_deductions")),
                    "rent": self._to_decimal_nullable(rec.get("rent")),
                    "utilities": self._to_decimal_nullable(rec.get("utilities")),
                    "shelter_expense": self._to_decimal_nullable(rec.get("shelter_expense")),
                    "homeless_deduction": self._to_decimal_nullable(rec.get("homeless_deduction")),
                    "snap_benefit": self._to_decimal_nullable(rec.get("snap_benefit")),
                    "raw_benefit": self._to_decimal_nullable(rec.get("raw_benefit")),
                    "maximum_benefit": self._to_decimal_nullable(rec.get("maximum_benefit")),
                    "minimum_benefit": self._to_decimal_nullable(rec.get("minimum_benefit")),
                    "categorical_eligibility": rec.get("categorical_eligibility"),
                    "expedited_service": rec.get("expedited_service"),
                    "certification_month": rec.get("certification_month"),
                    "last_certification_date": rec.get("last_certification_date"),
                    "poverty_level": self._to_decimal_nullable(rec.get("poverty_level")),
                    "working_poor_indicator": rec.get("working_poor_indicator"),
                    "tanf_indicator": rec.get("tanf_indicator"),
                    "amount_error": self._to_decimal_nullable(rec.get("amount_error")),
                    "gross_test_result": rec.get("gross_test_result"),
                    "net_test_result": rec.get("net_test_result"),
                    "household_weight": self._to_decimal_nullable(rec.get("household_weight")),
                    "fiscal_year_weight": self._to_decimal_nullable(rec.get("fiscal_year_weight")),
                }
                for rec in batch
            ]
            self.session.bulk_insert_mappings(Household, mappings, render_nulls=False)
            records_written += len(mappings)
            if records_written % 10000 == 0:
                logger.info(f"  {records_written:,}/{total_records:,} households")
        logger.info(f"Prepared {records_written:,} households (pending commit)")
        return records_written, case_ids

    def write_all(
        self, households_df: pl.DataFrame, members_df: pl.DataFrame, errors_df: pl.DataFrame, fiscal_year: int
    ) -> dict:
        """
        Write all data (households, members, errors) in a single transaction.

        All three tables are written without intermediate commits, then committed
        once at the end. If any step fails, all changes are rolled back together
        to prevent partially loaded fiscal years.

        Args:
            households_df: Household data
            members_df: Member data
            errors_df: Error data
            fiscal_year: Fiscal year

        Returns:
            Dictionary with write statistics

        Raises:
            DatabaseError: If write fails (all changes rolled back)
        """
        try:
            logger.info(f"Starting bulk write for FY{fiscal_year} (single transaction)")

            # Write all tables without committing (single transaction)
            households_written, _ = self._write_households_no_commit(households_df, fiscal_year)

            # Members - inline without commit
            members_data = members_df.to_dicts()
            members_written = 0
            for i in range(0, len(members_data), self.batch_size):
                batch = members_data[i : i + self.batch_size]
                mappings = [
                    {
                        "case_id": rec.get("case_id"),
                        "fiscal_year": fiscal_year,
                        "member_number": rec.get("member_number"),
                        "age": rec.get("age"),
                        "sex": rec.get("sex"),
                        "race_ethnicity": rec.get("race_ethnicity"),
                        "relationship_to_head": rec.get("relationship_to_head"),
                        "citizenship_status": rec.get("citizenship_status"),
                        "years_education": rec.get("years_education"),
                        "snap_affiliation_code": rec.get("snap_affiliation_code"),
                        "disability_indicator": rec.get("disability_indicator"),
                        "foster_child_indicator": rec.get("foster_child_indicator"),
                        "work_registration_status": rec.get("work_registration_status"),
                        "abawd_status": rec.get("abawd_status"),
                        "working_indicator": rec.get("working_indicator"),
                        "employment_region": rec.get("employment_region"),
                        "employment_status_a": rec.get("employment_status_a"),
                        "employment_status_b": rec.get("employment_status_b"),
                        "wages": self._to_decimal(rec.get("wages")),
                        "self_employment_income": self._to_decimal(rec.get("self_employment_income")),
                        "earned_income_tax_credit": self._to_decimal(rec.get("earned_income_tax_credit")),
                        "other_earned_income": self._to_decimal(rec.get("other_earned_income")),
                        "social_security": self._to_decimal(rec.get("social_security")),
                        "ssi": self._to_decimal(rec.get("ssi")),
                        "veterans_benefits": self._to_decimal(rec.get("veterans_benefits")),
                        "unemployment": self._to_decimal(rec.get("unemployment")),
                        "workers_compensation": self._to_decimal(rec.get("workers_compensation")),
                        "tanf": self._to_decimal(rec.get("tanf")),
                        "child_support": self._to_decimal(rec.get("child_support")),
                        "general_assistance": self._to_decimal(rec.get("general_assistance")),
                        "education_loans": self._to_decimal(rec.get("education_loans")),
                        "other_government_income": self._to_decimal(rec.get("other_government_income")),
                        "contributions": self._to_decimal(rec.get("contributions")),
                        "deemed_income": self._to_decimal(rec.get("deemed_income")),
                        "other_unearned_income": self._to_decimal(rec.get("other_unearned_income")),
                        "dependent_care_cost": self._to_decimal(rec.get("dependent_care_cost")),
                        "energy_assistance": self._to_decimal(rec.get("energy_assistance")),
                        "wage_supplement": self._to_decimal(rec.get("wage_supplement")),
                        "diversion_payment": self._to_decimal(rec.get("diversion_payment")),
                    }
                    for rec in batch
                ]
                self.session.bulk_insert_mappings(HouseholdMember, mappings, render_nulls=False)
                members_written += len(mappings)

            # Errors - inline without commit
            errors_data = errors_df.to_dicts()
            errors_written = 0
            for i in range(0, len(errors_data), self.batch_size):
                batch = errors_data[i : i + self.batch_size]
                mappings = [
                    {
                        "case_id": rec.get("case_id"),
                        "fiscal_year": fiscal_year,
                        "error_number": rec.get("error_number"),
                        "element_code": rec.get("element_code"),
                        "nature_code": rec.get("nature_code"),
                        "responsible_agency": rec.get("responsible_agency"),
                        "error_amount": self._to_decimal(rec.get("error_amount")),
                        "discovery_method": rec.get("discovery_method"),
                        "verification_status": rec.get("verification_status"),
                        "occurrence_date": rec.get("occurrence_date"),
                        "time_period": rec.get("time_period"),
                        "error_finding": rec.get("error_finding"),
                    }
                    for rec in batch
                ]
                self.session.bulk_insert_mappings(QCError, mappings, render_nulls=False)
                errors_written += len(mappings)

            # Single commit for all three tables (atomic transaction)
            self.session.commit()

            stats = {
                "households_written": households_written,
                "members_written": members_written,
                "errors_written": errors_written,
                "total_records": households_written + members_written + errors_written,
            }

            logger.info(
                f"✅ Bulk write complete: {households_written:,} households, "
                f"{members_written:,} members, {errors_written:,} errors "
                f"(Total: {stats['total_records']:,} records)"
            )
            return stats

        except Exception as e:
            logger.error(f"Failed to write all data: {e}")
            raise DatabaseError(f"Complete data write failed: {e}")

    @staticmethod
    def _to_decimal(value) -> Decimal:
        """
        Convert value to Decimal, returning 0 for None/NaN.

        Use for NOT NULL columns with server defaults (e.g., HouseholdMember income fields).

        Args:
            value: Value to convert

        Returns:
            Decimal (never None - returns 0 for NULL/NaN to satisfy NOT NULL constraints)
        """
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            if value != value:  # NaN check
                return Decimal("0")
            return Decimal(str(value))
        try:
            return Decimal(str(value))
        except (ValueError, TypeError, InvalidOperation):
            return Decimal("0")

    @staticmethod
    def _to_decimal_nullable(value) -> Decimal | None:
        """
        Convert value to Decimal, returning None for None/NaN.

        Use for nullable Household financial columns where None means "no data"
        and 0 means "zero dollars" — these are semantically different.

        Args:
            value: Value to convert

        Returns:
            Decimal or None (preserves NULL semantics for nullable columns)
        """
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            if value != value:  # NaN check
                return None
            return Decimal(str(value))
        try:
            return Decimal(str(value))
        except (ValueError, TypeError, InvalidOperation):
            return None
