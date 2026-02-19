-- ============================================================================
-- SNAP QC Database Schema
-- Self-documenting DDL for Vanna AI
-- ============================================================================
--
-- This file contains the complete database schema with:
-- 1. Table definitions with columns and constraints
-- 2. COMMENT ON statements with business context
-- 3. Example queries embedded in comments for Vanna training
--
-- Usage:
--   psql -d snapanalyst_db -f schema.sql
--
-- ============================================================================

-- ============================================================================
-- SCHEMAS
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS app;
COMMENT ON SCHEMA app IS 'Application/system data (user prompts, load history)';

-- ============================================================================
-- REFERENCE TABLES
-- These provide human-readable descriptions for coded values.
-- Always JOIN to these tables to get meaningful descriptions.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ref_status: QC finding status codes
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_status (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);

COMMENT ON TABLE ref_status IS 'QC finding status codes for households.
Values: 1=Amount correct, 2=Overissuance, 3=Underissuance
Example queries:
- Show all overissuance cases: SELECT * FROM households WHERE status = 2
- Count by status: SELECT rs.description, COUNT(*) FROM households h JOIN ref_status rs ON h.status = rs.code GROUP BY rs.description';

COMMENT ON COLUMN ref_status.code IS 'Status code: 1=Correct, 2=Overissuance (too much paid), 3=Underissuance (too little paid)';

-- ----------------------------------------------------------------------------
-- ref_element: Error element types - what area had the problem
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_element (
    code INTEGER PRIMARY KEY,
    description VARCHAR(150) NOT NULL,
    category VARCHAR(50)
);

COMMENT ON TABLE ref_element IS 'Error element types - what area of the case had the problem.
Categories: earned_income (311-320), unearned_income (321-346), assets (211-222), deductions (411-450), computation (520)
Example queries:
- Show errors by type: SELECT re.description, COUNT(*) FROM qc_errors e JOIN ref_element re ON e.element_code = re.code GROUP BY re.description
- Find wage errors: SELECT * FROM qc_errors WHERE element_code = 311
- Income errors: SELECT * FROM qc_errors WHERE element_code BETWEEN 311 AND 346';

COMMENT ON COLUMN ref_element.code IS 'Element code: 311=Wages, 321=SSI, 211=Bank accounts, 520=Computation';
COMMENT ON COLUMN ref_element.category IS 'Category grouping: earned_income, unearned_income, assets, deductions, computation';

-- ----------------------------------------------------------------------------
-- ref_nature: Nature of error - what went wrong
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_nature (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL,
    category VARCHAR(50)
);

COMMENT ON TABLE ref_nature IS 'Nature of error - what specifically went wrong.
Categories: income (unreported/underreported), verification, computation
Example queries:
- Unreported income errors: SELECT * FROM qc_errors WHERE nature_code = 35
- Error causes: SELECT rn.description, COUNT(*) FROM qc_errors e JOIN ref_nature rn ON e.nature_code = rn.code GROUP BY rn.description';

COMMENT ON COLUMN ref_nature.code IS 'Nature code: 35=Unreported income source, 75=Benefit incorrectly computed';
COMMENT ON COLUMN ref_nature.category IS 'Category: income, verification, computation';

-- ----------------------------------------------------------------------------
-- ref_agency_responsibility: Who caused the error
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_agency_responsibility (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL,
    responsibility_type VARCHAR(20)
);

COMMENT ON TABLE ref_agency_responsibility IS 'Who is responsible for the error - client or agency.
Codes 1-8 are client errors, codes 10-21 are agency errors.
Use responsibility_type column to filter: "client" or "agency"
Example queries:
- Client vs agency errors: SELECT responsibility_type, COUNT(*) FROM qc_errors e JOIN ref_agency_responsibility ra ON e.responsible_agency = ra.code GROUP BY responsibility_type
- Agency errors only: SELECT * FROM qc_errors e JOIN ref_agency_responsibility ra ON e.responsible_agency = ra.code WHERE ra.responsibility_type = ''agency''';

COMMENT ON COLUMN ref_agency_responsibility.responsibility_type IS 'Type: "client" (codes 1-8) or "agency" (codes 10-21)';

-- ----------------------------------------------------------------------------
-- ref_error_finding: Impact of error on benefits
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_error_finding (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);

COMMENT ON TABLE ref_error_finding IS 'Error finding - impact on benefits. Values: 2=Overissuance (too much paid), 3=Underissuance (too little paid), 4=Ineligible (should not have received any benefits).
Example queries:
- Overissuance errors only: SELECT * FROM qc_errors WHERE error_finding = 2
- Ineligible cases: SELECT * FROM qc_errors WHERE error_finding = 4
- Errors by finding: SELECT rf.description, COUNT(*) FROM qc_errors e JOIN ref_error_finding rf ON e.error_finding = rf.code GROUP BY rf.description';

-- ----------------------------------------------------------------------------
-- ref_categorical_eligibility: Categorical eligibility status
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_categorical_eligibility (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);

COMMENT ON TABLE ref_categorical_eligibility IS 'Categorical eligibility status - exempt from income/asset tests.
Example queries:
- Categorically eligible households: SELECT * FROM households WHERE categorical_eligibility = 1';

-- ----------------------------------------------------------------------------
-- ref_expedited_service: Expedited SNAP benefits status
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_expedited_service (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);

COMMENT ON TABLE ref_expedited_service IS 'Expedited service status - whether benefits were issued quickly.
Values: 1=Entitled and received on time, 2=Entitled but NOT received on time, 3=Not entitled
Example queries:
- Expedited but late: SELECT * FROM households WHERE expedited_service = 2
- Expedited on time: SELECT * FROM households WHERE expedited_service = 1';

-- ----------------------------------------------------------------------------
-- ref_sex: Gender codes
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_sex (
    code INTEGER PRIMARY KEY,
    description VARCHAR(100) NOT NULL
);

COMMENT ON TABLE ref_sex IS 'Gender codes for household members.
Values: 1=Male, 2=Female
Example queries:
- Members by gender: SELECT rs.description, COUNT(*) FROM household_members m JOIN ref_sex rs ON m.sex = rs.code GROUP BY rs.description';

-- ----------------------------------------------------------------------------
-- ref_snap_affiliation: SNAP eligibility status
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_snap_affiliation (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);

COMMENT ON TABLE ref_snap_affiliation IS 'SNAP case affiliation - member eligibility status.
Codes 1-2 are eligible, other codes indicate various ineligibility reasons.
Example queries:
- Ineligible members: SELECT * FROM household_members WHERE snap_affiliation_code NOT IN (1, 2)';

-- ----------------------------------------------------------------------------
-- ref_discovery: How error was discovered
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_discovery (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);

COMMENT ON TABLE ref_discovery IS 'How the error was discovered during QC review.';

-- ----------------------------------------------------------------------------
-- ref_state: State/territory reference
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_state (
    fips_code INTEGER PRIMARY KEY,
    state_name VARCHAR(50) NOT NULL UNIQUE,
    abbreviation VARCHAR(2)
);

COMMENT ON TABLE ref_state IS 'State and territory reference with FIPS codes and 2-letter abbreviations. NOTE: For state-level queries, use households.state_name directly (no JOIN needed). This table is useful only for FIPS code lookups.
Example: SELECT rs.fips_code, rs.abbreviation, rs.state_name FROM ref_state rs ORDER BY rs.state_name';

-- ----------------------------------------------------------------------------
-- Additional reference tables
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_case_classification (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_case_classification IS 'Case classification for error rate calculation. CRITICAL: Filter WHERE case_classification = 1 for ALL official error rate calculations. Values: 1=Included in official error rates, 2=Excluded by SSA, 3=Excluded by FNS';

CREATE TABLE IF NOT EXISTS ref_abawd_status (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_abawd_status IS 'ABAWD (Able-Bodied Adult Without Dependents) work requirement status. Code 1 = not an ABAWD. Other codes indicate ABAWD status and work requirement compliance. JOIN household_members ON abawd_status.';

CREATE TABLE IF NOT EXISTS ref_citizenship_status (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_citizenship_status IS 'Citizenship and immigration status codes.';

CREATE TABLE IF NOT EXISTS ref_race_ethnicity (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_race_ethnicity IS 'Race and ethnicity codes.';

CREATE TABLE IF NOT EXISTS ref_relationship (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_relationship IS 'Relationship to head of household codes.';

CREATE TABLE IF NOT EXISTS ref_work_registration (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_work_registration IS 'Work registration status codes.';

CREATE TABLE IF NOT EXISTS ref_education_level (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_education_level IS 'Education level codes.';

CREATE TABLE IF NOT EXISTS ref_employment_status_type (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_employment_status_type IS 'Employment status type codes.';

CREATE TABLE IF NOT EXISTS ref_disability (
    code INTEGER PRIMARY KEY,
    description VARCHAR(100) NOT NULL
);
COMMENT ON TABLE ref_disability IS 'Disability indicator codes. 1=Disabled';

CREATE TABLE IF NOT EXISTS ref_working_indicator (
    code INTEGER PRIMARY KEY,
    description VARCHAR(100) NOT NULL
);
COMMENT ON TABLE ref_working_indicator IS 'Working indicator codes.';

CREATE TABLE IF NOT EXISTS ref_homelessness (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_homelessness IS 'Homelessness status codes.';

CREATE TABLE IF NOT EXISTS ref_reporting_system (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_reporting_system IS 'Reporting system/requirement codes.';

CREATE TABLE IF NOT EXISTS ref_action_type (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_action_type IS 'Action type codes.';

CREATE TABLE IF NOT EXISTS ref_allotment_adjustment (
    code INTEGER PRIMARY KEY,
    description VARCHAR(200) NOT NULL
);
COMMENT ON TABLE ref_allotment_adjustment IS 'Allotment adjustment type codes.';


-- ============================================================================
-- MAIN TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- households: Household-level SNAP QC data
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS households (
    -- Primary Key
    case_id VARCHAR(50) NOT NULL,
    fiscal_year INTEGER NOT NULL,
    PRIMARY KEY (case_id, fiscal_year),
    
    -- Case Information
    case_classification INTEGER REFERENCES ref_case_classification(code),
    
    -- Geographic & Administrative
    region_code VARCHAR(10),
    state_code VARCHAR(2),  -- 2-letter state abbreviation (e.g., CA, TX). Use state_name for full name.
    state_name VARCHAR(50),  -- Full state name for geographic queries
    year_month VARCHAR(6),  -- YYYYMM format
    status INTEGER REFERENCES ref_status(code),  -- QC finding code (1,2,3), NOT geographic state
    stratum VARCHAR(20),
    
    -- Household Composition
    raw_household_size INTEGER,  -- Original household size before SNAP adjustments
    certified_household_size INTEGER,  -- USE THIS for "household size" queries
    snap_unit_size INTEGER,  -- SNAP unit size (may differ from certified size)
    num_noncitizens INTEGER DEFAULT 0,
    num_disabled INTEGER DEFAULT 0,
    num_elderly INTEGER DEFAULT 0,
    num_children INTEGER DEFAULT 0,
    composition_code VARCHAR(10),
    
    -- Financial Summary (monthly amounts in dollars)
    gross_income DECIMAL(12,2),  -- USE THIS for "income" or "total income" queries (before deductions)
    net_income DECIMAL(12,2),  -- Income AFTER deductions
    earned_income DECIMAL(12,2),  -- Wages, self-employment (subset of gross)
    unearned_income DECIMAL(12,2),  -- SSI, SSDI, etc. (subset of gross)
    
    -- Assets
    liquid_resources DECIMAL(12,2),
    real_property DECIMAL(12,2),
    vehicle_assets DECIMAL(12,2),
    total_assets DECIMAL(12,2),
    
    -- Deductions
    standard_deduction DECIMAL(10,2),
    earned_income_deduction DECIMAL(10,2),
    dependent_care_deduction DECIMAL(10,2),
    medical_deduction DECIMAL(10,2),
    shelter_deduction DECIMAL(10,2),
    total_deductions DECIMAL(10,2),
    
    -- Housing Expenses
    rent DECIMAL(10,2),
    utilities DECIMAL(10,2),
    shelter_expense DECIMAL(10,2),
    homeless_deduction DECIMAL(10,2),
    
    -- Benefits (monthly amounts in dollars)
    snap_benefit DECIMAL(10,2),  -- USE THIS for "benefit" queries (QC-corrected correct amount)
    raw_benefit DECIMAL(10,2),  -- Original benefit before QC correction (may be wrong)
    maximum_benefit DECIMAL(10,2),  -- Max allowed for household size
    minimum_benefit DECIMAL(10,2),  -- Minimum benefit amount
    
    -- Eligibility & Certification
    categorical_eligibility INTEGER REFERENCES ref_categorical_eligibility(code),
    expedited_service INTEGER REFERENCES ref_expedited_service(code),
    certification_month VARCHAR(6),
    last_certification_date INTEGER,
    
    -- Poverty & Work Status
    poverty_level DECIMAL(10,2),
    working_poor_indicator BOOLEAN,
    tanf_indicator BOOLEAN,
    
    -- QC Information
    amount_error DECIMAL(10,2),
    gross_test_result INTEGER,
    net_test_result INTEGER,
    
    -- Statistical Weights
    household_weight DECIMAL(18,8),
    fiscal_year_weight DECIMAL(18,8),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE households IS 'SNAP QC household-level records. One row per case per fiscal year.
This is the main table for household-level analysis.

COMMON QUERIES:
- How many households? SELECT COUNT(*) FROM households
- Households by state: SELECT state_name, COUNT(*) FROM households GROUP BY state_name
- Average income by state: SELECT state_name, AVG(gross_income) FROM households GROUP BY state_name
- Overissuance cases: SELECT * FROM households WHERE status = 2
- Underissuance cases: SELECT * FROM households WHERE status = 3
- Total benefits by year: SELECT fiscal_year, SUM(snap_benefit) FROM households GROUP BY fiscal_year
- Households with elderly: SELECT * FROM households WHERE num_elderly > 0
- Households with children: SELECT * FROM households WHERE num_children > 0
- Average benefit by household size: SELECT certified_household_size, AVG(snap_benefit) FROM households GROUP BY certified_household_size';

COMMENT ON COLUMN households.case_id IS 'Unique case identifier (HHLDNO)';
COMMENT ON COLUMN households.fiscal_year IS 'Federal fiscal year (October-September)';
COMMENT ON COLUMN households.state_name IS 'Full state name (e.g., California, Texas, New York). Use this column for "by state" or "by states" queries. NOT the same as status column.';
COMMENT ON COLUMN households.status IS 'QC finding code (NOT geographic state): 1=Correct, 2=Overissuance, 3=Underissuance. For geographic state use state_name column. JOIN ref_status for description';
COMMENT ON COLUMN households.gross_income IS 'Total monthly gross income BEFORE deductions. Use this for "total income" or "gross income" queries. For income after deductions use net_income';
COMMENT ON COLUMN households.net_income IS 'Monthly income AFTER deductions. Use gross_income for total/gross income queries';
COMMENT ON COLUMN households.snap_benefit IS 'QC-calculated CORRECT SNAP benefit amount. This is the accurate amount. Use this for benefit analysis. raw_benefit is the original (possibly incorrect) amount';
COMMENT ON COLUMN households.raw_benefit IS 'Originally issued SNAP benefit BEFORE QC correction (may be incorrect). Use snap_benefit for the correct amount';
COMMENT ON COLUMN households.amount_error IS 'Dollar amount of benefit error in households table (positive=overpaid, negative=underpaid). For individual error amounts see qc_errors.error_amount';
COMMENT ON COLUMN households.num_elderly IS 'Count of members age 60+';
COMMENT ON COLUMN households.num_children IS 'Count of members under 18';
COMMENT ON COLUMN households.certified_household_size IS 'SNAP-certified household size for benefit calculation. Use this for "household size" queries. raw_household_size is before certification adjustments';
COMMENT ON COLUMN households.categorical_eligibility IS 'Categorical eligibility: 1=Exempt from income/asset tests. JOIN ref_categorical_eligibility';
COMMENT ON COLUMN households.expedited_service IS 'Expedited service: 1=On time, 2=Late. JOIN ref_expedited_service';
COMMENT ON COLUMN households.state_code IS '2-letter state abbreviation (e.g., CA, TX). Prefer state_name for GROUP BY and display';
COMMENT ON COLUMN households.last_certification_date IS 'Last certification date as integer (YYYYMM format from source data). Not a DATE type — requires conversion for date arithmetic';

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_household_state_year ON households(state_name, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_household_fiscal_year ON households(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_household_status ON households(status);
CREATE INDEX IF NOT EXISTS idx_household_snap_benefit ON households(snap_benefit);


-- ----------------------------------------------------------------------------
-- household_members: Person-level data
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS household_members (
    -- Primary Key
    case_id VARCHAR(50) NOT NULL,
    fiscal_year INTEGER NOT NULL,
    member_number INTEGER NOT NULL,
    PRIMARY KEY (case_id, fiscal_year, member_number),
    FOREIGN KEY (case_id, fiscal_year) REFERENCES households(case_id, fiscal_year) ON DELETE CASCADE,
    
    -- Demographics
    age INTEGER CHECK (age >= 0 AND age <= 120),
    sex INTEGER REFERENCES ref_sex(code),
    race_ethnicity INTEGER,
    relationship_to_head INTEGER,
    citizenship_status INTEGER,
    years_education INTEGER,
    
    -- Status Indicators
    snap_affiliation_code INTEGER REFERENCES ref_snap_affiliation(code),
    disability_indicator INTEGER,
    foster_child_indicator INTEGER,
    work_registration_status INTEGER,
    abawd_status INTEGER,
    working_indicator INTEGER,
    
    -- Employment
    employment_region INTEGER,
    employment_status_a INTEGER,
    employment_status_b INTEGER,
    
    -- Earned Income Sources (monthly dollars)
    wages DECIMAL(10,2) DEFAULT 0,
    self_employment_income DECIMAL(10,2) DEFAULT 0,
    earned_income_tax_credit DECIMAL(10,2) DEFAULT 0,
    other_earned_income DECIMAL(10,2) DEFAULT 0,
    
    -- Unearned Income Sources (monthly dollars)
    social_security DECIMAL(10,2) DEFAULT 0,
    ssi DECIMAL(10,2) DEFAULT 0,
    veterans_benefits DECIMAL(10,2) DEFAULT 0,
    unemployment DECIMAL(10,2) DEFAULT 0,
    workers_compensation DECIMAL(10,2) DEFAULT 0,
    tanf DECIMAL(10,2) DEFAULT 0,
    child_support DECIMAL(10,2) DEFAULT 0,
    general_assistance DECIMAL(10,2) DEFAULT 0,
    education_loans DECIMAL(10,2) DEFAULT 0,
    other_government_income DECIMAL(10,2) DEFAULT 0,
    contributions DECIMAL(10,2) DEFAULT 0,
    deemed_income DECIMAL(10,2) DEFAULT 0,
    other_unearned_income DECIMAL(10,2) DEFAULT 0,
    
    -- Deductions & Expenses
    dependent_care_cost DECIMAL(10,2) DEFAULT 0,
    energy_assistance DECIMAL(10,2) DEFAULT 0,
    wage_supplement DECIMAL(10,2) DEFAULT 0,
    diversion_payment DECIMAL(10,2) DEFAULT 0,
    
    -- Calculated Fields
    total_earned_income DECIMAL(10,2),
    total_unearned_income DECIMAL(10,2),
    total_income DECIMAL(10,2),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE household_members IS 'Person-level data for household members. One row per person per household.
JOIN to households using (case_id, fiscal_year).

COMMON QUERIES:
- Members by age: SELECT age, COUNT(*) FROM household_members GROUP BY age
- Members by gender: SELECT sex, COUNT(*) FROM household_members GROUP BY sex
- Ineligible members: SELECT * FROM household_members WHERE snap_affiliation_code NOT IN (1, 2)
- Members with SSI: SELECT * FROM household_members WHERE ssi > 0
- Members with wages: SELECT * FROM household_members WHERE wages > 0
- Average wages by state: SELECT h.state_name, AVG(m.wages) FROM household_members m JOIN households h ON m.case_id = h.case_id AND m.fiscal_year = h.fiscal_year WHERE m.wages > 0 GROUP BY h.state_name';

COMMENT ON COLUMN household_members.member_number IS 'Member position in household (1-17)';
COMMENT ON COLUMN household_members.age IS 'Age in years (0=under 1, 98=98 or older)';
COMMENT ON COLUMN household_members.sex IS 'Gender: 1=Male, 2=Female. JOIN ref_sex for description';
COMMENT ON COLUMN household_members.snap_affiliation_code IS 'SNAP eligibility: 1-2=Eligible, others=Ineligible. JOIN ref_snap_affiliation';
COMMENT ON COLUMN household_members.wages IS 'Monthly wages and salaries';
COMMENT ON COLUMN household_members.ssi IS 'Supplemental Security Income (monthly)';
COMMENT ON COLUMN household_members.social_security IS 'RSDI/Social Security benefits (monthly)';
COMMENT ON COLUMN household_members.tanf IS 'TANF/Welfare benefits (monthly)';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_member_fiscal_year ON household_members(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_member_age ON household_members(age);
CREATE INDEX IF NOT EXISTS idx_member_affiliation ON household_members(snap_affiliation_code);


-- ----------------------------------------------------------------------------
-- qc_errors: Quality Control error findings
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qc_errors (
    -- Primary Key
    case_id VARCHAR(50) NOT NULL,
    fiscal_year INTEGER NOT NULL,
    error_number INTEGER NOT NULL,
    PRIMARY KEY (case_id, fiscal_year, error_number),
    FOREIGN KEY (case_id, fiscal_year) REFERENCES households(case_id, fiscal_year) ON DELETE CASCADE,
    
    -- Error Details
    element_code INTEGER REFERENCES ref_element(code),
    nature_code INTEGER REFERENCES ref_nature(code),
    responsible_agency INTEGER REFERENCES ref_agency_responsibility(code),
    error_amount DECIMAL(10,2),
    discovery_method INTEGER REFERENCES ref_discovery(code),
    verification_status INTEGER,
    
    -- Timing
    occurrence_date INTEGER,
    time_period VARCHAR(20),
    
    -- Finding
    error_finding INTEGER REFERENCES ref_error_finding(code),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE qc_errors IS 'Quality Control error findings. One row per error per household.
JOIN to households using (case_id, fiscal_year).
JOIN to ref_element, ref_nature, ref_agency_responsibility for descriptions.

COMMON QUERIES:
- Errors by type: SELECT re.description, COUNT(*) FROM qc_errors e JOIN ref_element re ON e.element_code = re.code GROUP BY re.description ORDER BY COUNT(*) DESC
- Errors by state: SELECT h.state_name, COUNT(*) FROM qc_errors e JOIN households h ON e.case_id = h.case_id AND e.fiscal_year = h.fiscal_year GROUP BY h.state_name
- Client vs agency errors: SELECT ra.responsibility_type, COUNT(*) FROM qc_errors e JOIN ref_agency_responsibility ra ON e.responsible_agency = ra.code GROUP BY ra.responsibility_type
- Total error amount by state: SELECT h.state_name, SUM(e.error_amount) FROM qc_errors e JOIN households h ON e.case_id = h.case_id AND e.fiscal_year = h.fiscal_year GROUP BY h.state_name
- Income errors: SELECT * FROM qc_errors WHERE element_code BETWEEN 311 AND 346
- Wage errors: SELECT * FROM qc_errors WHERE element_code = 311
- Asset errors: SELECT * FROM qc_errors WHERE element_code IN (211, 221, 222)
- Computation errors: SELECT * FROM qc_errors WHERE element_code = 520';

COMMENT ON COLUMN qc_errors.error_number IS 'Error sequence number for this household (1-9)';
COMMENT ON COLUMN qc_errors.element_code IS 'Error element type: 311=Wages, 321=SSI, 211=Assets. JOIN ref_element for description';
COMMENT ON COLUMN qc_errors.nature_code IS 'Nature of error: 35=Unreported income. JOIN ref_nature for description';
COMMENT ON COLUMN qc_errors.responsible_agency IS 'Who caused error. JOIN ref_agency_responsibility, use responsibility_type for client vs agency';
COMMENT ON COLUMN qc_errors.error_amount IS 'Dollar amount of THIS specific error (always positive/absolute value). Direction (over/under) is in error_finding column. For signed household-level total see households.amount_error';
COMMENT ON COLUMN qc_errors.error_finding IS 'Error finding: 2=Overissuance, 3=Underissuance, 4=Ineligible. JOIN ref_error_finding for description';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_error_fiscal_year ON qc_errors(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_error_element ON qc_errors(element_code);
CREATE INDEX IF NOT EXISTS idx_error_nature ON qc_errors(nature_code);
CREATE INDEX IF NOT EXISTS idx_error_amount ON qc_errors(error_amount);


-- ============================================================================
-- APPLICATION TABLES (app schema)
-- ============================================================================

CREATE TABLE IF NOT EXISTS app.user_prompts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    prompt_type VARCHAR(20) NOT NULL CHECK (prompt_type IN ('sql', 'kb')),
    prompt_text TEXT NOT NULL CHECK (LENGTH(prompt_text) >= 20 AND LENGTH(prompt_text) <= 5000),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, prompt_type)
);

COMMENT ON TABLE app.user_prompts IS 'Custom LLM prompts per user for SQL and KB insights.';

CREATE TABLE IF NOT EXISTS app.data_load_history (
    id SERIAL PRIMARY KEY,
    fiscal_year INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_size_bytes INTEGER,
    total_rows_in_file INTEGER,
    rows_loaded INTEGER,
    rows_skipped INTEGER,
    households_created INTEGER,
    members_created INTEGER,
    errors_created INTEGER,
    load_status VARCHAR(20) NOT NULL,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    loaded_by VARCHAR(100),
    load_method VARCHAR(50)
);

COMMENT ON TABLE app.data_load_history IS 'Tracking of data loading jobs.';


-- ============================================================================
-- ENRICHED VIEWS
-- Pre-joined views for common query patterns
-- ============================================================================

CREATE OR REPLACE VIEW v_households_enriched AS
SELECT 
    h.*,
    rs.description AS status_description,
    rce.description AS categorical_eligibility_description,
    res.description AS expedited_service_description
FROM households h
LEFT JOIN ref_status rs ON h.status = rs.code
LEFT JOIN ref_categorical_eligibility rce ON h.categorical_eligibility = rce.code
LEFT JOIN ref_expedited_service res ON h.expedited_service = res.code;

COMMENT ON VIEW v_households_enriched IS 'Households with reference table descriptions pre-joined.
Use this view for queries that need human-readable status descriptions.';

CREATE OR REPLACE VIEW v_qc_errors_enriched AS
SELECT 
    e.*,
    h.state_name,
    h.state_code,
    h.status AS household_status,
    re.description AS element_description,
    re.category AS element_category,
    rn.description AS nature_description,
    rn.category AS nature_category,
    ra.description AS agency_description,
    ra.responsibility_type,
    rf.description AS finding_description
FROM qc_errors e
JOIN households h ON e.case_id = h.case_id AND e.fiscal_year = h.fiscal_year
LEFT JOIN ref_element re ON e.element_code = re.code
LEFT JOIN ref_nature rn ON e.nature_code = rn.code
LEFT JOIN ref_agency_responsibility ra ON e.responsible_agency = ra.code
LEFT JOIN ref_error_finding rf ON e.error_finding = rf.code;

COMMENT ON VIEW v_qc_errors_enriched IS 'QC errors with all reference tables and household info pre-joined.
Use this view for comprehensive error analysis with human-readable descriptions.
Example: SELECT element_description, COUNT(*) FROM v_qc_errors_enriched GROUP BY element_description';


-- ============================================================================
-- ANALYTICAL TABLES AND VIEWS
-- Pre-computed aggregations for common analyst queries
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ref_tolerance_threshold: USDA tolerance thresholds by fiscal year
-- Eliminates hardcoded values in error rate calculations
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_tolerance_threshold (
    fiscal_year INTEGER PRIMARY KEY,
    threshold_amount DECIMAL(10,2) NOT NULL,
    source_note VARCHAR(200)
);

COMMENT ON TABLE ref_tolerance_threshold IS 'USDA tolerance thresholds by fiscal year for Payment Error Rate calculation.
Errors with ABS(amount_error) <= threshold are excluded from official error rates.
Updated annually by USDA/FNS based on Thrifty Food Plan adjustments.
Example: SELECT threshold_amount FROM ref_tolerance_threshold WHERE fiscal_year = 2023';

INSERT INTO ref_tolerance_threshold (fiscal_year, threshold_amount, source_note) VALUES
(2021, 39.00, 'FY2021 tolerance threshold based on Thrifty Food Plan'),
(2022, 48.00, 'FY2022 tolerance threshold based on Thrifty Food Plan'),
(2023, 54.00, 'FY2023 tolerance threshold based on Thrifty Food Plan')
ON CONFLICT (fiscal_year) DO NOTHING;

-- ----------------------------------------------------------------------------
-- fns_error_rates_historical: Official FNS-published error rates
-- For comparing computed rates to official published rates
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fns_error_rates_historical (
    fiscal_year INTEGER NOT NULL,
    state_name VARCHAR(50) NOT NULL,
    PRIMARY KEY (fiscal_year, state_name),
    payment_error_rate DECIMAL(6,4),
    overpayment_rate DECIMAL(6,4),
    underpayment_rate DECIMAL(6,4),
    case_error_rate DECIMAL(6,4),
    sample_size INTEGER,
    completion_rate DECIMAL(5,2),
    source_document VARCHAR(200),
    notes TEXT
);

COMMENT ON TABLE fns_error_rates_historical IS 'Official FNS-published SNAP QC error rates from annual reports.
These are FINAL official rates after FNS arbitration and adjustments.
Compare with mv_state_error_rates (computed from raw QC sample) to identify differences.
Use state_name = ''National'' for national-level rates.
Example: SELECT fiscal_year, payment_error_rate FROM fns_error_rates_historical WHERE state_name = ''National'' ORDER BY fiscal_year';

CREATE INDEX IF NOT EXISTS idx_fns_historical_fy ON fns_error_rates_historical(fiscal_year);

-- ----------------------------------------------------------------------------
-- mv_state_error_rates: Pre-computed state-level error rates by fiscal year
-- The #1 most-used analytical query, pre-computed for instant access
-- ----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_state_error_rates AS
WITH base AS (
    SELECT
        h.fiscal_year,
        h.state_name,
        h.state_code,
        COALESCE(t.threshold_amount, 54) AS tolerance_threshold,
        COUNT(*) AS total_sample_cases,
        COUNT(*) FILTER (WHERE h.status != 1) AS error_sample_cases,
        COUNT(*) FILTER (WHERE h.status = 2) AS overissuance_sample_cases,
        COUNT(*) FILTER (WHERE h.status = 3) AS underissuance_sample_cases,
        SUM(h.household_weight) AS estimated_total_households,
        SUM(h.snap_benefit * h.household_weight) AS total_weighted_benefits,
        SUM(CASE WHEN ABS(h.amount_error) > COALESCE(t.threshold_amount, 54)
            THEN ABS(h.amount_error) * h.household_weight ELSE 0 END
        ) AS total_weighted_error_dollars,
        SUM(CASE WHEN h.amount_error > COALESCE(t.threshold_amount, 54)
            THEN h.amount_error * h.household_weight ELSE 0 END
        ) AS weighted_overpayment_dollars,
        SUM(CASE WHEN h.amount_error < -COALESCE(t.threshold_amount, 54)
            THEN ABS(h.amount_error) * h.household_weight ELSE 0 END
        ) AS weighted_underpayment_dollars,
        SUM(h.snap_benefit * h.household_weight) / NULLIF(SUM(h.household_weight), 0) AS avg_weighted_benefit,
        SUM(h.gross_income * h.household_weight) / NULLIF(SUM(h.household_weight), 0) AS avg_weighted_gross_income
    FROM households h
    LEFT JOIN ref_tolerance_threshold t ON h.fiscal_year = t.fiscal_year
    WHERE h.case_classification = 1
    GROUP BY h.fiscal_year, h.state_name, h.state_code, t.threshold_amount
)
SELECT
    fiscal_year,
    state_name,
    state_code,
    tolerance_threshold,
    total_sample_cases,
    error_sample_cases,
    overissuance_sample_cases,
    underissuance_sample_cases,
    estimated_total_households,
    total_weighted_benefits,
    avg_weighted_benefit,
    avg_weighted_gross_income,
    ROUND((total_weighted_error_dollars / NULLIF(total_weighted_benefits, 0)) * 100, 4) AS payment_error_rate,
    ROUND((weighted_overpayment_dollars / NULLIF(total_weighted_benefits, 0)) * 100, 4) AS overpayment_rate,
    ROUND((weighted_underpayment_dollars / NULLIF(total_weighted_benefits, 0)) * 100, 4) AS underpayment_rate,
    ROUND((error_sample_cases::NUMERIC / NULLIF(total_sample_cases::NUMERIC, 0)) * 100, 2) AS case_error_rate,
    total_weighted_error_dollars,
    weighted_overpayment_dollars,
    weighted_underpayment_dollars
FROM base
ORDER BY fiscal_year, state_name;

COMMENT ON MATERIALIZED VIEW mv_state_error_rates IS 'Pre-computed state-level SNAP QC error rates by fiscal year. Includes official USDA payment error rate, overpayment rate, underpayment rate, and case error rate. Uses case_classification = 1 and year-specific tolerance thresholds from ref_tolerance_threshold. REFRESH with: REFRESH MATERIALIZED VIEW mv_state_error_rates. Example: SELECT state_name, payment_error_rate FROM mv_state_error_rates WHERE fiscal_year = 2023 ORDER BY payment_error_rate DESC';

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_state_error_rates ON mv_state_error_rates(fiscal_year, state_name);

-- ----------------------------------------------------------------------------
-- mv_error_element_rollup: Pre-aggregated error analysis for corrective action
-- ----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_error_element_rollup AS
SELECT
    h.fiscal_year,
    h.state_name,
    re.code AS element_code,
    re.description AS element_description,
    re.category AS element_category,
    rf.description AS finding_type,
    ra.responsibility_type,
    COUNT(*) AS sample_error_count,
    SUM(e.error_amount * h.household_weight) AS weighted_error_dollars,
    AVG(e.error_amount) AS avg_sample_error_amount
FROM qc_errors e
JOIN households h ON e.case_id = h.case_id AND e.fiscal_year = h.fiscal_year
JOIN ref_element re ON e.element_code = re.code
LEFT JOIN ref_error_finding rf ON e.error_finding = rf.code
LEFT JOIN ref_agency_responsibility ra ON e.responsible_agency = ra.code
WHERE h.case_classification = 1
GROUP BY h.fiscal_year, h.state_name, re.code, re.description, re.category,
         rf.description, ra.responsibility_type;

COMMENT ON MATERIALIZED VIEW mv_error_element_rollup IS 'Pre-aggregated error element analysis with weighted dollar impact. Use for corrective action prioritization: which error types drive the most dollars? Includes element category, finding type (over/under/ineligible), and responsibility (client/agency). REFRESH with: REFRESH MATERIALIZED VIEW mv_error_element_rollup. Example: SELECT element_description, SUM(weighted_error_dollars) FROM mv_error_element_rollup WHERE fiscal_year = 2023 AND finding_type = ''Overissuance'' GROUP BY element_description ORDER BY SUM(weighted_error_dollars) DESC';

CREATE INDEX IF NOT EXISTS idx_mv_error_rollup_fy_state ON mv_error_element_rollup(fiscal_year, state_name);
CREATE INDEX IF NOT EXISTS idx_mv_error_rollup_category ON mv_error_element_rollup(element_category);

-- ----------------------------------------------------------------------------
-- mv_demographic_profile: Pre-aggregated demographics for equity analysis
-- ----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_demographic_profile AS
SELECT
    h.fiscal_year,
    h.state_name,
    CASE
        WHEN m.age < 6 THEN 'Under 6'
        WHEN m.age BETWEEN 6 AND 17 THEN '6-17'
        WHEN m.age BETWEEN 18 AND 24 THEN '18-24'
        WHEN m.age BETWEEN 25 AND 49 THEN '25-49'
        WHEN m.age BETWEEN 50 AND 59 THEN '50-59'
        WHEN m.age >= 60 THEN '60+'
    END AS age_group,
    rre.description AS race_ethnicity,
    rcs.description AS citizenship_status,
    rel.description AS education_level,
    CASE WHEN m.working_indicator = 1 THEN 'Working' ELSE 'Not Working' END AS working_status,
    CASE WHEN m.disability_indicator = 1 THEN 'Disabled' ELSE 'Not Disabled' END AS disability_status,
    COUNT(*) AS sample_member_count,
    SUM(h.household_weight) AS estimated_member_count
FROM household_members m
JOIN households h ON m.case_id = h.case_id AND m.fiscal_year = h.fiscal_year
LEFT JOIN ref_race_ethnicity rre ON m.race_ethnicity = rre.code
LEFT JOIN ref_citizenship_status rcs ON m.citizenship_status = rcs.code
LEFT JOIN ref_education_level rel ON m.years_education = rel.code
WHERE m.snap_affiliation_code IN (1, 2)
GROUP BY h.fiscal_year, h.state_name, age_group, rre.description, rcs.description,
         rel.description, working_status, disability_status;

COMMENT ON MATERIALIZED VIEW mv_demographic_profile IS 'Pre-aggregated demographic profile of eligible SNAP members by state and fiscal year. Covers age, race/ethnicity, citizenship, education, employment, and disability. Only includes eligible members (snap_affiliation_code IN (1,2)). REFRESH with: REFRESH MATERIALIZED VIEW mv_demographic_profile. Example: SELECT race_ethnicity, SUM(estimated_member_count) FROM mv_demographic_profile WHERE fiscal_year = 2023 GROUP BY race_ethnicity ORDER BY SUM(estimated_member_count) DESC';

CREATE INDEX IF NOT EXISTS idx_mv_demo_fy_state ON mv_demographic_profile(fiscal_year, state_name);

-- ----------------------------------------------------------------------------
-- v_household_summary: Household-level segmentation view
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_household_summary AS
SELECT
    h.case_id,
    h.fiscal_year,
    h.state_name,
    h.state_code,
    h.status,
    rs.description AS status_description,
    h.snap_benefit,
    h.raw_benefit,
    h.amount_error,
    h.gross_income,
    h.net_income,
    h.earned_income,
    h.unearned_income,
    h.total_deductions,
    h.certified_household_size,
    h.num_elderly,
    h.num_children,
    h.num_disabled,
    h.num_noncitizens,
    h.categorical_eligibility,
    h.expedited_service,
    h.working_poor_indicator,
    h.tanf_indicator,
    h.poverty_level,
    h.household_weight,
    h.case_classification,
    -- Household type classification
    CASE
        WHEN h.num_elderly > 0 AND h.num_children = 0 AND h.certified_household_size = h.num_elderly THEN 'Elderly Only'
        WHEN h.num_children > 0 AND h.num_elderly = 0 THEN 'With Children (No Elderly)'
        WHEN h.num_elderly > 0 AND h.num_children > 0 THEN 'Elderly and Children'
        WHEN h.certified_household_size = 1 AND h.num_elderly = 0 THEN 'Single Adult'
        ELSE 'Other Adult'
    END AS household_type,
    -- Income category
    CASE
        WHEN h.gross_income = 0 OR h.gross_income IS NULL THEN 'Zero Income'
        WHEN h.earned_income > 0 AND h.unearned_income = 0 THEN 'Earned Income Only'
        WHEN h.earned_income = 0 AND h.unearned_income > 0 THEN 'Unearned Income Only'
        WHEN h.earned_income > 0 AND h.unearned_income > 0 THEN 'Mixed Income'
        ELSE 'Unknown'
    END AS income_category,
    -- Error classification with tolerance
    CASE
        WHEN h.status = 1 THEN 'No Error'
        WHEN h.status = 2 AND ABS(h.amount_error) > COALESCE(t.threshold_amount, 54) THEN 'Overissuance (Above Tolerance)'
        WHEN h.status = 2 THEN 'Overissuance (Within Tolerance)'
        WHEN h.status = 3 AND ABS(h.amount_error) > COALESCE(t.threshold_amount, 54) THEN 'Underissuance (Above Tolerance)'
        WHEN h.status = 3 THEN 'Underissuance (Within Tolerance)'
        ELSE 'Unknown'
    END AS error_classification
FROM households h
LEFT JOIN ref_status rs ON h.status = rs.code
LEFT JOIN ref_tolerance_threshold t ON h.fiscal_year = t.fiscal_year;

COMMENT ON VIEW v_household_summary IS 'Household-level summary with pre-computed household type, income category, and error classification.
Uses ref_tolerance_threshold to distinguish above/below tolerance errors.
Example: SELECT household_type, COUNT(*), SUM(household_weight) FROM v_household_summary WHERE fiscal_year = 2023 GROUP BY household_type';

-- ----------------------------------------------------------------------------
-- Additional indexes for common analytical query patterns
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_household_case_classification ON households(case_classification);
CREATE INDEX IF NOT EXISTS idx_household_class_fy ON households(case_classification, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_member_race_ethnicity ON household_members(race_ethnicity);
CREATE INDEX IF NOT EXISTS idx_member_citizenship ON household_members(citizenship_status);
CREATE INDEX IF NOT EXISTS idx_member_work_reg ON household_members(work_registration_status);
CREATE INDEX IF NOT EXISTS idx_member_working ON household_members(working_indicator);
CREATE INDEX IF NOT EXISTS idx_member_disability ON household_members(disability_indicator);


-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
