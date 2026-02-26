# CLAUDE.md

## Project Overview

SnapAnalyst is an AI-powered platform for querying SNAP (Supplemental Nutrition Assistance Program) Quality Control data using natural language. Users ask questions in plain English, the system generates SQL via Vanna AI (ChromaDB for RAG), executes against PostgreSQL, and returns results with AI-powered summaries.

## Build & Run Commands

### Docker (Primary)
```bash
docker-compose up -d                        # Start all services
docker-compose down                         # Stop services
docker-compose down -v                      # Stop + remove volumes (full reset)
docker-compose logs -f backend-server       # Backend API logs
docker-compose logs -f frontend-server      # Chainlit UI logs
```

### Local Development
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements/base.txt
pip install -r requirements/dev.txt         # adds pytest, ruff, mypy
cp .env.example .env

docker-compose up -d postgres               # Start PostgreSQL via Docker
./start_all.sh                               # Start all services

# Or start individually:
PYTHONPATH=. python src/api/main.py          # API on :8000
chainlit run chainlit_app.py --port 8001     # UI on :8001
```

### Testing & Linting
```bash
pytest tests/                                # All tests
pytest tests/unit/                           # Unit tests only
pytest tests/integration/                    # Integration tests
ruff check .                                 # Lint
ruff format .                                # Format
mypy src/                                    # Type check
```

Always run tests before committing. Use conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).

Code style: line length 120 (configured in `pyproject.toml`). Ruff rules: E/W/F/I/B/C4/UP/ARG/SIM.

## Architecture

### Three Layers

1. **Chainlit UI** (`chainlit_app.py`, `ui/`)
   - Thin layer — `chainlit_app.py` has only decorators and ONNX config
   - Business logic in `ui/handlers/` and `ui/services/`
   - Persona/message templates in `ui/responses.py`; HTML formatting in `ui/formatters.py`
   - Calls backend via `src/clients/api_client.py`

2. **FastAPI Backend** (`src/api/`, port 8000)
   - Routers in `src/api/routers/`: `chatbot.py`, `query.py`, `filter.py`, `schema.py`, `llm.py`, `data_export.py`, `data_loading.py`, `files.py`, `management.py`, `schema_exports.py`
   - All database queries are read-only (SELECT/WITH only)

3. **Services & Data** (`src/services/`, `src/database/`)
   - `llm_service.py`: Entry point for SQL generation (wraps Vanna)
   - `llm_providers.py`: Provider-specific Vanna classes (OpenAI, Anthropic, Ollama, Azure)
   - `ai_summary.py`: Natural language summaries of query results
   - `kb_chromadb.py`: Knowledge base for insights

### Data Flow

```
User question → ui/handlers/queries.py → API /api/v1/chat/data
→ llm_service.generate_sql() → Vanna (ChromaDB RAG → LLM → SQL)
→ PostgreSQL (read-only) → code enrichment → AI summary → UI
```

### ChromaDB Stores

1. **KB ChromaDB** (`./chromadb/kb/`) — Knowledge base for Knowledge mode insights
   - Managed via Settings > Knowledge sidebar panel
   - Used by `src/services/kb_chromadb.py`

2. **Vanna ChromaDB** (`./chromadb/vanna_ddl/`) — SQL generation training data
   - Managed via Settings > Knowledge SQL sidebar panel
   - Collections: `ddl` (schema), `documentation` (business context), `sql` (question-SQL pairs)
   - Used by Vanna via `_get_vanna_instance()` in `llm_providers.py`

### Vanna AI (SQL Generation)

Uses Vanna 0.x-style DDL training with 2.x Agent architecture via `LegacyVannaAdapter`.

Provider classes in `llm_providers.py`: `OpenAIVanna`, `AnthropicVanna`, `OllamaVanna`, `AzureOpenAIVanna`.

Training functions in `llm_providers.py`:
- `train_vanna_with_ddl(force_retrain)` — Startup training (DDL + docs + query examples), called once on first use
- `train_vanna(force_retrain, reload_training_data)` — Full reset: clears all data, retrains DDL. With `reload_training_data=True`, also reloads from `datasets/snap/training/`

Training data sources:
- `datasets/snap/training/` — docs + question/SQL pairs for RAG
- `src/database/ddl_extractor.py` — DDL extraction from live database
- Table discovery configured in `datasets/snap/config.yaml` (`include_table_prefixes`, `exclude_tables`, `exclude_table_prefixes`)

### Database Schema

Normalized from 1,200+ column CSV:

**public schema** (SNAP data):
- `households` (composite PK: case_id + fiscal_year), `household_members`, `qc_errors`
- `ref_*` (25+ lookup tables), `state_error_rates`, `fns_error_rates_historical`
- `md_*` tables: Maryland-specific error analysis

**app schema** (application state):
- `user_prompts`, `data_load_history`, `users`

Migrations managed by Alembic (`migrations/`).

## Configuration

Environment variables (`.env`):
- `LLM_PROVIDER`: `openai` | `anthropic` | `ollama` | `azure_openai`
- `LLM_SQL_MODEL` / `LLM_KB_MODEL`: Models for SQL generation and summaries
- `DATABASE_URL`: PostgreSQL connection string
- `VANNA_STORE_USER_QUERIES`: Toggle continuous learning

Settings loaded via pydantic in `src/core/config.py`. Computed properties `settings.sql_model` and `settings.kb_model` have provider-specific fallback defaults.

Dataset config in `datasets/snap/config.yaml`: `data_files` (per-year download URLs, single source of truth for fiscal years), table inclusion/exclusion for Vanna training.

## Chat Interface

### Slash Commands
Only `/clear` is routed via `ui/handlers/commands/router.py`.
- `/clear` — Clear chat history

### Chat Modes (via mode selector)
- **SQL** (default) — Natural language to SQL
- **Insights** — Thread-aware insight (equivalent to `/?`)
- **Knowledge** — KB lookup (equivalent to `/??`)
- **Settings** — Opens Settings sidebar panel

### Settings Sidebar Panels
All configuration is accessed via the Settings toolbar button, which opens a navigation panel dispatching to sub-panels via `open_settings_panel` action callback in `chainlit_app.py`:
- **Filters** — State/fiscal year filters (`utility_commands.handle_filter`)
- **LLM Params** — Provider/model settings (`info_commands.handle_llm`)
- **Knowledge SQL** — Vanna ChromaDB management (`memsql_commands.handle_memsql_panel`)
- **Knowledge** — KB ChromaDB management (`memory_commands.handle_mem_panel`)
- **Database** — Stats and export (`info_commands.handle_database_panel`)

## Key Patterns

- **Prompts**: Centralized in `src/core/prompts.py` (`VANNA_SQL_SYSTEM_PROMPT`, `AI_SUMMARY_PROMPT`). Includes USDA error rate formulas and SNAP business rules.
- **Filter Manager**: `src/core/filter_manager.py` — state/year filtering across queries
- **Code Enrichment**: `src/services/code_enrichment.py` — numeric codes to descriptions
- **Async/Sync Bridge**: `llm_service.py` wraps sync via `asyncio.to_thread()`
- **Singletons**: `get_llm_service()`, `get_settings()` return cached instances
- **Thread Safety**: `ContextVar` for user_id (middleware in `main.py`); thread-local for custom prompts in `llm_providers.py`
- **Feedback Training**: Thumbs up/down on SQL query results trains/detrains Vanna ChromaDB.
  Controlled by `VANNA_STORE_USER_QUERIES` (default: True). Only SQL mode — Insights/Knowledge
  feedback is a no-op. Implementation in `ui/services/feedback_training.py`.
- **ETL Pipeline**: `src/etl/` (reader, transformer, validator, writer, loader)
