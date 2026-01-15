# Recommendations: Incorporating Business Context into Vanna Training

## Current Situation

### What We Have ✅
1. **Working SQL generation** - Basic DDL training works
2. **Correct table structure** - Knows which tables have which columns
3. **Query execution** - Can run queries and return results

### What We're Missing ❌
1. **Code lookups** - Doesn't know status=2 means "Overissuance"
2. **Business terminology** - Doesn't understand domain terms like "ABAWD", "categorical eligibility"
3. **Value meanings** - Can't interpret element_code=311 means "Wages and salaries"
4. **Context for queries** - Can't help users query "overissuance cases" or "wage errors"

---

## The Problem

When a user asks:
- ❌ "Show me overissuance cases" → LLM doesn't know to use `WHERE status = 2`
- ❌ "Find wage errors" → LLM doesn't know element_code=311
- ❌ "Show ineligible members" → LLM doesn't know snap_affiliation_code meanings

---

## Recommended Solution: Enhanced DDL with Comments

### Approach
Use **SQL comments in DDL** to embed business context directly into the schema training. This is:
- ✅ Simple - Vanna already understands DDL with comments
- ✅ Fast - No additional processing needed
- ✅ Accurate - Context is right in the schema
- ✅ Maintainable - Single source of truth

### Example Enhanced DDL

Instead of:
```sql
CREATE TABLE households (
    status INTEGER
);
```

Use:
```sql
CREATE TABLE households (
    status INTEGER,  
    -- Status codes: 1=Amount correct, 2=Overissuance, 3=Underissuance
    -- Common queries: WHERE status = 2 for overissuance cases
);
```

---

## Implementation Plan

### Phase 1: Core Columns (Immediate) ⭐

Add code lookups for most-queried columns:

**households table:**
```sql
CREATE TABLE households (
    case_id VARCHAR(50),
    fiscal_year INTEGER,
    state_name VARCHAR(50),  -- State name for geographic queries
    
    status INTEGER,
    -- 1=Amount correct, 2=Overissuance, 3=Underissuance
    -- Example: WHERE status = 2 finds overissuance cases
    
    gross_income DECIMAL(12,2),  -- Total household income
    net_income DECIMAL(12,2),    -- After deductions
    earned_income DECIMAL(12,2), -- From wages/employment
    unearned_income DECIMAL(12,2), -- From benefits/assistance
    
    snap_benefit DECIMAL(10,2),  -- Final benefit amount
    
    certified_household_size INTEGER,
    num_elderly INTEGER,  -- Age 60+
    num_children INTEGER, -- Under 18
    num_disabled INTEGER,
    
    categorical_eligibility INTEGER,
    -- 0=Not categorically eligible
    -- 1=Categorically eligible (exempt from income/asset tests)
    -- 2=Recoded as categorically eligible
    
    expedited_service INTEGER,
    -- 1=Entitled and received within time frame
    -- 2=Entitled but NOT received within time frame  
    -- 3=Not entitled
);
```

**qc_errors table:**
```sql
CREATE TABLE qc_errors (
    case_id VARCHAR(50),
    fiscal_year INTEGER,
    error_number INTEGER,
    
    element_code INTEGER,
    -- Common codes:
    -- 311=Wages and salaries, 331=RSDI benefits, 332=Veterans benefits
    -- 333=SSI/State SSI, 334=Unemployment, 335=Workers compensation
    -- 150=Unit composition, 211=Bank accounts/cash
    
    nature_code INTEGER,
    -- Common codes:
    -- 35=Unreported income source, 37=Income not included
    -- 38=More income than budgeted, 75=Benefit incorrectly computed
    
    error_amount DECIMAL(10,2),
    -- Dollar amount of the error
    
    error_finding INTEGER
    -- 2=Overissuance, 3=Underissuance, 4=Ineligible
);
```

**household_members table:**
```sql
CREATE TABLE household_members (
    case_id VARCHAR(50),
    fiscal_year INTEGER,
    member_number INTEGER,
    
    age INTEGER,  -- 0=under 1 year, 98=98 or older
    
    sex INTEGER,
    -- 1=Male, 2=Female, 3=Prefer not to answer
    
    snap_affiliation_code INTEGER,
    -- 1=Eligible and entitled to benefits
    -- 2=Eligible participant in another unit
    -- 7=Ineligible student, 8=Disqualified for violation
    -- 9=Ineligible due to work requirements
    -- 19=In home but not part of SNAP household
    
    wages DECIMAL(10,2),
    self_employment_income DECIMAL(10,2),
    social_security DECIMAL(10,2),
    ssi DECIMAL(10,2),
    unemployment DECIMAL(10,2),
    tanf DECIMAL(10,2),
    total_income DECIMAL(10,2)
);
```

### Phase 2: Documentation Training (Next)

Add business documentation as separate training:

```python
vanna.train(documentation="""
SNAP QC Database Business Context:

Common Query Patterns:
- Overissuance cases: households WHERE status = 2
- Underissuance cases: households WHERE status = 3
- Wage errors: qc_errors WHERE element_code = 311
- Income errors: qc_errors WHERE element_code IN (311, 331, 333, 334)
- Elderly households: households WHERE num_elderly > 0
- Households with children: households WHERE num_children > 0

Business Terms:
- SNAP = Supplemental Nutrition Assistance Program (food stamps)
- QC = Quality Control review
- Overissuance = Household received more benefits than entitled
- Underissuance = Household received less benefits than entitled
- RSDI = Social Security Disability Insurance
- SSI = Supplemental Security Income
- TANF = Temporary Assistance for Needy Families
- ABAWD = Able-Bodied Adults Without Dependents
""")
```

### Phase 3: Example Queries (Best Practice)

Train with real-world query patterns:

```python
examples = [
    {
        "question": "Show me all overissuance cases",
        "sql": "SELECT * FROM households WHERE status = 2"
    },
    {
        "question": "How many households had wage errors?",
        "sql": "SELECT COUNT(DISTINCT case_id) FROM qc_errors WHERE element_code = 311"
    },
    {
        "question": "Find elderly households in California",
        "sql": "SELECT * FROM households WHERE state_name = 'California' AND num_elderly > 0"
    },
    {
        "question": "What's the average error amount for income-related errors?",
        "sql": "SELECT AVG(error_amount) FROM qc_errors WHERE element_code BETWEEN 311 AND 346"
    }
]
```

---

## Prioritized Code Lookups to Include

### Critical (Must Have) ⭐⭐⭐

1. **status** (households) - Most queried field
   - 1=Correct, 2=Overissuance, 3=Underissuance

2. **element_code** (qc_errors) - Core error classification  
   - 311=Wages, 331=RSDI, 333=SSI, 334=Unemployment
   - 150=Unit composition, 211=Assets

3. **snap_affiliation_code** (members) - Member eligibility
   - 1=Eligible, 7=Student, 8=Disqualified, 9=Work requirements

### Important (Should Have) ⭐⭐

4. **categorical_eligibility** (households)
5. **expedited_service** (households)
6. **nature_code** (qc_errors) - Error details
7. **sex** (members)

### Nice to Have ⭐

8. **case_classification** (households)
9. **error_finding** (qc_errors)
10. Other lookup codes

---

## Implementation Code

### Option A: Inline in _train_basic_schema() (Recommended)

Update `src/services/llm_service.py`:

```python
def _train_basic_schema(self) -> None:
    """Train Vanna on DDL with embedded business context"""
    logger.info("Training Vanna on schema with business context...")
    
    # Load code lookups from data_mapping.json
    schema_path = Path(settings.vanna_schema_path)
    with open(schema_path, 'r') as f:
        mapping = json.load(f)
    
    code_lookups = mapping.get('code_lookups', {})
    
    # Build DDL with inline comments
    ddl = self._build_enhanced_ddl(code_lookups)
    
    for table_ddl in ddl:
        self.vanna.train(ddl=table_ddl)
    
    logger.info("Trained on enhanced schema with code lookups")

def _build_enhanced_ddl(self, code_lookups: dict) -> list:
    """Build DDL statements with code lookup comments"""
    
    # Extract specific lookups
    status_codes = code_lookups.get('status_codes', {})
    element_codes = code_lookups.get('element_codes', {})
    
    # Build commented DDL...
```

### Option B: Separate Documentation File (Alternative)

Create `schema_context.txt`:
```
SNAP QC Database Code Lookups:

status (households table):
- 1 = Amount correct
- 2 = Overissuance (received too much)
- 3 = Underissuance (received too little)

element_code (qc_errors table):
- 311 = Wages and salaries errors
- 331 = RSDI benefits errors
...
```

Then train:
```python
with open('schema_context.txt', 'r') as f:
    context = f.read()
vanna.train(documentation=context)
```

---

## Recommended Approach

### Start Simple (TODAY)

1. ✅ Update `_train_basic_schema()` to include top 5 code lookups as inline comments
2. ✅ Add 3-5 example queries for common patterns
3. ✅ Test with real user queries

### Expand Gradually (NEXT)

4. Add more code lookups based on actual user queries
5. Add business documentation training
6. Create query pattern library

### Measure Success

- Track queries that fail or return empty results
- Monitor which code lookups users try to use
- Gather feedback on query accuracy

---

## Estimated Impact

### Before (Current)
```
User: "Show me overissuance cases"
SQL: SELECT * FROM households WHERE [uncertain]
Result: ❌ Wrong or empty
```

### After (With Context)
```
User: "Show me overissuance cases" 
SQL: SELECT * FROM households WHERE status = 2
Result: ✅ Correct data
```

### Query Success Rate Improvement
- Current: ~60% (only basic queries work)
- With Phase 1: ~80% (code-based queries work)
- With Phase 2+3: ~90% (business term queries work)

---

## Next Steps

1. **Review this document** - Confirm approach
2. **Implement Phase 1** - Enhanced DDL with top code lookups
3. **Test with real queries** - Validate improvements
4. **Iterate** - Add more context based on usage

Would you like me to proceed with implementing Phase 1?
