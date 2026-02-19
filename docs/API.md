# SnapAnalyst API Reference

This document provides a reference for the SnapAnalyst REST API.

## Base URL

- **Development**: `http://localhost:8000/api/v1`
- **Docker**: `http://localhost:8000/api/v1`

## Interactive Documentation

When running in development mode, interactive API docs are available:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Authentication

Currently, the API does not require authentication. API key authentication can be enabled via environment variables.

---

## Endpoints Overview

| Category | Prefix | Description |
|----------|--------|-------------|
| [Chat](#chat-api) | `/chat` | Natural language queries and insights |
| [Query](#query-api) | `/query` | Direct SQL execution |
| [Data](#data-api) | `/data` | Data loading and export |
| [Filter](#filter-api) | `/filter` | Query filtering |
| [Schema](#schema-api) | `/schema` | Database schema information |
| [LLM](#llm-api) | `/llm` | LLM configuration and memory |
| [System](#system-api) | `/system` | Health checks and management |

---

## Chat API

Natural language to SQL conversion and knowledge base insights.

### POST `/chat/data`
Convert natural language question to SQL and optionally execute it.

**Request Body:**
```json
{
  "question": "How many households received SNAP benefits in California?",
  "execute": true,
  "explain": false,
  "user_id": "user@example.com"
}
```

**Response:**
```json
{
  "question": "How many households received SNAP benefits in California?",
  "sql": "SELECT COUNT(*) FROM households WHERE state_code = 'CA'",
  "explanation": null,
  "executed": true,
  "results": [{"count": 12345}],
  "row_count": 1
}
```

### POST `/chat/insights`
Generate insights using knowledge base with optional data context.

**Request Body:**
```json
{
  "question": "What does error code 02 mean?",
  "data_context": null,
  "user_id": "user@example.com"
}
```

### POST `/chat/stream`
Stream SQL generation progress via Server-Sent Events (SSE).

### POST `/chat/insights/stream`
Stream insight generation via Server-Sent Events (SSE).

### GET `/chat/examples`
Get example questions for the chat interface.

---

## Query API

Direct SQL query execution.

### POST `/query/sql`
Execute a SQL query directly (read-only queries only).

**Request Body:**
```json
{
  "sql": "SELECT state_name, COUNT(*) as count FROM households GROUP BY state_name",
  "limit": 1000
}
```

**Response:**
```json
{
  "success": true,
  "data": [...],
  "row_count": 50,
  "execution_time_ms": 45.2
}
```

### GET `/query/schema`
Get database schema information for query building.

### GET `/query/examples`
Get example SQL queries.

---

## Data API

Data loading, export, and file management.

### GET `/data/files`
List available CSV files for loading.

**Response:**
```json
{
  "files": [
    {
      "filename": "qc_pub_fy2023.csv",
      "size_mb": 45.2,
      "fiscal_year": 2023,
      "loaded": true
    }
  ],
  "snapdata_path": "/app/snapdata"
}
```

### POST `/data/load`
Start loading a CSV file into the database.

**Request Body:**
```json
{
  "filename": "qc_pub_fy2023.csv",
  "fiscal_year": 2023
}
```

**Response:** `202 Accepted` with job ID for status polling.

### GET `/data/load/status/{job_id}`
Get status of a data loading job.

### GET `/data/export/excel`
Export all data to Excel with documentation.

**Query Parameters:**
- `state` (optional): Filter by state name (e.g., "California")
- `fiscal_year` (optional): Filter by fiscal year

### POST `/data/reset`
Reset database (delete all data).

### POST `/data/upload`
Upload a CSV file.

---

## Filter API

Manage query filters for state and fiscal year.

### GET `/filter`
Get current active filter.

### POST `/filter/set`
Set a new filter.

**Request Body:**
```json
{
  "state": "California",
  "fiscal_year": 2023
}
```

### POST `/filter/clear`
Clear all active filters.

### GET `/filter/options`
Get available filter options (states and years in database).

---

## Schema API

Database schema documentation and code lookups.

### GET `/schema/tables`
Get all table structures with columns and types.

### GET `/schema/tables/{table_name}`
Get structure of a specific table.

### GET `/schema/relationships`
Get table relationships (foreign keys).

### GET `/schema/code-lookups`
Get all code lookup tables (reference data).

### GET `/schema/code-lookups/{lookup_name}`
Get specific code lookup table.

### GET `/schema/documentation`
Get complete schema documentation.

### GET `/schema/query-tips`
Get tips for writing effective queries.

### GET `/schema/database-info`
Get database metadata (row counts, sizes).

---

## Schema Export API

Export schema documentation in various formats.

### GET `/schema-export/tables/csv`
Export table structures to CSV.

### GET `/schema-export/tables/markdown`
Export table structures to Markdown.

### GET `/schema-export/tables/pdf`
Export table structures to PDF.

### GET `/schema-export/code-lookups/csv`
Export code lookups to CSV.

### GET `/schema-export/code-lookups/pdf`
Export code lookups to PDF.

### GET `/schema-export/relationships/csv`
Export table relationships to CSV.

---

## LLM API

LLM provider configuration and memory management.

### GET `/llm/provider`
Get current LLM provider information.

**Response:**
```json
{
  "provider": "openai",
  "model": "gpt-4",
  "status": "configured"
}
```

### GET `/llm/health`
Check LLM provider health/connectivity.

### GET `/llm/memory/stats`
Get ChromaDB memory statistics.

### GET `/llm/memory/list`
List all entries in AI memory.

### POST `/llm/memory/add`
Add documentation to AI memory via file upload.

**Request:** `multipart/form-data`
- `files` (required): One or more `.md` or `.txt` files
- `category` (optional): Category label
- `tags` (optional): Comma-separated tags

### DELETE `/llm/memory/{doc_id}`
Delete a specific memory entry.

### POST `/llm/memory/reset`
Reset AI memory and retrain.

### POST `/llm/train`
Manually trigger AI training.

### GET `/llm/training/status`
Get training status.

### GET `/llm/prompt/{prompt_type}`
Get current prompt for a user. `prompt_type` is `kb` or `sql`.

**Headers:** `X-User-ID` (optional, defaults to "default")

**Response:**
```json
{
  "prompt_text": "...",
  "is_custom": false,
  "char_count": 1234,
  "prompt_type": "kb"
}
```

### PUT `/llm/prompt/{prompt_type}`
Set a custom prompt for a user.

**Headers:** `X-User-ID`

**Request Body:**
```json
{
  "prompt_text": "Your custom prompt text..."
}
```

### DELETE `/llm/prompt/{prompt_type}`
Reset prompt to system default.

**Headers:** `X-User-ID`

### GET `/llm/vanna/stats`
Get Vanna SQL training data statistics (DDL, documentation, SQL pair counts).

### GET `/llm/vanna/list`
List Vanna training data grouped by type (ddl, documentation, sql).

### POST `/llm/vanna/add`
Add training data to Vanna via file upload.

**Request:** `multipart/form-data`
- `files` (required): `.md`/`.txt` files (documentation) or `.json` files (question-SQL pairs)

### DELETE `/llm/vanna/{entry_id}`
Delete a specific Vanna training entry.

### POST `/llm/vanna/reset`
Reset Vanna training data and retrain.

**Request Body:**
```json
{
  "reload_training_data": true
}
```
- `reload_training_data`: When true, reloads docs and query examples from `datasets/snap/training/`

---

## System API

System health and management.

### GET `/system/health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "llm": "configured",
  "version": "0.1.0"
}
```

### GET `/system/stats`
Get system statistics (database size, query counts).

---

## Error Responses

All endpoints return standard error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `202` - Accepted (async operation started)
- `400` - Bad Request (invalid input)
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

---

## Rate Limiting

Rate limiting is not enabled by default. For production deployments, consider adding rate limiting via a reverse proxy or the `slowapi` middleware.

---

## Examples

### Query with Filter

```bash
# Set filter
curl -X POST http://localhost:8000/api/v1/filter/set \
  -H "Content-Type: application/json" \
  -d '{"state": "California", "fiscal_year": 2023}'

# Query with filter applied
curl -X POST http://localhost:8000/api/v1/chat/data \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the average SNAP benefit?", "execute": true}'
```

### Export Data

```bash
# Export to Excel
curl "http://localhost:8000/api/v1/data/export/excel?fiscal_year=2023" \
  -o snap_data_2023.xlsx
```

### Direct SQL

```bash
curl -X POST http://localhost:8000/api/v1/query/sql \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT COUNT(*) FROM households", "limit": 100}'
```
