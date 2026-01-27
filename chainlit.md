# Welcome to SnapAnalyst AI!

An AI-powered platform that enables analysts, researchers, and policy makers to query complex SNAP Quality Control data using natural language and gain insights—without needing SQL expertise.

---

## What I Can Do

I'm your AI assistant for analyzing SNAP Quality Control data:

| Feature | Description |
|:--------|:------------|
| **Natural Language** | Query the database using plain English |
| **SQL Generation** | Automatically generate SQL from your questions |
| **Direct SQL** | Execute SQL directly (read-only, for power users) |
| **AI Insights** | Get intelligent summaries and analysis of your data |
| **Smart Filtering** | Filter all queries by state and/or fiscal year using the settings panel. Filters apply automatically to all queries and exports |
| **Thread Panel** | Access all your previous chat sessions from the left sidebar. Resume conversations and review past analyses |
| **Code Translation** | Automatically translate codes to meaningful descriptions |
| **Excel Export** | Download data to Excel with comprehensive README |
| **Schema Help** | Explain database schema and relationships |

---

## Quick Start Examples

**Try these questions:**

```
What is the payment error rate in 2023 for each state?
What are the top 3 causes of payment errors?
How have error rates changed from 2021 to 2023?
Show me unreported income errors by state
```

---

## Advanced Features

### Direct SQL
Power users can execute SQL directly:
```sql
SELECT state_name, COUNT(*) as household_count
FROM households
WHERE fiscal_year = 2023
GROUP BY state_name
ORDER BY household_count DESC
```

### AI-Powered Insights

Get deeper insights from your data using ChromaDB-enhanced analysis:

- **`/?` Full Thread Insight** - Ask questions that consider your entire conversation history
  ```
  /? Compare the error patterns across all my previous queries
  /? What trends do you see in the data I've analyzed so far?
  ```

- **`/??` Knowledge Base Lookup** - Query the knowledge base directly without thread context
  ```
  /?? What does status code 2 mean?
  /?? Explain element code 311
  ```

---

## Chat Commands

Type these commands to access features:

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/download` | Export current results to Excel |
| `/filter status` | Check active state/year filters |
| `/database` | View database statistics |
| `/schema` | Explore database structure |
| `/llm` | View LLM configuration |
| `/clear` | Clear chat history |

---

## Quick Reference: Common Codes

**Element Codes (Error Types)**

| Code | Description |
|------|-------------|
| 311 | Wages and salaries |
| 331 | RSDI (Social Security) |
| 333 | SSI |
| 334 | Unemployment |
| 150 | Household composition |
| 211 | Bank accounts/cash |
| 363 | Shelter deduction |
| 520 | Computation errors |

**Nature Codes (What Went Wrong)**

| Code | Description |
|------|-------------|
| 35 | Unreported income |
| 37 | Income known but not included |
| 38 | More income than budgeted |
| 75 | Benefit incorrectly computed |

**Status Codes**

| Code | Description |
|------|-------------|
| 1 | Amount correct |
| 2 | Overissuance |
| 3 | Underissuance |

---

**Need Help?** Type `/help` for a complete list of commands

**Last Updated:** January 27, 2026
