# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SnapAnalyst is an AI-powered platform for querying SNAP (Supplemental Nutrition Assistance Program) Quality Control data using natural language. Users ask questions in plain English, the system generates SQL via Vanna AI (using ChromaDB for RAG), executes against PostgreSQL, and returns results with AI-powered summaries.

## Build & Run Commands

### Docker (Primary)
```bash
docker-compose up -d              # Start all services
docker-compose down               # Stop services
docker-compose down -v            # Stop and remove volumes (full reset)
docker-compose logs -f            # View all logs
docker-compose logs -f backend-server   # Backend API logs
docker-compose logs -f frontend-server  # Chainlit UI logs
docker-compose logs -f data-loader      # Data initialization logs
```

### Local Development
```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements/base.txt
cp .env.example .env

# Start PostgreSQL via Docker
docker-compose up -d postgres

# Start all services (kills existing, starts fresh)
./start_all.sh

# Or start individually:
PYTHONPATH=. python src/api/main.py          # Terminal 1: API on :8000
chainlit run chainlit_app.py --port 8001     # Terminal 2: UI on :8001

# Stop
./stop_all.sh
```

### Testing
```bash
pytest tests/                              # All tests
pytest tests/unit/                         # Unit tests only
pytest tests/integration/                  # Integration tests
pytest tests/unit/test_transformer.py -v  # Single test file
ruff check .                               # Linting
```

**Always run tests before committing. Use conventional commit format (e.g., `feat:`, `fix:`, `docs:`, `refactor:`, `test:`).**

## Architecture

### Three-Layer Architecture

1. **Chainlit UI Layer** (`chainlit_app.py`, `ui/`)
   - Thin UI layer - `chainlit_app.py` contains only Chainlit decorators and routing
   - Business logic lives in `ui/handlers/` and `ui/services/`
   - Communicates with backend via `src/clients/api_client.py`

2. **FastAPI Backend** (`src/api/`)
   - REST API at `:8000` with routers in `src/api/routers/`
   - Key routers: `chatbot.py` (LLM queries), `query.py` (SQL execution), `filter.py`, `schema.py`
   - All database queries are read-only for safety

3. **Services & Data** (`src/services/`, `src/database/`)
   - `llm_service.py`: Main entry point for SQL generation (wraps Vanna)
   - `llm_providers.py`: Provider-specific Vanna classes (OpenAI, Anthropic, Ollama, Azure)
   - `ai_summary.py`: Generates natural language summaries of query results
   - `kb_chromadb.py`: ChromaDB knowledge base for insights

### Vanna AI Integration (SQL Generation)

The system uses Vanna 0.x-style DDL training wrapped with 2.x Agent architecture:

```
User Question → llm_service.py → _get_vanna_instance() → ChromaDB RAG → LLM → SQL
```

Key classes in `llm_providers.py`:
- `OpenAIVanna`, `AnthropicVanna`, `OllamaVanna`, `AzureOpenAIVanna` - Provider-specific implementations
- `LegacyVannaAdapter` bridges 0.x instances to 2.x Agent compatibility
- DDL is trained once and stored in ChromaDB at `./chromadb/vanna_ddl`

### Database Schema

Normalized from 1,200+ column CSV into:
- `households`: Core case data (composite PK: case_id + fiscal_year)
- `household_members`: Person-level data (FK to households)
- `qc_errors`: Quality control findings (FK to households)
- `ref_*` tables (20+): Code lookup/reference tables
- `user_prompts`: Custom LLM prompts per user (app schema)

### Data Flow for Queries

1. User enters question in Chainlit UI
2. `ui/handlers/queries.py` → `handle_chat_query()`
3. API call to `/api/v1/chat/data` via `src/clients/api_client.py`
4. `src/api/routers/chatbot.py` → `llm_service.generate_sql()`
5. Vanna retrieves relevant DDL from ChromaDB, generates SQL
6. SQL executed against PostgreSQL (read-only)
7. Results enriched with code translations (numeric codes → descriptions)
8. AI summary generated via `ai_summary.py`
9. Response returned to UI with formatted results

## Key Configuration

Environment variables in `.env`:
- `LLM_PROVIDER`: `openai`, `anthropic`, `ollama`, or `azure_openai`
- `LLM_SQL_MODEL`: Model for SQL generation (e.g., `gpt-4.1`)
- `LLM_KB_MODEL`: Model for summaries/insights (e.g., `gpt-3.5-turbo`)
- `DATABASE_URL`: PostgreSQL connection string

Settings loaded via pydantic in `src/core/config.py` - use `settings.property_name` to access.

## Chat Commands

The UI supports slash commands routed through `ui/handlers/commands/router.py`:
- `/help`, `/status`, `/database`, `/schema`, `/llm` - Info commands
- `/filter status`, `/export`, `/clear` - Utility commands
- `/mem add|list|reset`, `/prompt show|set|reset` - Memory/prompt management
- `/? question` - Full thread insight with previous query context
- `/?? question` - Knowledge base lookup only

## Important Patterns

- **Prompts**: Centralized in `src/core/prompts.py` - update here for system prompts, personas, message templates
- **Filter Manager**: `src/core/filter_manager.py` handles state/year filtering across queries
- **Code Enrichment**: `src/services/code_enrichment.py` translates numeric codes to descriptions
- **Async/Sync Bridge**: `llm_service.py` has both sync (`generate_sql`) and async (`generate_sql_async`) methods - async wraps sync in thread pool
- **Singleton Pattern**: `get_llm_service()`, `get_settings()` return cached instances

## File Locations

- Custom system prompts: `src/core/prompts.py` (`VANNA_SQL_SYSTEM_PROMPT`, `AI_SUMMARY_PROMPT`)
- Database DDL extraction: `src/database/ddl_extractor.py`
- ETL pipeline: `src/etl/` (reader, transformer, writer, loader)
- Dataset config: `datasets/snap/` (data_mapping.json, query_examples.json)
