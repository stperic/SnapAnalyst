# Phase 1: Separator Pattern Implementation

## Feature: Query | Analysis Instructions

### What Was Implemented

**Core Logic**: Parse user questions with `|` separator to split SQL generation from analysis instructions.

---

## How It Works

### User Input Format
```
<SQL_QUESTION> | <ANALYSIS_INSTRUCTIONS>
```

### Examples

#### Example 1: Focus on Specific State
```
Input: "What's the average income by state? | Focus your analysis on Maryland"

Processing:
1. SQL Part (to Vanna): "What's the average income by state?"
2. Generated SQL: SELECT state_name, AVG(gross_income) ... (ALL 53 states)
3. Analysis Part (to Summary LLM): "Focus your analysis on Maryland"

Result:
- Data: All 53 states returned
- Summary: "Maryland ($1,153.65) ranks in the middle compared to Pennsylvania 
  ($1,282.15, highest) and Tennessee ($782.88, lowest)..."
```

#### Example 2: Compare Regions
```
Input: "Show errors by state | Compare Northeast vs South regions"

Processing:
1. SQL: All states' errors
2. Summary: Focuses comparison on those regions

Result: Full context with targeted analysis
```

#### Example 3: No Separator (Backward Compatible)
```
Input: "What's the average income by state?"

Processing:
1. Works exactly as before
2. No separator detected
3. Standard behavior

Result: Normal query + summary
```

---

## Code Changes

### 1. `chainlit_app.py` - `handle_chat_query()`

**Added separator parsing:**
```python
# Parse question for separator pattern
sql_question = question
analysis_instructions = None

if "|" in question:
    parts = question.split("|", maxsplit=1)
    sql_question = parts[0].strip()
    analysis_instructions = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None

# Send only SQL part to Vanna
query_response = await call_api(
    "/chat/query",
    method="POST",
    data={"question": sql_question, ...}
)

# Pass both parts to summary
ai_summary = await generate_ai_summary(
    question=sql_question,
    analysis_instructions=analysis_instructions,
    ...
)
```

### 2. `chainlit_app.py` - `generate_ai_summary()`

**Added `analysis_instructions` parameter:**
```python
async def generate_ai_summary(
    question: str, 
    sql: str, 
    results: List[Dict], 
    row_count: int, 
    filters: str = "", 
    analysis_instructions: Optional[str] = None  # NEW
) -> str:
```

**Enhanced prompt to emphasize instructions:**
```python
system_prompt = f"""
USER'S QUESTION: "{question}"

{f"🎯 SPECIAL ANALYSIS INSTRUCTIONS: {analysis_instructions}" if analysis_instructions else ""}
{f"^^^ CRITICAL: Follow these specific instructions in your analysis! ^^^" if analysis_instructions else ""}

DATA TO ANALYZE:
{data_context}

INSTRUCTIONS:
1. Answer the user's specific question
2. {"MOST IMPORTANT: " + analysis_instructions if analysis_instructions else "Provide insights"}
...
"""
```

---

## Edge Cases Handled

### Empty Right Side
```
"Average income by state |"  # Trailing separator with no content
```
**Handled**: `parts[1].strip()` returns empty, set `analysis_instructions = None`

### Multiple Separators
```
"Income | by | state | Focus on Maryland"
```
**Handled**: `split("|", maxsplit=1)` splits only on FIRST `|`
- Left: "Income"
- Right: "by | state | Focus on Maryland"

### No Separator
```
"What's the average income?"
```
**Handled**: Works exactly as before (backward compatible)

### Whitespace
```
"Income by state   |   Focus on Maryland  "
```
**Handled**: `.strip()` on both parts removes extra whitespace

---

## Testing Scenarios

### Test 1: Basic Separator
```
Query: "What's the average income by state? | Provide insights for Maryland"

Expected:
✅ SQL generates for all states
✅ Summary focuses on Maryland with context
✅ Shows Maryland compared to highest/lowest
```

### Test 2: No Separator (Backward Compatible)
```
Query: "What's the average income by state?"

Expected:
✅ Works exactly as before
✅ Normal summary of all states
```

### Test 3: Complex Instructions
```
Query: "Show all errors | Compare the top 3 error states and explain why they might have more errors"

Expected:
✅ SQL returns all error data
✅ Summary identifies top 3 and provides analysis
```

### Test 4: Empty Instructions
```
Query: "Show income by state |"

Expected:
✅ Treated as no separator
✅ Normal behavior
```

---

## Benefits

### 1. **Flexibility**
- User controls SQL scope vs analysis focus
- Single query can ask broad question + targeted analysis

### 2. **Context Preservation**
- SQL gets all data (full context)
- Summary can compare/contrast even when focusing on specific item

### 3. **Backward Compatible**
- Existing queries work unchanged
- Optional feature - no user training required for basic use

### 4. **Natural Language**
- Separator is intuitive: "Do X | Focus on Y"
- Similar to Unix pipes (familiar to technical users)

---

## What's NOT in Phase 1

These are deferred to Phase 2/3:

- ❌ UI indication that separator is available
- ❌ Help documentation update
- ❌ Visual feedback showing parsed parts
- ❌ Welcome message examples
- ❌ Usage metrics/logging

---

## How to Use (User Guide)

### Basic Query (No Separator)
```
"What's the average income by state?"
→ Returns: All states with general summary
```

### Focused Analysis (With Separator)
```
"What's the average income by state? | Focus on Maryland and compare to neighbors"
→ Returns: All states, but summary focuses on Maryland vs VA, PA, DE
```

### Pattern
```
<BROAD_QUESTION> | <SPECIFIC_ANALYSIS_REQUEST>
```

**Tips**:
- Left side: What data you want
- Right side: How to analyze it
- Use `|` to separate
- Right side is optional

---

## Implementation Status

### ✅ Completed (Phase 1)
- Separator parsing logic
- SQL question extraction
- Analysis instructions extraction
- Enhanced summary prompt
- Edge case handling
- Backward compatibility

### 🚧 Pending (Phase 2/3)
- UI documentation
- Help command update
- Welcome message examples
- Visual feedback in results
- Usage logging

---

## Test Now

**Try these queries:**

1. **Without separator** (should work as before):
   ```
   What's the average income by state?
   ```

2. **With separator** (should focus analysis):
   ```
   What's the average income by state? | Provide detailed insights for Maryland
   ```

3. **Complex analysis**:
   ```
   Show all errors by state | Compare the 3 states with the most errors
   ```

**Expected**: Query #2 should return all 53 states but summary focuses on Maryland with context!

---

## Summary

Phase 1 implements the core separator pattern (`|`) that allows users to specify SQL generation instructions (left) separately from analysis instructions (right). The feature is fully backward compatible and ready to use immediately.
