"""
SnapAnalyst Column Mapping Configuration

Maps wide-format CSV columns (1,200+) to normalized database schema.
Defines which columns are person-level (repeated 1-17) and error-level (repeated 1-9).
"""

# Person-level variables (repeated for members 1-17)
PERSON_LEVEL_VARIABLES: dict[str, str] = {
    # Demographics
    "FSAFIL": "snap_affiliation_code",
    "AGE": "age",
    "SEX": "sex",
    "RACETH": "race_ethnicity",
    "REL": "relationship_to_head",
    "CTZN": "citizenship_status",
    "YRSED": "years_education",
    # Status Indicators
    "DIS": "disability_indicator",
    "FOSTER": "foster_child_indicator",
    "WRKREG": "work_registration_status",
    "ABWDST": "abawd_status",
    "WORK": "working_indicator",
    # Employment
    "EMPRG": "employment_region",
    "EMPSTA": "employment_status_a",
    "EMPSTB": "employment_status_b",
    # Earned Income
    "WAGES": "wages",
    "SLFEMP": "self_employment_income",
    "EITC": "earned_income_tax_credit",
    "OTHERN": "other_earned_income",
    # Unearned Income
    "SOCSEC": "social_security",
    "SSI": "ssi",
    "VET": "veterans_benefits",
    "UNEMP": "unemployment",
    "WCOMP": "workers_compensation",
    "TANF": "tanf",
    "CSUPRT": "child_support",
    "GA": "general_assistance",
    "EDLOAN": "education_loans",
    "OTHGOV": "other_government_income",
    "CONT": "contributions",
    "DEEM": "deemed_income",
    "OTHUN": "other_unearned_income",
    # Deductions & Expenses
    "DPCOST": "dependent_care_cost",
    "ENERGY": "energy_assistance",
    "WGESUP": "wage_supplement",
    "DIVER": "diversion_payment",
}

# Error-level variables (repeated for errors 1-9)
ERROR_LEVEL_VARIABLES: dict[str, str] = {
    "ELEMENT": "element_code",
    "NATURE": "nature_code",
    "AGENCY": "responsible_agency",
    "AMOUNT": "error_amount",
    "DISCOV": "discovery_method",
    "VERIF": "verification_status",
    "OCCDATE": "occurrence_date",
    "TIMEPER": "time_period",
    "E_FINDG": "error_finding",
}

# Household-level variables (one per household)
HOUSEHOLD_LEVEL_VARIABLES: dict[str, str] = {
    # Unique Identifier & Classification
    "HHLDNO": "case_id",  # Unique unit identifier (row number in source file)
    "CASE": "case_classification",  # Classification code (1-3), NOT unique ID
    # Geographic & Administrative
    "REGIONCD": "region_code",
    "STATE": "state_code",
    "STATENAME": "state_name",
    "YRMONTH": "year_month",
    "STATUS": "status",
    "STRATUM": "stratum",
    # Household Composition
    "RAWHSIZE": "raw_household_size",
    "CERTHHSZ": "certified_household_size",
    "FSUSIZE": "snap_unit_size",
    "FSNONCIT": "num_noncitizens",
    "FSDIS": "num_disabled",
    "FSELDER": "num_elderly",
    "FSKID": "num_children",
    "COMPOSITION": "composition_code",
    # Financial Summary
    "RAWGROSS": "gross_income",
    "RAWNET": "net_income",
    "RAWERND": "earned_income",
    "FSUNEARN": "unearned_income",
    # Assets
    "LIQRESOR": "liquid_resources",
    "REALPROP": "real_property",
    "FSVEHAST": "vehicle_assets",
    "FSASSET": "total_assets",
    # Deductions
    "FSSTDDED": "standard_deduction",
    "FSERNDED": "earned_income_deduction",
    "FSDEPDED": "dependent_care_deduction",
    "FSMEDDED": "medical_deduction",
    "SHELDED": "shelter_deduction",
    "FSTOTDED": "total_deductions",
    # Housing Expenses
    "RENT": "rent",
    "UTIL": "utilities",
    "FSCSEXP": "shelter_expense",
    "HOMELESS_DED": "homeless_deduction",
    # Benefits
    "FSBEN": "snap_benefit",
    "RAWBEN": "raw_benefit",
    "BENMAX": "maximum_benefit",
    "MINIMUM_BEN": "minimum_benefit",
    # Eligibility & Certification
    "CAT_ELIG": "categorical_eligibility",
    "EXPEDSER": "expedited_service",
    "CERTMTH": "certification_month",
    "LASTCERT": "last_certification_date",
    # Poverty & Work Status
    "TPOV": "poverty_level",
    "WRK_POOR": "working_poor_indicator",
    "TANF_IND": "tanf_indicator",
    # QC Information
    "AMTERR": "amount_error",
    "FSGRTEST": "gross_test_result",
    "FSNETEST": "net_test_result",
    # Statistical Weights
    "HWGT": "household_weight",
    "FYWGT": "fiscal_year_weight",
}


def get_person_column_name(base_variable: str, member_number: int) -> str:
    """
    Get the wide-format column name for a person-level variable.

    Args:
        base_variable: Base variable name (e.g., 'WAGES')
        member_number: Member number (1-17)

    Returns:
        Wide-format column name (e.g., 'WAGES1', 'WAGES17')

    Example:
        >>> get_person_column_name('WAGES', 1)
        'WAGES1'
        >>> get_person_column_name('AGE', 17)
        'AGE17'
    """
    return f"{base_variable}{member_number}"


def get_error_column_name(base_variable: str, error_number: int) -> str:
    """
    Get the wide-format column name for an error-level variable.

    Args:
        base_variable: Base variable name (e.g., 'ELEMENT')
        error_number: Error number (1-9)

    Returns:
        Wide-format column name (e.g., 'ELEMENT1', 'ELEMENT9')
    """
    return f"{base_variable}{error_number}"


def get_all_person_columns() -> list[str]:
    """Get all person-level column names for members 1-17"""
    columns = []
    for var in PERSON_LEVEL_VARIABLES:
        for i in range(1, 18):  # Members 1-17
            columns.append(get_person_column_name(var, i))
    return columns


def get_all_error_columns() -> list[str]:
    """Get all error-level column names for errors 1-9"""
    columns = []
    for var in ERROR_LEVEL_VARIABLES:
        for i in range(1, 10):  # Errors 1-9
            columns.append(get_error_column_name(var, i))
    return columns


def get_required_household_columns() -> list[str]:
    """Get required household columns that must exist"""
    return ["HHLDNO", "STATE", "YRMONTH", "FSBEN"]


def get_required_person_columns() -> list[str]:
    """Get required person columns (for at least one member)"""
    return ["FSAFIL1", "AGE1"]  # At minimum, need first member's affiliation and age
