#!/usr/bin/env python3
"""
Generate a small synthetic SNAP QC CSV for unit testing.

Creates tests/data/test.csv with realistic column structure:
- 48 household-level columns
- 37 person-level × 17 members = 629 columns
- 9 error-level × 9 positions = 81 columns
- Extra unmapped columns to match real file breadth (800+)
- 1100 rows of synthetic data

Run: python tests/data/generate_test_csv.py
"""

import csv
import random
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.column_mapping import (
    ERROR_LEVEL_VARIABLES,
    HOUSEHOLD_LEVEL_VARIABLES,
    PERSON_LEVEL_VARIABLES,
    get_error_column_name,
    get_person_column_name,
)

NUM_ROWS = 1100
MAX_MEMBERS = 17
MAX_ERRORS = 9

# US state codes and names used in SNAP data
STATES = [
    (1, "Alabama"), (2, "Alaska"), (4, "Arizona"), (5, "Arkansas"),
    (6, "California"), (8, "Colorado"), (9, "Connecticut"), (10, "Delaware"),
    (11, "District of Columbia"), (12, "Florida"), (13, "Georgia"), (15, "Hawaii"),
    (16, "Idaho"), (17, "Illinois"), (18, "Indiana"), (19, "Iowa"),
    (20, "Kansas"), (21, "Kentucky"), (22, "Louisiana"), (23, "Maine"),
    (24, "Maryland"), (25, "Massachusetts"), (26, "Michigan"), (27, "Minnesota"),
    (28, "Mississippi"), (29, "Missouri"), (30, "Montana"), (31, "Nebraska"),
    (32, "Nevada"), (33, "New Hampshire"), (34, "New Jersey"), (35, "New Mexico"),
    (36, "New York"), (37, "North Carolina"), (38, "North Dakota"), (39, "Ohio"),
    (40, "Oklahoma"), (41, "Oregon"), (42, "Pennsylvania"), (44, "Rhode Island"),
    (45, "South Carolina"), (46, "South Dakota"), (47, "Tennessee"), (48, "Texas"),
    (49, "Utah"), (50, "Vermont"), (51, "Virginia"), (53, "Washington"),
    (54, "West Virginia"), (55, "Wisconsin"), (56, "Wyoming"),
]

# Extra unmapped columns present in real SNAP QC files (to push past 800)
EXTRA_COLUMNS = [
    "RESSION", "AUTHREP", "AUTHREPNO", "CERTEFDT", "CERTDATE", "INTDATE",
    "REVIEW_DATE", "FNSDATE", "COMPL_DATE", "ACTION", "ACTDATE",
    "HHLDTYPE", "NBRDEC", "NBRFAIL", "NBRREF", "CORRDATE",
    "ERRDATE", "LSTDATE", "DISPDT", "CLMDT", "RFRLDT",
    "INTVDT", "RPTDT", "DUESDT", "NOTICE_DATE",
    "RECON_DATE", "ADMIN_DT", "RVW_TYPE", "QC_TYPE",
    "CAT_TYPE", "RPT_TYPE", "REP_MODE", "INT_MODE",
    "SYS_TYPE", "FILE_TYPE", "BATCH_NO", "SEQ_NO",
    "VERDATE", "REFDATE", "ENDDATE", "BEGDATE",
    "CALCDATE", "ADJDATE", "PAYDATE", "ISSDATE",
    "APPDATE", "REDDATE", "PRIORBEN", "CURBEN",
    "ADJBEN", "CALCBEN", "GROSSINC", "NETINC",
    "TOTALDED", "TOTALEXP", "SHELTEXP", "UTILEXP",
    "MEDEXP", "DEPEXP", "ERNDED", "STDDED",
]


def generate_row(row_idx: int) -> dict:
    """Generate one synthetic SNAP QC row."""
    random.seed(row_idx)  # Reproducible per row
    row = {}

    state_code, state_name = random.choice(STATES)
    num_members = random.randint(1, min(6, MAX_MEMBERS))  # Most households 1-6
    num_errors = random.choices([0, 1, 2, 3], weights=[75, 15, 7, 3])[0]
    status = random.choices([1, 2, 3], weights=[70, 20, 10])[0]  # 1=correct, 2=over, 3=under

    hh_size = num_members
    snap_benefit = round(random.uniform(16.0, 1504.0), 2)
    gross_income = round(random.uniform(0, 5000.0), 2)
    net_income = round(gross_income * random.uniform(0.5, 0.9), 2)
    earned_income = round(gross_income * random.uniform(0, 0.8), 2)

    # Household-level columns
    hh_values = {
        "HHLDNO": str(row_idx + 1),
        "CASE": random.randint(1, 3),
        "REGIONCD": random.randint(1, 4),
        "STATE": state_code,
        "STATENAME": state_name,
        "YRMONTH": f"2023{random.randint(1, 12):02d}",
        "STATUS": status,
        "STRATUM": random.randint(1, 4),
        "RAWHSIZE": hh_size + random.randint(0, 2),
        "CERTHHSZ": hh_size,
        "FSUSIZE": hh_size,
        "FSNONCIT": random.choices([0, 1], weights=[90, 10])[0],
        "FSDIS": random.choices([0, 1, 2], weights=[70, 25, 5])[0],
        "FSELDER": random.choices([0, 1, 2], weights=[75, 20, 5])[0],
        "FSKID": max(0, hh_size - random.randint(1, 3)),
        "COMPOSITION": random.randint(1, 5),
        "RAWGROSS": gross_income,
        "RAWNET": net_income,
        "RAWERND": earned_income,
        "FSUNEARN": round(gross_income - earned_income, 2),
        "LIQRESOR": round(random.uniform(0, 2000), 2),
        "REALPROP": round(random.uniform(0, 500), 2),
        "FSVEHAST": round(random.uniform(0, 5000), 2),
        "FSASSET": round(random.uniform(0, 7000), 2),
        "FSSTDDED": 198,
        "FSERNDED": round(earned_income * 0.2, 2) if earned_income > 0 else 0,
        "FSDEPDED": round(random.uniform(0, 300), 2) if hh_size > 2 else 0,
        "FSMEDDED": round(random.uniform(0, 200), 2) if random.random() < 0.15 else 0,
        "SHELDED": round(random.uniform(0, 600), 2),
        "FSTOTDED": round(random.uniform(198, 1200), 2),
        "RENT": round(random.uniform(0, 1500), 2),
        "UTIL": round(random.uniform(0, 400), 2),
        "FSCSEXP": round(random.uniform(0, 1800), 2),
        "HOMELESS_DED": 0,
        "FSBEN": snap_benefit,
        "RAWBEN": snap_benefit,
        "BENMAX": round(snap_benefit * random.uniform(1.0, 1.5), 2),
        "MINIMUM_BEN": 23,
        "CAT_ELIG": random.choices([1, 2, 3], weights=[60, 30, 10])[0],
        "EXPEDSER": random.choices([1, 2], weights=[15, 85])[0],
        "CERTMTH": random.randint(1, 12),
        "LASTCERT": f"2023{random.randint(1, 12):02d}",
        "TPOV": random.randint(50, 200),
        "WRK_POOR": 1 if earned_income > 0 else 0,
        "TANF_IND": random.choices([0, 1], weights=[85, 15])[0],
        "AMTERR": round(random.uniform(-200, 200), 2) if status != 1 else 0,
        "FSGRTEST": random.randint(0, 1),
        "FSNETEST": random.randint(0, 1),
        "HWGT": round(random.uniform(50, 500), 4),
        "FYWGT": round(random.uniform(50, 500), 4),
    }
    row.update(hh_values)

    # Person-level columns for all 17 member slots
    for m in range(1, MAX_MEMBERS + 1):
        is_active = m <= num_members
        for source_var in PERSON_LEVEL_VARIABLES:
            col_name = get_person_column_name(source_var, m)
            if not is_active:
                row[col_name] = ""
            elif source_var == "FSAFIL":
                row[col_name] = random.randint(1, 3)
            elif source_var == "AGE":
                row[col_name] = random.randint(0, 85) if m > 1 else random.randint(18, 70)
            elif source_var == "SEX":
                row[col_name] = random.randint(1, 2)
            elif source_var == "RACETH":
                row[col_name] = random.randint(1, 6)
            elif source_var == "REL":
                row[col_name] = 1 if m == 1 else random.randint(2, 8)
            elif source_var == "CTZN":
                row[col_name] = random.choices([1, 2, 3], weights=[90, 7, 3])[0]
            elif source_var == "YRSED":
                row[col_name] = random.randint(0, 18) if random.random() > 0.1 else ""
            elif source_var in ("DIS", "FOSTER", "WORK"):
                row[col_name] = random.choices([0, 1], weights=[85, 15])[0]
            elif source_var == "WRKREG":
                row[col_name] = random.randint(1, 4)
            elif source_var == "ABWDST":
                row[col_name] = random.randint(1, 5)
            elif source_var in ("EMPRG",):
                row[col_name] = random.randint(1, 4) if random.random() > 0.5 else ""
            elif source_var in ("EMPSTA", "EMPSTB"):
                row[col_name] = random.randint(1, 6) if random.random() > 0.6 else ""
            elif source_var == "WAGES":
                row[col_name] = round(random.uniform(0, 3000), 2) if random.random() > 0.5 else 0.0
            elif source_var in ("SOCSEC", "SSI", "TANF", "UNEMP"):
                row[col_name] = round(random.uniform(0, 1500), 2) if random.random() > 0.7 else 0.0
            else:
                # Other numeric fields - always use float for consistency
                row[col_name] = round(random.uniform(0, 500), 2) if random.random() > 0.7 else 0.0

    # Error-level columns for all 9 error slots
    for e in range(1, MAX_ERRORS + 1):
        has_error = e <= num_errors
        for source_var in ERROR_LEVEL_VARIABLES:
            col_name = get_error_column_name(source_var, e)
            if not has_error:
                row[col_name] = ""
            elif source_var == "ELEMENT":
                row[col_name] = random.choice([311, 312, 321, 322, 331, 332, 411, 412, 511])
            elif source_var == "NATURE":
                row[col_name] = random.randint(1, 5)
            elif source_var == "AGENCY":
                row[col_name] = random.randint(1, 3)
            elif source_var == "AMOUNT":
                row[col_name] = round(random.uniform(1, 500), 2)
            elif source_var == "DISCOV":
                row[col_name] = random.randint(1, 4)
            elif source_var == "E_FINDG":
                row[col_name] = random.randint(1, 3)
            else:
                row[col_name] = random.randint(1, 5) if random.random() > 0.3 else ""

    # Extra columns (unmapped but present in real files) to reach 800+
    for extra_col in EXTRA_COLUMNS:
        row[extra_col] = random.randint(0, 99) if random.random() > 0.5 else ""

    return row


def main():
    output_path = Path(__file__).parent / "test.csv"

    # Build column order: household, person×17, error×9, extras
    columns = list(HOUSEHOLD_LEVEL_VARIABLES.keys())
    for m in range(1, MAX_MEMBERS + 1):
        for source_var in PERSON_LEVEL_VARIABLES:
            columns.append(get_person_column_name(source_var, m))
    for e in range(1, MAX_ERRORS + 1):
        for source_var in ERROR_LEVEL_VARIABLES:
            columns.append(get_error_column_name(source_var, e))
    columns.extend(EXTRA_COLUMNS)

    print(f"Generating {NUM_ROWS} rows with {len(columns)} columns...")

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for i in range(NUM_ROWS):
            writer.writerow(generate_row(i))

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Written: {output_path} ({size_mb:.1f} MB, {NUM_ROWS} rows, {len(columns)} columns)")


if __name__ == "__main__":
    main()
