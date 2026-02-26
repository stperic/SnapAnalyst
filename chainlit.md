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

### Chat Modes

Use the mode selector in the chat input to switch between query types:

- **SQL** (default) — Natural language to SQL queries
- **Insights** — Ask questions that consider your entire conversation history
- **Knowledge** — Query the knowledge base directly for code lookups and documentation
- **Settings** — Open the Settings sidebar panel

### Settings

Click the **Settings** toolbar button (or select Settings mode) to access:

| Panel | Description |
|-------|-------------|
| **Filters** | Set state and fiscal year filters |
| **LLM Params** | Configure LLM provider, model, temperature |
| **Knowledge SQL** | Manage Vanna SQL training data — upload, browse, delete, reset |
| **Knowledge** | Manage KB documents — upload, browse, delete, reset |
| **Database** | View database statistics, export data |

Type `/clear` in the chat to clear your conversation history.

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

**Need Help?** Use the **Settings** button to access all features, or ask me a question in plain English.

**Last Updated:** February 26, 2026
