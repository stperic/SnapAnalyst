# SnapAnalyst Schema Export

Generated: 2026-01-14 00:01:48

## Code Lookup Tables

### case_classification_codes

**Description:** Case classification for error rate calculation

**Source Field:** CASE


| Code | Description |
|------|-------------|
| 1 | Included in error rate calculation |
| 2 | Excluded from error rate calculation—processed by SSA worker |
| 3 | Excluded from error rate calculation, as designated by FNS (for example, demonstration project, simplified SNAP) |


### status_codes

**Description:** Status of case error findings

**Source Field:** STATUS


| Code | Description |
|------|-------------|
| 1 | Amount correct |
| 2 | Overissuance |
| 3 | Underissuance |


### expedited_service_codes

**Description:** Whether household received expedited SNAP benefits

**Source Field:** EXPEDSER


| Code | Description |
|------|-------------|
| 1 | Entitled to expedited service and received benefits within Federal time frame |
| 2 | Entitled to expedited service but did not receive benefits within Federal time frame |
| 3 | Not entitled to expedited service |


### categorical_eligibility_codes

**Description:** Indicator of categorical eligibility status

**Source Field:** CAT_ELIG


| Code | Description |
|------|-------------|
| 0 | Unit not categorically eligible for benefits |
| 1 | Unit reported as categorically eligible for benefits and therefore not subject to SNAP income or asset tests |
| 2 | Unit recoded as categorically eligible after being identified as pure cash PA or as meeting State-specified criteria for BBCE |


### error_finding_codes

**Description:** Impact of variance on benefits (error finding)

**Source Field:** E_FINDG


| Code | Description |
|------|-------------|
| 2 | Overissuance |
| 3 | Underissuance |
| 4 | Ineligible |


### sex_codes

**Description:** Sex of household member

**Source Field:** SEX


| Code | Description |
|------|-------------|
| 1 | Male |
| 2 | Female |
| 3 | Prefer not to answer |


### snap_affiliation_codes

**Description:** SNAP case affiliation status

**Source Field:** FSAFIL


| Code | Description |
|------|-------------|
| 1 | Eligible member of SNAP case under review and entitled to receive benefits |
| 2 | Eligible SNAP participant in another unit, not currently under review |
| 4 | Member is ineligible noncitizen and not participating in State-funded SNAP |
| 5 | Member not paying/cooperating with child support agency |
| 6 | Member is ineligible striker |
| 7 | Member is ineligible student |
| 8 | Member disqualified for program violation |
| 9 | Member ineligible to participate due to disqualification or failure to meet work requirements |
| 10 | ABAWD time limit exhausted |
| 11 | Fleeing felon or parole and probation violator |
| 13 | Convicted drug felon |
| 14 | Social Security Number disqualified |
| 15 | SSI recipient in California |
| 16 | Prisoner in detention center |
| 17 | Foster care |
| 18 | Member is ineligible noncitizen and participating in State-funded SNAP |
| 19 | Individual in the home but not part of SNAP household |
| 99 | Unknown |


### element_codes

**Description:** Type of variance element (what area had the problem)

**Source Field:** ELEMENT


| Code | Description |
|------|-------------|
| 111 | Student status |
| 130 | Citizenship and noncitizen status |
| 140 | Residency |
| 150 | Unit composition |
| 151 | Recipient disqualification |
| 160 | Employment and training programs |
| 161 | Time-limited participation |
| 162 | Work registration requirements |
| 163 | Voluntary quit/reduced work effort |
| 164 | Workfare and comparable workfare |
| 165 | Employment status/job availability |
| 166 | Acceptance of employment |
| 170 | Social Security number |
| 211 | Bank accounts or cash on hand |
| 212 | Nonrecurring lump-sum payment |
| 213 | Other liquid assets |
| 221 | Real property |
| 222 | Vehicles |
| 224 | Other nonliquid resources |
| 225 | Combined resources |
| 311 | Wages and salaries |
| 312 | Self-employment |
| 314 | Other earned income |
| 321 | Earned income deductions |
| 323 | Dependent care deduction |
| 331 | RSDI benefits |
| 332 | Veterans' benefits |
| 333 | SSI and/or State SSI supplement |
| 334 | Unemployment compensation |
| 335 | Workers' compensation |
| 336 | Other government benefits |
| 342 | Contributions |
| 343 | Deemed income |
| 344 | TANF, PA, or GA |
| 345 | Educational grants/scholarships/loans |
| 346 | Other unearned income |
| 350 | Child support payments received from absent parent |
| 361 | Standard deduction |
| 363 | Shelter deduction |
| 364 | Standard utility allowance |
| 365 | Medical expense deductions |
| 366 | Child support payment deduction |
| 371 | Combined gross income |
| 372 | Combined net income |
| 520 | Arithmetic computation |
| 530 | Transitional benefits |
| 560 | Reporting systems |
| 810 | SNAP simplification project |
| 820 | Demonstration projects |


### nature_codes

**Description:** Nature of each variance (what went wrong)

**Source Field:** NATURE


| Code | Description |
|------|-------------|
| 6 | Eligible person(s) excluded |
| 7 | Ineligible person(s) included |
| 12 | Eligible person(s) with no income, resources, or deductible expenses excluded |
| 13 | Eligible person(s) with income excluded |
| 14 | Eligible person(s) with resources excluded |
| 15 | Eligible person(s) with deductible expenses excluded |
| 16 | Newborn improperly excluded |
| 20 | Incorrect resource limit applied |
| 24 | Resource should have been excluded |
| 28 | Incorrect income limit applied |
| 29 | Exceeds prescribed limit |
| 30 | Resource should have been included |
| 32 | Failed to consider or incorrectly considered income of ineligible member |
| 35 | Unreported source of income (do not use for change in employment status) |
| 36 | Rounding used/not used or incorrectly applied |
| 37 | All income from source known but not included |
| 38 | More income received from this source than budgeted |
| 39 | Employment status changed from unemployed to employed |
| 40 | Employment status changed from employed to unemployed |
| 41 | Change only in amount of earnings |
| 42 | Conversion to monthly amount not used or incorrectly applied |
| 43 | Averaging not used or incorrectly applied |
| 44 | Less income received from this source than budgeted |
| 45 | Cost of doing business not used or incorrectly applied |
| 46 | Failed to consider/anticipate month with extra pay date |
| 52 | Deduction that should have been included was not |
| 53 | Deduction included that should not have been |
| 54 | Incorrect standard used (not as a result of change in unit size or move) |
| 64 | Incorrect amount used resulting from change in residence |
| 65 | Incorrect standard used resulting from change in unit size |
| 75 | Benefit/allotment/eligibility incorrectly computed |
| 77 | Unit not entitled to transitional benefits |
| 79 | Incorrect use of allotment tables |
| 80 | Improper prorating of initial month's benefits |
| 97 | Not required to be reported or acted upon based on time frames and reporting requirements |
| 98 | Transcription or computation errors |
| 99 | Other |
| 111 | Child support payment(s) not considered or incorrectly applied for initial month(s) of eligibility |
| 112 | Retained child support payment(s) not considered or incorrectly applied |
| 120 | Variance/errors resulting from noncompliance with this means-tested public assistance program |
| 123 | Incorrectly prorated |
| 124 | Variances resulting from use of automatic Federal information exchange system |
| 127 | Pass-through not considered or incorrectly applied |
| 200 | Eligible noncitizen excluded |
| 201 | Ineligible noncitizen included |
| 301 | Unit improperly participating under retrospective budgeting |
| 302 | Unit improperly participating under prospective budgeting |
| 303 | Unit improperly participating under monthly reporting |
| 304 | Unit improperly participating under quarterly reporting |
| 305 | Unit improperly participating under semiannual reporting |
| 306 | Unit improperly participating under change reporting |
| 307 | Unit improperly participating under status reporting |
| 308 | Unit improperly participating under 5 hour reporting |
| 309 | Unit improperly participating in transitional benefits |


### agency_responsibility_codes

**Description:** Primary cause of variance (agency vs client responsibility)

**Source Field:** AGENCY


| Code | Description |
|------|-------------|
| 1 | Information not reported |
| 2 | Incomplete or incorrect information provided; agency not required to verify |
| 3 | Information withheld by client (case referred for IPV investigation) |
| 4 | Incorrect information provided by client (case referred for IPV investigation) |
| 7 | Inaccurate information reported by collateral contact |
| 8 | Acted on incorrect Federal computer match information not requiring verification |
| 10 | Policy incorrectly applied |
| 12 | Reported information disregarded or not applied |
| 14 | Agency failed to follow up on inconsistent or incomplete information |
| 15 | Agency failed to follow up on impending changes |
| 16 | Agency failed to verify required information |
| 17 | Computer programming error |
| 18 | Data entry and/or coding error |
| 19 | Mass change error |
| 20 | Arithmetic computation error |
| 21 | Computer user error |
| 99 | Other |


### discovery_method_codes

**Description:** How variance was discovered

**Source Field:** DISCOV


| Code | Description |
|------|-------------|
| 1 | Variance clearly identified from case record (not automated match) |
| 2 | Variance clearly identified from case record (automated match) |
| 3 | Variance discovered from recipient interview |
| 4 | Employer (present or former) |
| 5 | Financial institution, insurance company, or other business |
| 6 | Landlord |
| 7 | Government agency or public records, not automated match |
| 8 | Government agency or public records, automated match |
| 9 | Other |

