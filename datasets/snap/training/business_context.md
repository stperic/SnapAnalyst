SNAP QC Database - Domain Context

PROGRAM TERMS:
- SNAP = Supplemental Nutrition Assistance Program (formerly "food stamps")
- QC = Quality Control — federal review process to ensure benefit accuracy
- FNS = Food and Nutrition Service (USDA agency administering SNAP)
- PER = Payment Error Rate (official USDA metric for SNAP accuracy)
- Overissuance = household received more benefits than entitled (amount_error > 0)
- Underissuance = household received less benefits than entitled (amount_error < 0)
- RSDI = Retirement, Survivors, and Disability Insurance (Social Security)
- SSI = Supplemental Security Income
- TANF = Temporary Assistance for Needy Families (welfare/cash assistance)
- ABAWD = Able-Bodied Adults Without Dependents (subject to work requirements)
- BBCE = Broad-Based Categorical Eligibility (categorical_eligibility = 2)
- Fiscal year = October through September (e.g., FY2023 = Oct 2022 – Sep 2023)

TABLES AND RELATIONSHIPS:
- households: One row per case per fiscal year. Contains state_name, income, benefits, case status, sampling weights. Composite PK: (case_id, fiscal_year).
- household_members: One row per person per case. Contains age, sex, income sources, disability. FK to households via (case_id, fiscal_year).
- qc_errors: One row per error finding per case. Contains element_code, nature_code, error_amount. FK to households via (case_id, fiscal_year).
- ref_* tables: Lookup/reference tables. JOIN via code columns for human-readable descriptions.
- state_name is ONLY in the households table.

KEY HOUSEHOLD COLUMNS:
- snap_benefit: QC-corrected correct benefit amount (use for analysis)
- raw_benefit: Original agency-issued benefit (may differ from snap_benefit if error found)
- amount_error: Dollar error = raw_benefit minus snap_benefit. Positive = overpaid, negative = underpaid. This is a SIGNED value.
- gross_income: Total household income BEFORE deductions
- net_income: Income AFTER all deductions (drives benefit calculation)
- certified_household_size: Number of people in the SNAP unit (use for "household size")
- num_elderly: Members age 60+ (SNAP elderly threshold is 60, not 65)
- num_children: Members under 18
- num_disabled: Members with disability
- num_noncitizens: Noncitizen members
- household_weight: Monthly statistical sampling weight (use for weighted estimates)
- case_classification: 1=included in official error rates, 2=excluded SSA, 3=excluded FNS
- status: QC finding code (1=correct, 2=overissuance, 3=underissuance)
- categorical_eligibility: 1=categorically eligible (exempt from income/asset tests), 2=BBCE
- expedited_service: 1=entitled and received on time, 2=entitled but late, 3=not entitled

ADDITIONAL HOUSEHOLD COLUMNS:
- poverty_level: Gross income as % of Federal Poverty Level (130% FPL is SNAP gross income limit)
- working_poor_indicator: Boolean flag for households with earned income still eligible for SNAP
- tanf_indicator: Boolean flag for households also receiving TANF (welfare)
- gross_test_result: Whether household passed the gross income test (130% FPL)
- net_test_result: Whether household passed the net income test (100% FPL)

KEY MEMBER COLUMNS (household_members):
- age: Member age (0-98). 60+ = elderly for SNAP purposes.
- sex: Gender code (JOIN ref_sex for description)
- snap_affiliation_code: 1-2 = eligible participant, all others = ineligible (JOIN ref_snap_affiliation)
- race_ethnicity: Race/ethnicity code (JOIN ref_race_ethnicity) — required for FNS civil rights reporting
- citizenship_status: Immigration/citizenship status (JOIN ref_citizenship_status; 1-2 = US citizen, others = noncitizen categories)
- relationship_to_head: Family relationship (JOIN ref_relationship; head, spouse, child, parent, etc.)
- years_education: Education level (JOIN ref_education_level)
- employment_status_a: Detailed employment status (JOIN ref_employment_status_type; self-employed, farm worker, looking for work, etc.)
- work_registration_status: Work registration compliance (JOIN ref_work_registration; registrant, exempt, etc.)
- abawd_status: ABAWD work requirement status (JOIN ref_abawd_status; code 1 = not ABAWD)
- wages: Employment wages and salaries
- ssi: Supplemental Security Income amount
- social_security: RSDI benefits
- disability_indicator: 0=not disabled, 1=disabled
- working_indicator: 0=not working, 1=working

KEY ERROR COLUMNS (qc_errors):
- element_code: What area had the error (JOIN ref_element). Always a positive value.
- nature_code: What went wrong (JOIN ref_nature). Root cause of the error.
- error_amount: Dollar amount of THIS specific error. Always positive (absolute value). Direction is in error_finding.
- error_finding: Impact on benefits (JOIN ref_error_finding: 2=Overissuance, 3=Underissuance, 4=Ineligible)
- responsible_agency: Who caused the error (JOIN ref_agency_responsibility)
NOTE: qc_errors.error_amount is always positive. Use households.amount_error for signed dollar impact.

REFERENCE TABLE CATEGORIES:
ref_element.category groups error types:
- 'eligibility': certification period, residency, citizenship, work registration
- 'assets': countable assets, vehicles, resources
- 'earned_income': wages and salaries, self-employment income
- 'unearned_income': social security, SSI, veterans benefits, child support, TANF
- 'deductions': earned income deduction, shelter, dependent care, child support, medical, standard
- 'income_totals': gross income total, net income total
- 'computation': arithmetic errors, transitional benefits, reporting systems

ref_nature.category groups error causes:
- 'income': unreported or incorrectly reported income/earnings
- 'composition': household member inclusion/exclusion errors (persons added/removed)
- 'deduction': missing or incorrect deductions
- 'resources': resource/asset errors
- 'computation': arithmetic, transcription, or rounding errors
- 'reporting': reporting system or budgeting method errors
- 'benefits': benefit/allotment calculation or proration errors
NOTE: Some nature codes may have NULL category if they don't match a keyword pattern.

ref_agency_responsibility.responsibility_type:
- 'client': client information/verification errors (codes 1-4, 7-8)
- 'agency': agency policy/processing errors (codes 10, 12, 14-21)
- 'other': unclassified (code 99)
NOTE: Some reserved codes (22, 26) may have NULL responsibility_type.

INELIGIBLE CASES:
When error_finding = 4 (Ineligible), the household should not have received ANY benefits. The entire snap_benefit represents the error for these cases. This is distinct from overissuance (partial error) where only the difference is wrong.

WEIGHTED VS UNWEIGHTED — CRITICAL:
The QC database is a SAMPLE (~50,000 cases per year representing 22+ million households). For correct results:
- POPULATION-LEVEL ESTIMATES (total households, total benefits, average income, demographics): ALWAYS multiply by household_weight. Use SUM(column * household_weight) for totals, SUM(column * household_weight) / SUM(household_weight) for weighted averages, SUM(household_weight) instead of COUNT(*) for population counts.
- SAMPLE-LEVEL COUNTS (number of cases in the sample, sample adequacy, case error rate): Use unweighted COUNT(*). Label as "sample_count" to distinguish from population estimates.
- ROW-LEVEL LISTINGS (LIMIT 100 queries showing individual cases): No weighting needed.
- ERROR RATES: The official Payment Error Rate uses weighted formula. The Case Error Rate is unweighted (sample percentage).
If unsure, use weighted — it is almost always the correct choice for analytical questions.

ABAWD ANALYSIS:
- abawd_status is in household_members table (JOIN ref_abawd_status for descriptions)
- Code 1 = not an ABAWD; other codes indicate ABAWD status and work requirement compliance
- ABAWD work requirements are a major policy focus area for state agencies

EXPEDITED SERVICE COMPLIANCE:
- expedited_service: 1=entitled and received on time, 2=entitled but late, 3=not entitled
- Late rate = cases with code 2 / cases with code 1 or 2 — an FNS reporting metric

ERROR DISCOVERY METHODS:
- discovery_method in qc_errors (JOIN ref_discovery for descriptions)
- Methods include: case record review, client interview, employer verification, financial institution, government match
- Understanding discovery methods helps evaluate QC methodology effectiveness

2-YEAR ROLLING ERROR RATES:
FNS calculates error rates on a 2-year rolling basis for state liability determination. Combine two fiscal years in a single query, applying per-year tolerance thresholds via CASE expression.

PRE-COMPUTED ANALYTICAL VIEWS:
For common analytical queries, use these pre-computed tables/views instead of re-deriving complex formulas:

- ref_tolerance_threshold: USDA tolerance thresholds by fiscal year. Eliminates hardcoded threshold values. Query: SELECT threshold_amount FROM ref_tolerance_threshold WHERE fiscal_year = 2023

- mv_state_error_rates: Pre-computed state-level error rates by fiscal year. Includes payment_error_rate, overpayment_rate, underpayment_rate, case_error_rate, plus weighted totals. Uses case_classification = 1 and year-specific thresholds. REFRESH after data loads.

- mv_error_element_rollup: Pre-aggregated error analysis by element, state, year, finding type, and responsibility. Includes weighted_error_dollars for corrective action prioritization. Query: SELECT element_description, SUM(weighted_error_dollars) FROM mv_error_element_rollup WHERE fiscal_year = 2023 GROUP BY element_description ORDER BY SUM(weighted_error_dollars) DESC

- mv_demographic_profile: Pre-aggregated demographics (age, race/ethnicity, citizenship, education, employment, disability) of eligible SNAP members by state/year. Weighted population counts. Use for equity analysis and FNS civil rights reporting.

- v_household_summary: Household-level view with pre-classified household_type (Elderly Only, With Children, Single Adult, etc.), income_category (Earned Only, Unearned Only, Mixed, Zero Income), and error_classification (Above/Within Tolerance).

- fns_error_rates_historical: Official FNS-published error rates. Compare against mv_state_error_rates to validate computed rates. Use state_name = 'National' for national rates.
