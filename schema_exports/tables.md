# SnapAnalyst Schema Export

Generated: 2026-01-14 00:01:48

## Database Tables

### households

**Description:** Core household case data. Each row represents one SNAP household case from quality control review.

**Row Count:** ~50,000 per fiscal year

**Primary Key:** id


#### Columns

| Column | Type | Description | Range | Example |
|--------|------|-------------|-------|---------|
| id | SERIAL PRIMARY KEY | Internal database ID (auto-generated) |  |  |
| case_id | VARCHAR(50) | SNAP household identification number (row number from source file - unique unit identifier) | 1-55115 | 12345 |
| case_classification | INTEGER | Case classification for error rate calculation | 1-3 |  |
| fiscal_year | INTEGER | Fiscal year of the quality control review | 2021-2023 | 2023 |
| state_code | VARCHAR(2) | FIPS code for State or territory (numeric) | 1-78 | 9 |
| state_name | VARCHAR(50) | State or territory name |  | Connecticut |
| year_month | VARCHAR(6) | Sample year and month in YYYYMM format | 202210-202309 | 202210 |
| status | INTEGER | Status of case error findings | 1-3 | 1 |
| snap_benefit | DECIMAL(10,2) | Final calculated benefit (SNAP benefit allotment) | 4-3690 | 281.0 |
| raw_benefit | DECIMAL(10,2) | Reported SNAP benefit received (before QC corrections) | 0-9998 | 281.0 |
| amount_error | DECIMAL(10,2) | Amount of benefit in error | 0-1265 | 0.0 |
| maximum_benefit | DECIMAL(10,2) | Maximum benefit amount for unit size and region | 281-4092 | 281.0 |
| minimum_benefit | DECIMAL(10,2) | Minimum benefit amount | 23-44 | 23.0 |
| gross_income | DECIMAL(12,2) | Final gross countable unit income | 0-9488 | 561.0 |
| net_income | DECIMAL(12,2) | Final net countable income after deductions | 0-8499 | 0.0 |
| earned_income | DECIMAL(12,2) | Countable unit earned income | 0-8365 | 0.0 |
| unearned_income | DECIMAL(12,2) | Countable unit unearned income | 0-6863 | 561.0 |
| certified_household_size | INTEGER | Certified unit size | 1-17 | 1 |
| raw_household_size | INTEGER | Reported number of people in household | 1-16 | 1 |
| snap_unit_size | INTEGER | Constructed certified unit size | 1-17 | 1 |
| num_elderly | INTEGER | Number of elderly individuals in unit (age 60+) | 0-2 | 1 |
| num_children | INTEGER | Number of children in unit (under 18) | 0-15 | 0 |
| num_disabled | INTEGER | Number of non-elderly individuals with disabilities | 0-7 | 0 |
| num_noncitizens | INTEGER | Number of noncitizens in unit | 0-10 | 0 |
| poverty_level | DECIMAL(10,2) | Gross income/poverty level ratio | 0-621 | 50.0 |
| categorical_eligibility | INTEGER | Indicator of categorical eligibility status | 0-2 | 1 |
| expedited_service | INTEGER | Received expedited service indicator | 1-3 | 3 |
| working_poor_indicator | BOOLEAN | Indicator of working poor unit |  | False |
| tanf_indicator | BOOLEAN | Indicator of TANF receipt for unit |  | False |
| standard_deduction | DECIMAL(10,2) | Standard deduction | 170-515 | 193.0 |
| earned_income_deduction | DECIMAL(10,2) | Calculated earned income deduction | 0-1673 | 0.0 |
| dependent_care_deduction | DECIMAL(10,2) | Reported dependent care deduction | 0-3844 | 0.0 |
| medical_deduction | DECIMAL(10,2) | Calculated medical expense deduction | 0-1978 | 0.0 |
| shelter_deduction | DECIMAL(10,2) | Calculated excess shelter expense deduction | 0-4675 | 837.0 |
| total_deductions | DECIMAL(10,2) | Total deductions | 0-7056 | 1030.0 |
| rent | DECIMAL(10,2) | Rent/mortgage amount | 0-4721 | 100.0 |
| utilities | DECIMAL(10,2) | Utility amount | 0-1075 | 921.0 |
| shelter_expense | DECIMAL(10,2) | Calculated shelter expenses | 0-5360 | 0.0 |
| liquid_resources | DECIMAL(12,2) | Countable liquid assets under State rules | 0-8402 | 0.0 |
| real_property | DECIMAL(12,2) | Countable real property under State rules | 0-2500 | 0.0 |
| vehicle_assets | DECIMAL(12,2) | Countable non-excluded vehicles' value | 0-2825 | 0.0 |
| total_assets | DECIMAL(12,2) | Total countable assets under State rules | 0-8402 | 0.0 |
| certification_month | VARCHAR(6) | Months in certification period | 0-95 | 36 |
| last_certification_date | INTEGER | Date case was certified/recertified in YYYYMMDD format | 20130213-20230930 | 20221015 |
| gross_test_result | INTEGER | Indicator of passing gross income test | 0-1 | 1 |
| net_test_result | INTEGER | Indicator of passing net income test | 0-1 | 1 |
| household_weight | DECIMAL(18,8) | Monthly sample weight | 45.99-78335.51 | 3382.9227541 |
| fiscal_year_weight | DECIMAL(18,8) | Weight used for full-year calculations | 3.83-6527.96 | 281.9102295 |
| region_code | VARCHAR(10) | FNS region code | 1-7 | 1 |
| stratum | VARCHAR(20) | Stratum identification | 0-0 | 0 |
| composition_code | VARCHAR(10) | Unit composition code | 0-5 | 0 |
| homeless_deduction | DECIMAL(10,2) | Amount of homeless household shelter deduction | 0-167 | 0.0 |
| created_at | TIMESTAMP | Record creation timestamp |  |  |
| updated_at | TIMESTAMP | Record last update timestamp |  |  |

---

### household_members

**Description:** Individual household member data. Each household has 1-17 members.

**Row Count:** ~120,000 (about 2.4 members per household average)

**Primary Key:** id


#### Columns

| Column | Type | Description | Range | Example |
|--------|------|-------------|-------|---------|
| id | SERIAL PRIMARY KEY | Internal database ID (auto-generated) |  |  |
| household_id | INTEGER | Foreign key to households table |  |  |
| member_number | INTEGER | Member position in household (1-17) | 1-17 | 1 |
| age | INTEGER | Age in years | 0-98 | 62 |
| sex | INTEGER | Sex of member | 1-3 |  |
| snap_affiliation_code | INTEGER | SNAP case affiliation - member's participation status | 1-99 |  |
| disability_indicator | INTEGER | Person-level disability indicator | 0-1 |  |
| foster_child_indicator | INTEGER | Foster child status |  |  |
| working_indicator | INTEGER | Person-level working indicator | 0-1 |  |
| wages | DECIMAL(10,2) | Countable wages and salaries | 0-7526 | 0.0 |
| self_employment_income | DECIMAL(10,2) | Countable self-employment income | 0-5210 | 0.0 |
| social_security | DECIMAL(10,2) | Countable Social Security income (RSDI) | 0-6800 | 561.0 |
| ssi | DECIMAL(10,2) | Countable SSI benefits | 0-2406 | 0.0 |
| unemployment | DECIMAL(10,2) | Countable unemployment compensation | 0-3254 | 0.0 |
| tanf | DECIMAL(10,2) | Countable TANF payments | 0-2185 | 0.0 |
| child_support | DECIMAL(10,2) | Countable child support payment income | 0-2561 | 0.0 |
| veterans_benefits | DECIMAL(10,2) | Countable veterans' benefits | 0-4273 | 0.0 |
| workers_compensation | DECIMAL(10,2) | Countable workers' compensation benefits | 0-4441 | 0.0 |
| total_earned_income | DECIMAL(10,2) | Sum of all earned income sources (calculated field) |  |  |
| total_unearned_income | DECIMAL(10,2) | Sum of all unearned income sources (calculated field) |  |  |
| total_income | DECIMAL(10,2) | Total income (earned + unearned) (calculated field) |  |  |

---

### qc_errors

**Description:** Quality Control errors (variances) found during review. Up to 9 errors per household.

**Row Count:** ~20,000 errors across all households

**Primary Key:** id


#### Columns

| Column | Type | Description | Range | Example |
|--------|------|-------------|-------|---------|
| id | SERIAL PRIMARY KEY | Internal database ID (auto-generated) |  |  |
| household_id | INTEGER | Foreign key to households table |  |  |
| error_number | INTEGER | Error sequence number for this household (1-9) | 1-9 | 1 |
| element_code | INTEGER | Variance element - type of problem area | 111-820 | 520 |
| nature_code | INTEGER | Nature of variance - what went wrong | 6-309 | 75 |
| responsible_agency | INTEGER | Agency or client responsibility | 1-99 | 17 |
| error_amount | DECIMAL(10,2) | Variance dollar amount | 0-1480 | 57.0 |
| discovery_method | INTEGER | How variance was discovered | 1-9 | 2 |
| verification_status | INTEGER | How variance was verified | 1-9 | 2 |
| occurrence_date | INTEGER | Variance occurrence date in YYYYMM format | 200112-999999 | 202210 |
| time_period | VARCHAR(20) | Variance time period | 1-9 | 3 |
| error_finding | INTEGER | Impact of variance on benefits | 2-4 | 3 |
| created_at | TIMESTAMP | Record creation timestamp |  |  |

---
