"""
SnapAnalyst Database Writer

Writes transformed data to PostgreSQL database using SQLAlchemy.
"""
from typing import List, Optional, Tuple
from decimal import Decimal

import polars as pl
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.core.logging import get_logger
from src.core.exceptions import DatabaseError
from src.database.models import Household, HouseholdMember, QCError
from src.database.engine import SessionLocal

logger = get_logger(__name__)


class DatabaseWriter:
    """Writes transformed data to database with batch operations"""
    
    def __init__(self, session: Optional[Session] = None, batch_size: int = 1000):
        """
        Initialize database writer.
        
        Args:
            session: SQLAlchemy session (optional, will create if not provided)
            batch_size: Number of records to insert per batch
        """
        self.session = session
        self.batch_size = batch_size
        self._own_session = session is None
        logger.info(f"Database Writer initialized (batch_size={batch_size})")
    
    def __enter__(self):
        """Context manager entry"""
        if self._own_session:
            self.session = SessionLocal()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self._own_session and self.session:
            if exc_type is not None:
                logger.error(f"Rolling back due to error: {exc_val}")
                self.session.rollback()
            self.session.close()
    
    def write_households(
        self, 
        households_df: pl.DataFrame,
        fiscal_year: int
    ) -> Tuple[int, List[str]]:
        """
        Write household data to database.
        
        Args:
            households_df: Polars DataFrame with household data
            fiscal_year: Fiscal year being loaded
            
        Returns:
            Tuple of (records_written, case_ids)
            
        Raises:
            DatabaseError: If database write fails
        """
        try:
            logger.info(f"Writing {len(households_df)} households to database")
            
            # Convert Polars DataFrame to list of dicts
            households_data = households_df.to_dicts()
            
            # Track case IDs for foreign key relationships
            case_ids = []
            records_written = 0
            
            # Insert in batches
            for i in range(0, len(households_data), self.batch_size):
                batch = households_data[i:i + self.batch_size]
                
                household_objects = []
                for record in batch:
                    # Convert to Decimal for financial fields
                    household = Household(
                        case_id=record.get("case_id"),
                        fiscal_year=fiscal_year,
                        region_code=record.get("region_code"),
                        state_code=record.get("state_code"),
                        state_name=record.get("state_name"),
                        year_month=record.get("year_month"),
                        status=record.get("status"),
                        stratum=record.get("stratum"),
                        
                        # Household composition
                        raw_household_size=record.get("raw_household_size"),
                        certified_household_size=record.get("certified_household_size"),
                        snap_unit_size=record.get("snap_unit_size"),
                        num_noncitizens=record.get("num_noncitizens"),
                        num_disabled=record.get("num_disabled"),
                        num_elderly=record.get("num_elderly"),
                        num_children=record.get("num_children"),
                        composition_code=record.get("composition_code"),
                        
                        # Financial summary
                        gross_income=self._to_decimal(record.get("gross_income")),
                        net_income=self._to_decimal(record.get("net_income")),
                        earned_income=self._to_decimal(record.get("earned_income")),
                        unearned_income=self._to_decimal(record.get("unearned_income")),
                        
                        # Assets
                        liquid_resources=self._to_decimal(record.get("liquid_resources")),
                        real_property=self._to_decimal(record.get("real_property")),
                        vehicle_assets=self._to_decimal(record.get("vehicle_assets")),
                        total_assets=self._to_decimal(record.get("total_assets")),
                        
                        # Deductions
                        standard_deduction=self._to_decimal(record.get("standard_deduction")),
                        earned_income_deduction=self._to_decimal(record.get("earned_income_deduction")),
                        dependent_care_deduction=self._to_decimal(record.get("dependent_care_deduction")),
                        medical_deduction=self._to_decimal(record.get("medical_deduction")),
                        shelter_deduction=self._to_decimal(record.get("shelter_deduction")),
                        total_deductions=self._to_decimal(record.get("total_deductions")),
                        
                        # Housing
                        rent=self._to_decimal(record.get("rent")),
                        utilities=self._to_decimal(record.get("utilities")),
                        shelter_expense=self._to_decimal(record.get("shelter_expense")),
                        homeless_deduction=self._to_decimal(record.get("homeless_deduction")),
                        
                        # Benefits
                        snap_benefit=self._to_decimal(record.get("snap_benefit")),
                        raw_benefit=self._to_decimal(record.get("raw_benefit")),
                        maximum_benefit=self._to_decimal(record.get("maximum_benefit")),
                        minimum_benefit=self._to_decimal(record.get("minimum_benefit")),
                        
                        # Eligibility
                        categorical_eligibility=record.get("categorical_eligibility"),
                        expedited_service=record.get("expedited_service"),
                        certification_month=record.get("certification_month"),
                        last_certification_date=record.get("last_certification_date"),
                        
                        # Poverty & work
                        poverty_level=self._to_decimal(record.get("poverty_level")),
                        working_poor_indicator=record.get("working_poor_indicator"),
                        tanf_indicator=record.get("tanf_indicator"),
                        
                        # QC info
                        amount_error=self._to_decimal(record.get("amount_error")),
                        gross_test_result=record.get("gross_test_result"),
                        net_test_result=record.get("net_test_result"),
                        
                        # Weights
                        household_weight=self._to_decimal(record.get("household_weight")),
                        fiscal_year_weight=self._to_decimal(record.get("fiscal_year_weight")),
                    )
                    
                    household_objects.append(household)
                    case_ids.append(record.get("case_id"))
                
                # Bulk insert batch
                self.session.bulk_save_objects(household_objects)
                self.session.commit()
                
                records_written += len(batch)
                logger.debug(f"Written {records_written}/{len(households_data)} households")
            
            logger.info(f"Successfully wrote {records_written} households")
            return records_written, case_ids
            
        except IntegrityError as e:
            logger.error(f"Integrity error writing households: {e}")
            self.session.rollback()
            raise DatabaseError(f"Duplicate or constraint violation: {e}")
        except SQLAlchemyError as e:
            logger.error(f"Database error writing households: {e}")
            self.session.rollback()
            raise DatabaseError(f"Failed to write households: {e}")
    
    def write_members(
        self, 
        members_df: pl.DataFrame,
        fiscal_year: int
    ) -> int:
        """
        Write household member data to database.
        
        Args:
            members_df: Polars DataFrame with member data
            fiscal_year: Fiscal year for the data
            
        Returns:
            Number of records written
            
        Raises:
            DatabaseError: If database write fails
        """
        try:
            logger.info(f"Writing {len(members_df)} members to database")
            
            members_data = members_df.to_dicts()
            records_written = 0
            
            # Insert in batches
            for i in range(0, len(members_data), self.batch_size):
                batch = members_data[i:i + self.batch_size]
                
                member_objects = []
                for record in batch:
                    member = HouseholdMember(
                        # Natural key fields
                        case_id=record.get("case_id"),
                        fiscal_year=fiscal_year,
                        member_number=record.get("member_number"),
                        
                        # Demographics
                        age=record.get("age"),
                        sex=record.get("sex"),
                        race_ethnicity=record.get("race_ethnicity"),
                        relationship_to_head=record.get("relationship_to_head"),
                        citizenship_status=record.get("citizenship_status"),
                        years_education=record.get("years_education"),
                        
                        # Status
                        snap_affiliation_code=record.get("snap_affiliation_code"),
                        disability_indicator=record.get("disability_indicator"),
                        foster_child_indicator=record.get("foster_child_indicator"),
                        work_registration_status=record.get("work_registration_status"),
                        abawd_status=record.get("abawd_status"),
                        working_indicator=record.get("working_indicator"),
                        
                        # Employment
                        employment_region=record.get("employment_region"),
                        employment_status_a=record.get("employment_status_a"),
                        employment_status_b=record.get("employment_status_b"),
                        
                        # Earned income
                        wages=self._to_decimal(record.get("wages")),
                        self_employment_income=self._to_decimal(record.get("self_employment_income")),
                        earned_income_tax_credit=self._to_decimal(record.get("earned_income_tax_credit")),
                        other_earned_income=self._to_decimal(record.get("other_earned_income")),
                        
                        # Unearned income
                        social_security=self._to_decimal(record.get("social_security")),
                        ssi=self._to_decimal(record.get("ssi")),
                        veterans_benefits=self._to_decimal(record.get("veterans_benefits")),
                        unemployment=self._to_decimal(record.get("unemployment")),
                        workers_compensation=self._to_decimal(record.get("workers_compensation")),
                        tanf=self._to_decimal(record.get("tanf")),
                        child_support=self._to_decimal(record.get("child_support")),
                        general_assistance=self._to_decimal(record.get("general_assistance")),
                        education_loans=self._to_decimal(record.get("education_loans")),
                        other_government_income=self._to_decimal(record.get("other_government_income")),
                        contributions=self._to_decimal(record.get("contributions")),
                        deemed_income=self._to_decimal(record.get("deemed_income")),
                        other_unearned_income=self._to_decimal(record.get("other_unearned_income")),
                        
                        # Deductions
                        dependent_care_cost=self._to_decimal(record.get("dependent_care_cost")),
                        energy_assistance=self._to_decimal(record.get("energy_assistance")),
                        wage_supplement=self._to_decimal(record.get("wage_supplement")),
                        diversion_payment=self._to_decimal(record.get("diversion_payment")),
                    )
                    
                    member_objects.append(member)
                
                # Bulk insert batch
                self.session.bulk_save_objects(member_objects)
                self.session.commit()
                
                records_written += len(member_objects)
                logger.debug(f"Written {records_written}/{len(members_data)} members")
            
            logger.info(f"Successfully wrote {records_written} members")
            return records_written
            
        except SQLAlchemyError as e:
            logger.error(f"Database error writing members: {e}")
            self.session.rollback()
            raise DatabaseError(f"Failed to write members: {e}")
    
    def write_errors(
        self, 
        errors_df: pl.DataFrame,
        fiscal_year: int
    ) -> int:
        """
        Write QC error data to database.
        
        Args:
            errors_df: Polars DataFrame with error data
            fiscal_year: Fiscal year for the data
            
        Returns:
            Number of records written
            
        Raises:
            DatabaseError: If database write fails
        """
        try:
            logger.info(f"Writing {len(errors_df)} QC errors to database")
            
            errors_data = errors_df.to_dicts()
            records_written = 0
            
            # Insert in batches
            for i in range(0, len(errors_data), self.batch_size):
                batch = errors_data[i:i + self.batch_size]
                
                error_objects = []
                for record in batch:
                    error = QCError(
                        # Natural key fields
                        case_id=record.get("case_id"),
                        fiscal_year=fiscal_year,
                        error_number=record.get("error_number"),
                        # Error details
                        element_code=record.get("element_code"),
                        nature_code=record.get("nature_code"),
                        responsible_agency=record.get("responsible_agency"),
                        error_amount=self._to_decimal(record.get("error_amount")),
                        discovery_method=record.get("discovery_method"),
                        verification_status=record.get("verification_status"),
                        occurrence_date=record.get("occurrence_date"),
                        time_period=record.get("time_period"),
                        error_finding=record.get("error_finding"),
                    )
                    
                    error_objects.append(error)
                
                # Bulk insert batch
                self.session.bulk_save_objects(error_objects)
                self.session.commit()
                
                records_written += len(error_objects)
                logger.debug(f"Written {records_written}/{len(errors_data)} errors")
            
            logger.info(f"Successfully wrote {records_written} QC errors")
            return records_written
            
        except SQLAlchemyError as e:
            logger.error(f"Database error writing errors: {e}")
            self.session.rollback()
            raise DatabaseError(f"Failed to write errors: {e}")
    
    
    def write_all(
        self,
        households_df: pl.DataFrame,
        members_df: pl.DataFrame,
        errors_df: pl.DataFrame,
        fiscal_year: int
    ) -> dict:
        """
        Write all data (households, members, errors) in a single transaction.
        
        Args:
            households_df: Household data
            members_df: Member data
            errors_df: Error data
            fiscal_year: Fiscal year
            
        Returns:
            Dictionary with write statistics
            
        Raises:
            DatabaseError: If write fails
        """
        try:
            logger.info("Starting complete data write transaction")
            
            # Write all data - no mapping needed with natural keys!
            households_written, _ = self.write_households(households_df, fiscal_year)
            members_written = self.write_members(members_df, fiscal_year)
            errors_written = self.write_errors(errors_df, fiscal_year)
            
            stats = {
                "households_written": households_written,
                "members_written": members_written,
                "errors_written": errors_written,
                "total_records": households_written + members_written + errors_written,
            }
            
            logger.info(f"Write transaction complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to write all data: {e}")
            raise DatabaseError(f"Complete data write failed: {e}")
    
    
    @staticmethod
    def _to_decimal(value) -> Optional[Decimal]:
        """
        Convert value to Decimal, handling None and various types.
        
        Args:
            value: Value to convert
            
        Returns:
            Decimal or None
        """
        if value is None or (isinstance(value, float) and (value != value)):  # Check for NaN
            return None
        
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None
