"""
Reference/Lookup Tables for SNAP QC Database

These tables provide human-readable descriptions for all coded values,
enabling Vanna.ai to generate more accurate SQL through proper JOINs.

Schema: public (SNAP QC reference data)

ARCHITECTURE:
- Table structures are defined here (SQLAlchemy models)
- Actual data comes from data_mapping.json (single source of truth)
- Use populate_references.py to load data from JSON into tables

This follows the "Gold Standard" Vanna.ai pattern:
- Lookup tables with foreign keys
- LLM sees labels in schema, generates natural JOINs
- No documentation-based guessing for code values
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.engine import Base

# =============================================================================
# GENERIC REFERENCE TABLE STRUCTURE
# =============================================================================
# All reference tables follow the same pattern: code (int PK) + description (str)
# Some have additional category/type columns for grouping


class RefStatus(Base):
    """Status of case error findings (STATUS field)."""
    __tablename__ = "ref_status"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefCaseClassification(Base):
    """Case classification for error rate calculation (CASE field)."""
    __tablename__ = "ref_case_classification"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefCategoricalEligibility(Base):
    """Categorical eligibility status (CAT_ELIG field)."""
    __tablename__ = "ref_categorical_eligibility"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefExpeditedService(Base):
    """Expedited SNAP benefits status (EXPEDSER field)."""
    __tablename__ = "ref_expedited_service"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefErrorFinding(Base):
    """Impact of variance on benefits (E_FINDG field)."""
    __tablename__ = "ref_error_finding"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefSex(Base):
    """Sex of household member (SEX field)."""
    __tablename__ = "ref_sex"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(100), nullable=False)


class RefSnapAffiliation(Base):
    """SNAP case affiliation status (FSAFIL field)."""
    __tablename__ = "ref_snap_affiliation"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefElement(Base):
    """
    Type of variance element - what area had the problem (ELEMENT field).
    Critical for error analysis queries.
    """
    __tablename__ = "ref_element"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=True)


class RefNature(Base):
    """
    Nature of variance - what went wrong (NATURE field).
    Critical for understanding error causes.
    """
    __tablename__ = "ref_nature"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=True)


class RefAgencyResponsibility(Base):
    """
    Agency or client responsibility - who caused the error (AGENCY field).
    Codes 1-8 are client errors, 10-21 are agency errors.
    """
    __tablename__ = "ref_agency_responsibility"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    responsibility_type: Mapped[str] = mapped_column(String(20), nullable=True)


class RefDiscovery(Base):
    """How variance was discovered (DISCOV field)."""
    __tablename__ = "ref_discovery"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefState(Base):
    """
    State/territory reference with FIPS codes.
    Enables JOINs for state-based queries.
    """
    __tablename__ = "ref_state"
    fips_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    abbreviation: Mapped[str] = mapped_column(String(2), nullable=True)


class RefAbawdStatus(Base):
    """ABAWD (Able-Bodied Adult Without Dependents) status codes."""
    __tablename__ = "ref_abawd_status"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefCitizenshipStatus(Base):
    """Citizenship status codes."""
    __tablename__ = "ref_citizenship_status"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefRaceEthnicity(Base):
    """Race and ethnicity codes."""
    __tablename__ = "ref_race_ethnicity"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefRelationship(Base):
    """Relationship to head of household codes."""
    __tablename__ = "ref_relationship"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefWorkRegistration(Base):
    """Work registration status codes."""
    __tablename__ = "ref_work_registration"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefEducationLevel(Base):
    """Education level codes."""
    __tablename__ = "ref_education_level"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefEmploymentStatusType(Base):
    """Employment status type codes."""
    __tablename__ = "ref_employment_status_type"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefDisability(Base):
    """Disability indicator codes."""
    __tablename__ = "ref_disability"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(100), nullable=False)


class RefWorkingIndicator(Base):
    """Working indicator codes."""
    __tablename__ = "ref_working_indicator"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(100), nullable=False)


class RefHomelessness(Base):
    """Homelessness status codes."""
    __tablename__ = "ref_homelessness"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefReportingSystem(Base):
    """Reporting system/requirement codes."""
    __tablename__ = "ref_reporting_system"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefActionType(Base):
    """Action type codes."""
    __tablename__ = "ref_action_type"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RefAllotmentAdjustment(Base):
    """Allotment adjustment type codes."""
    __tablename__ = "ref_allotment_adjustment"
    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


# =============================================================================
# ALL REFERENCE MODELS (for bulk operations)
# =============================================================================

ALL_REFERENCE_MODELS = [
    RefStatus,
    RefCaseClassification,
    RefCategoricalEligibility,
    RefExpeditedService,
    RefErrorFinding,
    RefSex,
    RefSnapAffiliation,
    RefElement,
    RefNature,
    RefAgencyResponsibility,
    RefDiscovery,
    RefState,
    # New tables for complete Vanna coverage
    RefAbawdStatus,
    RefCitizenshipStatus,
    RefRaceEthnicity,
    RefRelationship,
    RefWorkRegistration,
    RefEducationLevel,
    RefEmploymentStatusType,
    RefDisability,
    RefWorkingIndicator,
    RefHomelessness,
    RefReportingSystem,
    RefActionType,
    RefAllotmentAdjustment,
]

# Mapping from JSON key to model class
JSON_KEY_TO_MODEL = {
    "status_codes": RefStatus,
    "case_classification_codes": RefCaseClassification,
    "categorical_eligibility_codes": RefCategoricalEligibility,
    "expedited_service_codes": RefExpeditedService,
    "error_finding_codes": RefErrorFinding,
    "sex_codes": RefSex,
    "snap_affiliation_codes": RefSnapAffiliation,
    "element_codes": RefElement,
    "nature_codes": RefNature,
    "agency_responsibility_codes": RefAgencyResponsibility,
    "discovery_method_codes": RefDiscovery,
    # New mappings
    "abawd_status_codes": RefAbawdStatus,
    "citizenship_status_codes": RefCitizenshipStatus,
    "race_ethnicity_codes": RefRaceEthnicity,
    "relationship_codes": RefRelationship,
    "work_registration_codes": RefWorkRegistration,
    "education_level_codes": RefEducationLevel,
    "employment_status_type_codes": RefEmploymentStatusType,
    "disability_codes": RefDisability,
    "working_indicator_codes": RefWorkingIndicator,
    "homelessness_codes": RefHomelessness,
    "reporting_system_codes": RefReportingSystem,
    "action_type_codes": RefActionType,
    "allotment_adjustment_codes": RefAllotmentAdjustment,
}
