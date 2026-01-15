# Dynamic Summary Generation Configuration

## New Setting: LLM_SUMMARY_MAX_PROMPT_SIZE

### Purpose
Controls when to use AI summary vs simple fallback message based on actual prompt size, not arbitrary row counts.

### Location
- **Config**: `src/core/config.py`
- **Environment**: Add to `.env` file

### Add to .env
```bash
# LLM Summary Configuration
LLM_SUMMARY_MAX_PROMPT_SIZE=8000  # Max prompt chars before fallback (default: 8000)
```

### How It Works

1. **Always Format Full Dataset**: All results are formatted with numbers rounded to 2 decimals
2. **Build Complete Prompt**: Question + filters + full data
3. **Check Size**: Compare `len(prompt)` against `LLM_SUMMARY_MAX_PROMPT_SIZE`
4. **Decision**:
   - ✅ **Fits**: Send to LLM → Get AI-generated insights
   - ❌ **Too Large**: Use simple fallback → "Query returned {n} results. Showing key findings..."

### Benefits

- **Dynamic**: Adapts to actual data size
  - 100 rows × 2 columns = small → AI summary ✅
  - 50 rows × 20 columns = large → Fallback ✅
- **Configurable**: Easy to tune per deployment/model
- **Consistent**: Follows same pattern as other LLM settings

### Examples

**Small Prompt (AI Summary)**:
```
Question: "What's the average by state?"
Data: 5 rows × 2 columns = ~500 chars
Prompt: ~1,200 chars
Result: ✅ "Average ranges from Tennessee ($782.88) to Pennsylvania ($1,282.15)..."
```

**Large Prompt (Fallback)**:
```
Question: "Show all household members"
Data: 200 rows × 15 columns = ~15,000 chars
Prompt: ~16,000 chars > 8000 limit
Result: ❌ "Query returned 200 results. Showing key findings in the data table below."
```

### Tuning Guide

| Model | Recommended Limit | Reasoning |
|-------|------------------|-----------|
| GPT-4 | 12,000 chars | Large context window, handles more data |
| GPT-3.5 | 8,000 chars | Balanced default |
| Claude | 15,000 chars | Very large context, can handle more |
| Ollama (local) | 4,000 chars | Smaller models, be conservative |

### Testing

```bash
# Current setting
grep LLM_SUMMARY_MAX_PROMPT_SIZE .env

# Test with different queries
# Small: "What's the average income?"
# Medium: "Show income by state" (53 rows)
# Large: "Show all household members" (200+ rows)
```

### Code Location

**Config Definition**: `src/core/config.py:93`
```python
llm_summary_max_prompt_size: int = Field(
    default=8000, 
    ge=1000, 
    le=50000,
    description="Max prompt size (chars) for summary generation before fallback"
)
```

**Usage**: `chainlit_app.py:generate_ai_summary()`
```python
from src.core.config import settings

# Check against configurable limit
prompt_size = len(system_prompt)
if prompt_size > settings.llm_summary_max_prompt_size:
    # Use fallback
    return f"Query returned {row_count} results..."
else:
    # Send to LLM
    summary = await call_llm(prompt)
```

### Migration Notes

- **No Breaking Changes**: Works with existing `.env` (uses default 8000)
- **Backward Compatible**: Old queries still work
- **Optional**: Can omit from `.env` to use default

### Monitoring

Watch for patterns:
```bash
# Check how often fallback is used
tail -f logs/chainlit.log | grep "Query returned"

# If too frequent, increase limit
# If AI summaries are poor quality, decrease limit
```
