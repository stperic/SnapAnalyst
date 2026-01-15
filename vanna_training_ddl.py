# Vanna Training DDL for SnapAnalyst Database

# Simple DDL statements for training Vanna
# Based on actual database schema

TRAINING_DDL = [
    # Table 1: households - Main household/case data with state and income
    """
    CREATE TABLE households (
        case_id VARCHAR(50) PRIMARY KEY,
        fiscal_year INTEGER NOT NULL,
        state_name VARCHAR(50),  -- State name for geographic queries
        gross_income DECIMAL(12,2),  -- Total household gross income
        net_income DECIMAL(12,2),
        earned_income DECIMAL(12,2),
        unearned_income DECIMAL(12,2),
        snap_benefit DECIMAL(10,2),
        certified_household_size INTEGER,
        num_elderly INTEGER,
        num_children INTEGER,
        num_disabled INTEGER,
        status INTEGER  -- 1=correct, 2=overissuance, 3=underissuance
    );
    -- NOTE: For state-level queries, use the households table which has state_name
    """,
    
    # Table 2: household_members - Individual member data (NO state_name column!)
    """
    CREATE TABLE household_members (
        case_id VARCHAR(50),
        fiscal_year INTEGER,
        member_number INTEGER,
        age INTEGER,
        sex INTEGER,
        wages DECIMAL(10,2),
        self_employment_income DECIMAL(10,2),
        social_security DECIMAL(10,2),
        ssi DECIMAL(10,2),
        unemployment DECIMAL(10,2),
        tanf DECIMAL(10,2),
        total_income DECIMAL(10,2),  -- Individual member income
        PRIMARY KEY (case_id, fiscal_year, member_number),
        FOREIGN KEY (case_id, fiscal_year) REFERENCES households(case_id, fiscal_year)
    );
    -- NOTE: This table does NOT have state_name. 
    -- For queries needing state, JOIN with households table or query households directly.
    """,
    
    # Table 3: qc_errors - Quality control errors  
    """
    CREATE TABLE qc_errors (
        case_id VARCHAR(50),
        fiscal_year INTEGER,
        error_number INTEGER,
        element_code INTEGER,  -- Type of error (311=wages, 331=RSDI, etc)
        nature_code INTEGER,  -- Nature of error
        error_amount DECIMAL(10,2),
        PRIMARY KEY (case_id, fiscal_year, error_number),
        FOREIGN KEY (case_id, fiscal_year) REFERENCES households(case_id, fiscal_year)
    );
    -- NOTE: This table does NOT have state_name.
    -- For queries needing state, JOIN with households table.
    """
]

# Training examples for common query patterns
TRAINING_SQL = [
    {
        "question": "What is the average income by state?",
        "sql": "SELECT state_name, AVG(gross_income) AS average_income FROM households WHERE gross_income IS NOT NULL GROUP BY state_name ORDER BY state_name"
    },
    {
        "question": "Show me households in California",
        "sql": "SELECT * FROM households WHERE state_name = 'California'"
    },
    {
        "question": "How many households received overissuance?",
        "sql": "SELECT COUNT(*) FROM households WHERE status = 2"
    }
]
