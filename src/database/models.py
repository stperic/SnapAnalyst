"""
SnapAnalyst Database Models

Normalized schema for SNAP QC data:
- households: Household-level data
- household_members: Person-level data (unpivoted from FSAFIL1-17, etc.)
- qc_errors: Quality control error findings (unpivoted from ELEMENT1-9, etc.)
- data_load_history: Tracking of data loading jobs
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    DECIMAL,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.engine import Base


class Household(Base):
    """
    Household-level SNAP QC data.
    
    Represents one case/household receiving SNAP benefits.
    Uses natural composite primary key: (case_id, fiscal_year)
    """
    
    __tablename__ = "households"
    
    # Natural Composite Primary Key
    case_id: Mapped[str] = mapped_column(String(50), primary_key=True, comment="HHLDNO - Unique unit identifier (row number)")
    fiscal_year: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Case Information
    case_classification: Mapped[Optional[int]] = mapped_column(Integer, comment="CASE - Classification code (1-3): 1=Included in error rate, 2=Excluded SSA, 3=Excluded FNS")
    
    # Geographic & Administrative
    region_code: Mapped[Optional[str]] = mapped_column(String(10), comment="FNS region code")
    state_code: Mapped[Optional[str]] = mapped_column(String(2), index=True, comment="2-letter state abbreviation")
    state_name: Mapped[Optional[str]] = mapped_column(String(50), comment="Full state name for geographic queries")
    year_month: Mapped[Optional[str]] = mapped_column(String(6), index=True, comment="Review period YYYYMM")
    status: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ref_status.code", ondelete="SET NULL"),
        comment="Error status: JOIN ref_status for description (1=correct, 2=overissuance, 3=underissuance)"
    )
    stratum: Mapped[Optional[str]] = mapped_column(String(20), comment="Sampling stratum code")
    
    # Household Composition
    raw_household_size: Mapped[Optional[int]] = mapped_column(Integer, comment="Total persons in household")
    certified_household_size: Mapped[Optional[int]] = mapped_column(Integer, comment="SNAP-certified household size")
    snap_unit_size: Mapped[Optional[int]] = mapped_column(Integer, comment="SNAP unit size for benefit calculation")
    num_noncitizens: Mapped[Optional[int]] = mapped_column(Integer, default=0, comment="Count of non-citizen members")
    num_disabled: Mapped[Optional[int]] = mapped_column(Integer, default=0, comment="Count of disabled members")
    num_elderly: Mapped[Optional[int]] = mapped_column(Integer, default=0, comment="Count of members age 60+")
    num_children: Mapped[Optional[int]] = mapped_column(Integer, default=0, comment="Count of members under 18")
    composition_code: Mapped[Optional[str]] = mapped_column(String(10), comment="Household composition type")
    
    # Financial Summary (monthly amounts in dollars)
    gross_income: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 2), comment="Total monthly gross income before deductions")
    net_income: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 2), comment="Monthly income after deductions")
    earned_income: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 2), comment="Monthly earned income (wages, self-employment)")
    unearned_income: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 2), comment="Monthly unearned income (SSI, TANF, etc)")
    
    # Assets
    liquid_resources: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 2))
    real_property: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 2))
    vehicle_assets: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 2))
    total_assets: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 2))
    
    # Deductions
    standard_deduction: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    earned_income_deduction: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    dependent_care_deduction: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    medical_deduction: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    shelter_deduction: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    total_deductions: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    
    # Housing Expenses
    rent: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    utilities: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    shelter_expense: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    homeless_deduction: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    
    # Benefits (monthly amounts in dollars)
    snap_benefit: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), index=True, comment="QC-calculated correct SNAP benefit amount")
    raw_benefit: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), comment="Originally issued SNAP benefit (before QC correction)")
    maximum_benefit: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), comment="Maximum SNAP benefit for household size")
    minimum_benefit: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), comment="Minimum SNAP benefit amount")
    
    # Eligibility & Certification (FK to reference tables)
    categorical_eligibility: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ref_categorical_eligibility.code", ondelete="SET NULL"),
        comment="Categorical eligibility status: JOIN ref_categorical_eligibility"
    )
    expedited_service: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ref_expedited_service.code", ondelete="SET NULL"),
        comment="Expedited service status: JOIN ref_expedited_service"
    )
    certification_month: Mapped[Optional[str]] = mapped_column(String(6), comment="Certification period YYYYMM")
    # Note: last_certification_date is actually an integer code in the source data, not a date
    last_certification_date: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Poverty & Work Status
    poverty_level: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2))
    working_poor_indicator: Mapped[Optional[bool]] = mapped_column(Boolean)
    tanf_indicator: Mapped[Optional[bool]] = mapped_column(Boolean)
    
    # QC Information
    amount_error: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), comment="Dollar amount of benefit error (positive=over, negative=under)")
    gross_test_result: Mapped[Optional[int]] = mapped_column(Integer, comment="Gross income test result (1=pass, 2=fail)")
    net_test_result: Mapped[Optional[int]] = mapped_column(Integer, comment="Net income test result (1=pass, 2=fail)")
    
    # Statistical Weights
    household_weight: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 8))
    fiscal_year_weight: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 8))
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    members: Mapped[List["HouseholdMember"]] = relationship(
        "HouseholdMember", back_populates="household", cascade="all, delete-orphan"
    )
    errors: Mapped[List["QCError"]] = relationship(
        "QCError", back_populates="household", cascade="all, delete-orphan"
    )
    
    # Constraints and Indexes
    __table_args__ = (
        Index("idx_household_state_year", "state_name", "fiscal_year"),
        Index("idx_household_state_code", "state_code"),
        Index("idx_household_year_month", "year_month"),
        Index("idx_household_snap_benefit", "snap_benefit"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Household(case_id={self.case_id}, fy={self.fiscal_year}, "
            f"state={self.state_code}, benefit={self.snap_benefit})>"
        )


class HouseholdMember(Base):
    """
    Person-level data for household members.
    
    Unpivoted from wide format (FSAFIL1-17, AGE1-17, etc.) to long format.
    One row per household member.
    Uses natural composite primary key: (case_id, fiscal_year, member_number)
    """
    
    __tablename__ = "household_members"
    
    # Natural Composite Primary Key + Foreign Key
    case_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_number: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Member position in household (1-17)"
    )
    
    # Demographics (FK to reference tables)
    age: Mapped[Optional[int]] = mapped_column(
        Integer, CheckConstraint("age >= 0 AND age <= 120"),
        comment="Age in years (0=under 1, 98=98 or older)"
    )
    sex: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ref_sex.code", ondelete="SET NULL"),
        comment="Gender: JOIN ref_sex for description (1=Male, 2=Female)"
    )
    race_ethnicity: Mapped[Optional[int]] = mapped_column(Integer, comment="Race/ethnicity code")
    relationship_to_head: Mapped[Optional[int]] = mapped_column(Integer, comment="Relationship to head of household")
    citizenship_status: Mapped[Optional[int]] = mapped_column(Integer, comment="Citizenship status code")
    years_education: Mapped[Optional[int]] = mapped_column(Integer, comment="Years of education completed")
    
    # Status Indicators (FK to reference tables)
    snap_affiliation_code: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ref_snap_affiliation.code", ondelete="SET NULL"), index=True,
        comment="SNAP eligibility status: JOIN ref_snap_affiliation for description"
    )
    disability_indicator: Mapped[Optional[int]] = mapped_column(Integer, comment="Disability status (1=disabled)")
    foster_child_indicator: Mapped[Optional[int]] = mapped_column(Integer, comment="Foster child status")
    work_registration_status: Mapped[Optional[int]] = mapped_column(Integer, comment="Work registration status code")
    abawd_status: Mapped[Optional[int]] = mapped_column(Integer, comment="ABAWD (Able-Bodied Adult) status")
    working_indicator: Mapped[Optional[int]] = mapped_column(Integer, comment="Currently working indicator")
    
    # Employment
    employment_region: Mapped[Optional[int]] = mapped_column(Integer)
    employment_status_a: Mapped[Optional[int]] = mapped_column(Integer)
    employment_status_b: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Earned Income Sources (monthly amounts in dollars)
    wages: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="Monthly wages and salaries")
    self_employment_income: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="Monthly self-employment income")
    earned_income_tax_credit: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="Earned Income Tax Credit")
    other_earned_income: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="Other earned income")
    
    # Unearned Income Sources (monthly amounts in dollars)
    social_security: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="RSDI/Social Security benefits")
    ssi: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="Supplemental Security Income")
    veterans_benefits: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="Veterans benefits")
    unemployment: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="Unemployment compensation")
    workers_compensation: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="Workers compensation")
    tanf: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="TANF/Welfare benefits")
    child_support: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment="Child support received")
    general_assistance: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    education_loans: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    other_government_income: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    contributions: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    deemed_income: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    other_unearned_income: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    
    # Deductions & Expenses (person-level)
    dependent_care_cost: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    energy_assistance: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    wage_supplement: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    diversion_payment: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    
    # Calculated Fields (can be computed in application layer or via database triggers)
    total_earned_income: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True)
    total_unearned_income: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True)
    total_income: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    household: Mapped["Household"] = relationship("Household", back_populates="members")
    
    # Constraints and Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ['case_id', 'fiscal_year'],
            ['households.case_id', 'households.fiscal_year'],
            ondelete='CASCADE'
        ),
        Index("idx_member_age", "age"),
        Index("idx_member_affiliation", "snap_affiliation_code"),
        Index("idx_member_wages", "wages"),
        Index("idx_member_social_security", "social_security"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<HouseholdMember(case_id={self.case_id}, fy={self.fiscal_year}, "
            f"member_num={self.member_number}, age={self.age})>"
        )


class QCError(Base):
    """
    Quality Control error findings.
    
    Unpivoted from wide format (ELEMENT1-9, NATURE1-9, etc.) to long format.
    One row per error finding.
    Uses natural composite primary key: (case_id, fiscal_year, error_number)
    """
    
    __tablename__ = "qc_errors"
    
    # Natural Composite Primary Key + Foreign Key
    case_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, primary_key=True)
    error_number: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Error sequence number for this household (1-9)"
    )
    
    # Error Details (FK to reference tables for Gold Standard lookups)
    element_code: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ref_element.code", ondelete="SET NULL"), index=True,
        comment="Error element type: JOIN ref_element for description and category"
    )
    nature_code: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ref_nature.code", ondelete="SET NULL"), index=True,
        comment="Nature of error (what went wrong): JOIN ref_nature for description"
    )
    responsible_agency: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ref_agency_responsibility.code", ondelete="SET NULL"),
        comment="Who caused error: JOIN ref_agency_responsibility (use responsibility_type for client vs agency)"
    )
    error_amount: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(10, 2), index=True,
        comment="Dollar amount of this specific error (positive=overissuance)"
    )
    discovery_method: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ref_discovery.code", ondelete="SET NULL"),
        comment="How error was discovered: JOIN ref_discovery"
    )
    verification_status: Mapped[Optional[int]] = mapped_column(Integer, comment="Verification status code")
    
    # Timing
    occurrence_date: Mapped[Optional[int]] = mapped_column(Integer, comment="When error occurred (YYYYMMDD)")
    time_period: Mapped[Optional[str]] = mapped_column(String(20), comment="Error time period")
    
    # Finding (FK to reference table)
    error_finding: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ref_error_finding.code", ondelete="SET NULL"),
        comment="Error finding (overissuance/underissuance/ineligible): JOIN ref_error_finding"
    )
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    household: Mapped["Household"] = relationship("Household", back_populates="errors")
    
    # Constraints and Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ['case_id', 'fiscal_year'],
            ['households.case_id', 'households.fiscal_year'],
            ondelete='CASCADE'
        ),
        Index("idx_error_element", "element_code"),
        Index("idx_error_nature", "nature_code"),
        Index("idx_error_amount", "error_amount"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<QCError(case_id={self.case_id}, fy={self.fiscal_year}, "
            f"error_num={self.error_number}, amount={self.error_amount})>"
        )


class DataLoadHistory(Base):
    """
    Tracking of data loading jobs.
    
    Records information about each CSV load operation.
    """
    
    __tablename__ = "data_load_history"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # File Information
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Counts
    total_rows_in_file: Mapped[Optional[int]] = mapped_column(Integer)
    rows_loaded: Mapped[Optional[int]] = mapped_column(Integer)
    rows_skipped: Mapped[Optional[int]] = mapped_column(Integer)
    households_created: Mapped[Optional[int]] = mapped_column(Integer)
    members_created: Mapped[Optional[int]] = mapped_column(Integer)
    errors_created: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Status
    load_status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # queued, in_progress, completed, failed, rolled_back
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    
    # User/System
    loaded_by: Mapped[Optional[str]] = mapped_column(String(100))
    load_method: Mapped[Optional[str]] = mapped_column(String(50))  # api, cli, scheduled
    
    # Constraints
    __table_args__ = (
        Index("idx_load_history_year", "fiscal_year"),
        Index("idx_load_history_status", "load_status"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DataLoadHistory(fy={self.fiscal_year}, status={self.load_status}, "
            f"rows={self.rows_loaded})>"
        )
