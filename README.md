# SnapAnalyst

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![CI](https://github.com/stperic/SnapAnalyst/actions/workflows/ci.yml/badge.svg)](https://github.com/stperic/SnapAnalyst/actions/workflows/ci.yml)
[![CodeQL](https://github.com/stperic/SnapAnalyst/actions/workflows/codeql.yml/badge.svg)](https://github.com/stperic/SnapAnalyst/actions/workflows/codeql.yml)

**AI-Powered SNAP Quality Control Data Analysis Platform**

<p align="center">
  <img src="media/SNAP%20Large.png" alt="SnapAnalyst Demo" width="240">
</p>

SnapAnalyst is an AI-powered platform that enables analysts, researchers, and policy makers to query complex SNAP (Supplemental Nutrition Assistance Program) Quality Control data using natural language and gain actionable insights—without needing SQL expertise. Ask questions in plain English and get instant, intelligent answers backed by SQL queries and AI-powered analysis.

### Powered by Vanna.AI

SnapAnalyst leverages [**Vanna.AI**](https://vanna.ai/) for intelligent natural language to SQL generation. Vanna is an open-source Python RAG (Retrieval-Augmented Generation) framework that trains on your database schema and generates accurate SQL queries from plain English questions.

- **Documentation**: [https://vanna.ai/docs](https://vanna.ai/docs/)
- **GitHub**: [https://github.com/vanna-ai/vanna](https://github.com/vanna-ai/vanna)
- **License**: MIT

## Table of Contents

- [Why SnapAnalyst?](#why-snapanalyst)
- [Features](#features)
- [Use Cases](#use-cases)
- [Quick Start with Docker](#quick-start-with-docker)
- [Chat Commands](#chat-commands)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Local Development](#local-development)
- [API Usage](#api-usage)
- [Project Structure](#project-structure)
- [System Requirements](#system-requirements)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Data Source](#data-source)
- [Getting Help](#getting-help)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Why SnapAnalyst?

**The Problem**: SNAP Quality Control data is incredibly valuable for policy analysis and research, but it's locked away in complex CSV files with 1,200+ columns, cryptic codes, and relationships that require deep domain knowledge to understand.

**The Solution**: SnapAnalyst transforms this complexity into simplicity:

- **Ask in Plain English** - No SQL or technical knowledge required
- **AI-Powered Analysis** - Get insights, not just data dumps
- **Instant Results** - Query millions of records in seconds
- **Automatic Code Translation** - Numeric codes become readable descriptions
- **Export Everything** - Download complete data packages with documentation
- **Safe & Secure** - Read-only queries prevent accidental data modification

## Features

### AI & Query Capabilities
- **Natural Language Queries**: Ask questions in plain English—no SQL knowledge required
- **Automatic SQL Generation**: AI translates your questions into optimized SQL queries
- **Direct SQL Support**: Power users can execute SQL directly (read-only for safety)
- **AI-Powered Insights**: Get intelligent summaries and analysis of query results
- **Code Translation**: Automatically translates numeric codes to meaningful descriptions

### Data Management
- **Smart Filtering**: Filter all queries by state and/or fiscal year using the settings panel. Filters apply automatically to all subsequent queries and exports. Easily switch between states (e.g., Connecticut, Maryland) or years (FY2021-FY2023) without rewriting questions.
- **Excel Export**: Download complete data packages with comprehensive documentation
- **CSV Upload**: Upload and load data files directly from your browser
- **Normalized Database**: 1,200+ CSV columns transformed into optimized PostgreSQL schema

### User Experience
- **Thread Panel**: Access all your previous chat sessions from the left sidebar. Resume conversations, review past analyses, and organize your work by topic. Each thread preserves your full query history, results, and context.
- **Chat History**: Every query, result, and insight is automatically saved. Navigate between different analysis sessions seamlessly.
- **Beautiful Web UI**: Modern chat interface built with Chainlit with real-time streaming responses
- **Formatted Results**: Clean, readable output with proper data formatting and syntax highlighting

### Technical Features
- **Multi-LLM Support**: OpenAI GPT-4, Anthropic Claude, Azure OpenAI, or free local Ollama
- **Schema Explorer**: Built-in database schema explanations and relationships
- **Authentication**: Secure password-based login with persistent user sessions
- **Streaming Responses**: Real-time token streaming for responsive AI interactions

## Use Cases

- **State QC Teams**: Identify top error elements by dollar impact, prioritize corrective actions, track payment error rate trends year over year
- **Policy Analysts**: Compare state performance against national benchmarks, analyze demographic patterns, study benefit adequacy
- **Program Administrators**: Monitor error rates, export data for internal reporting and corrective action planning, augment federal data with state-specific datasets
- **Researchers**: Query SNAP QC microdata without data preparation, explore income and eligibility patterns across fiscal years

## Quick Start with Docker

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- An LLM provider:
  - **OpenAI** API key, OR
  - **Anthropic** API key, OR
  - **Ollama** installed locally (free, no API key needed)

### 1. Clone and Configure

```bash
# Clone the repository
git clone https://github.com/stperic/SnapAnalyst.git
cd SnapAnalyst

# Copy environment template (optional - has sensible defaults)
cp .env.example .env

# Edit .env with your settings if needed:
# - Set your LLM provider (openai, anthropic, or ollama)
# - Add your API key if using OpenAI or Anthropic
# - Change SECRET_KEY for production
```

**Note**: The `.env` file is optional. Without it, the system defaults to Ollama with standard settings.

### 2. Start Services

```bash
docker-compose up -d
```

On first run, Docker will automatically:
- Download SNAP QC ZIP files for FY2021, FY2022, FY2023 (~10MB compressed from snapqcdata.net)
- Extract CSV files (~134MB total uncompressed)
- Load all data into the PostgreSQL database
- Start the API and Chat UI

**Note**: First run takes 5-10 minutes for data download and database initialization. Subsequent starts are instant as data persists in Docker volumes.

### 3. Access the Application

- **Chat UI**: http://localhost:8001
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (requires `ENVIRONMENT=development` in `.env`)

### First Steps

1. Open http://localhost:8001 in your browser
2. Ask questions in plain English (e.g., "What are the top 3 causes of payment errors?")
3. Set filters using the settings icon to focus on specific states or fiscal years
4. Export data with `/export` command or download query results using the CSV button

## Chat Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/export` | Export full database with comprehensive README |
| `/export 2023` | Export FY2023 data only |
| `/export tables=snap_my_table` | Export custom tables |
| `/filter status` | Check active state/year filters |
| `/database` | View database statistics |
| `/schema` | Explore database structure |
| `/llm` | View LLM configuration |
| `/clear` | Clear chat history |
| `/?` | Full thread insight with conversation context |
| `/??` | Knowledge base lookup only |
| `/mem` | Manage AI knowledge base (insights/docs) |
| `/memsql` | Manage Vanna SQL training data |

### Advanced Insight Commands

**Full Thread Insight (`/?`)**
Ask questions that consider your entire conversation history:
```
/? Compare the error patterns across all my previous queries
/? What trends do you see in the data I've analyzed so far?
```

**Knowledge Base Lookup (`/??`)**
Query the knowledge base directly without thread context:
```
/?? What does status code 2 mean?
/?? Explain element code 311
```

### AI Memory Commands

SnapAnalyst has two separate AI memory stores, each managed through a self-contained sidebar panel:

**Knowledge Base (`/mem`)** — Powers `/??` insights and documentation lookups

Type `/mem` to open the sidebar panel where you can:
- View statistics (status, document count, size)
- Browse and delete individual documents
- Upload `.md` / `.txt` files with optional category and tags
- Reset the entire knowledge base

**SQL Training (`/memsql`)** — Powers natural language to SQL generation via Vanna.AI

Type `/memsql` to open the sidebar panel where you can:
- View statistics (DDL, documentation, SQL pairs)
- Browse and delete individual training entries
- Upload training files (`.md`/`.txt` for docs, `.json` for question-SQL pairs)
- Reset training data with option to reload from training folder
- View and update the SQL system prompt

**Upload file formats for `/memsql`:**
- `.md` / `.txt` — Added as documentation context for SQL generation
- `.json` — Must contain `{"example_queries": [{"question": "...", "sql": "..."}]}`

**Reset (available in the `/memsql` panel):**
The Reset button clears all Vanna training data (DDL, docs, SQL pairs) and retrains DDL from the database schema. A **"Reload SNAP training data"** checkbox (checked by default) controls whether documentation and query examples from the training folder (`datasets/snap/training/`) are also reloaded automatically. Uncheck it to start with DDL only and add training data manually via Upload.

### Training Data & System Prompts (Advanced)

Vanna AI's behavior is driven by two configurable folders:

1. **Training data** (`SQL_TRAINING_DATA_PATH`) — Documentation and query examples for RAG
2. **System prompts** (`SYSTEM_PROMPTS_PATH`) — LLM system prompts that set persona and domain rules

```
datasets/snap/
├── training/                     # Training data (SQL_TRAINING_DATA_PATH)
│   ├── business_context.md       # Domain knowledge & business rules
│   └── query_examples.json       # Example question/SQL pairs
└── prompts/                      # System prompts (SYSTEM_PROMPTS_PATH)
    ├── sql_system_prompt.txt     # SQL generation system prompt
    └── kb_system_prompt.txt      # Knowledge base insight prompt
```

#### Training Data Folder

The system scans the training folder at startup. No naming conventions required — all files are loaded by extension:

| Extension | Purpose | Format |
|-----------|---------|--------|
| `.md`, `.txt` | Documentation — chunked and stored in ChromaDB for RAG retrieval during SQL generation | Plain text or Markdown |
| `.json` | Question/SQL pairs — taught to Vanna as examples | `{"example_queries": [{"question": "...", "sql": "...", "explanation": "..."}]}` |

The optional `explanation` field in query examples is stored for documentation purposes but is not used during training. Only the `question` and `sql` fields are sent to Vanna for RAG matching.

#### System Prompts Folder

| File | Purpose | Fallback if missing |
|------|---------|---------------------|
| `sql_system_prompt.txt` | System prompt sent to the LLM for SQL generation. Include domain-specific calculations, business rules, field naming conventions, and SQL guidelines. | Generic "expert data analyst and PostgreSQL specialist" prompt |
| `kb_system_prompt.txt` | System prompt for `/??` knowledge base insights. Sets the LLM's persona and response style. | Generic "data analyst" prompt |

#### Customizing System Prompts

The system prompts are the most important files for SQL generation quality. The SNAP dataset includes a `sql_system_prompt.txt` with domain-specific rules (pre-computed views, tolerance thresholds, SQL conventions). When replacing the dataset, write your own prompts with your domain knowledge.

**Example `sql_system_prompt.txt` for a custom dataset:**
```
You are an expert healthcare data analyst and PostgreSQL specialist.
Generate accurate, executable SQL queries based on natural language questions.

### Domain Rules
- Patient IDs use composite key (patient_id, encounter_date)
- Diagnosis codes follow ICD-10 format (e.g., 'E11.65')
- Always filter WHERE status = 'active' unless user asks for all records
- Use encounter_date for time-based queries (YYYY-MM-DD format)

### SQL Guidelines
- Dialect: PostgreSQL
- Apply LIMIT 100 for non-aggregate queries
- Use ILIKE for case-insensitive text search

Return only the SQL query without markdown formatting.
```

#### Replacing the SNAP Dataset

To use SnapAnalyst with your own data:

1. **Create your folders:**
   ```bash
   mkdir -p datasets/mydata/training datasets/mydata/prompts
   ```

2. **Add training files:**
   - Any `.md`/`.txt` files — Business context, documentation
   - Any `.json` files — Example question/SQL pairs in the format above

3. **Add prompt files:**
   - `sql_system_prompt.txt` — Your domain-specific SQL prompt
   - `kb_system_prompt.txt` — Your KB insight persona (optional)

4. **Point to your folders** in `.env`:
   ```bash
   SQL_TRAINING_DATA_PATH=./datasets/mydata/training
   SYSTEM_PROMPTS_PATH=./datasets/mydata/prompts
   ```

5. **Load your data** into PostgreSQL and retrain via `/memsql` → Reset Full

If you omit the prompt files or the prompts folder, generic defaults are used — the system never assumes SNAP-specific terminology.

#### Runtime Prompt Customization

Users can override prompts per-user without editing files, using the sidebar panels:
- `/memsql` panel → **System Prompt** section — Upload a `.txt` file to override the SQL generation prompt, or reset to default
- `/mem` panel → **System Prompt** section — Upload a `.txt` file to override the KB insight prompt, or reset to default
- `/prompt sql` or `/prompt kb` — View the current prompt (custom or default)

Custom prompts are stored in the database per user and take priority over the prompts folder files.

### Data Export Commands

**Export Full Database (`/export`)**
Download complete database with comprehensive README documentation:
```
/export                                    # Default: 3 core tables (households, members, errors)
/export 2023                               # FY2023 only
/export tables=households                  # Single table
/export tables=households,snap_my_table    # Multiple tables (including custom)
/export 2023 tables=snap_my_table          # Combine filters
```

**What's Included:**
- **README Sheet**: Complete documentation, column definitions, code lookups
- **Data Sheets**: Requested tables with proper formatting
- **Code Translation**: Numeric codes automatically translated to descriptions
- **Filtered Data**: Respects active state/year filters

**Custom Table Support:**
Users can export custom tables by name. Tables must follow naming conventions:
- Custom tables: `snap_*` prefix (e.g., `snap_state_analysis`)
- Reference tables: `ref_*` prefix (e.g., `ref_custom_codes`)
- Views: `v_*` or `snap_v_*` prefix

**CSV Download Button (Query Results)**
After running a query, click the "📥 CSV" button to export only that query's results as CSV. This is lighter and faster for ad-hoc analysis of specific queries.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  Chainlit UI    │  │  FastAPI API    │  │  PostgreSQL │ │
│  │  Port 8001      │→ │  Port 8000      │→ │  Port 5432  │ │
│  │                 │  │                 │  │             │ │
│  │  Chat Interface │  │  LLM Service    │  │  Normalized │ │
│  │  Filters        │  │  Query Engine   │  │  Schema     │ │
│  │  Export         │  │  Data Loading   │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema

The ETL pipeline transforms wide-format CSV (1,200+ columns) into a normalized schema:

| Table | Description | Key Fields |
|-------|-------------|------------|
| `households` | Core case data | state_name, snap_benefit, income totals |
| `household_members` | Individual member data | age, wages, employment status |
| `qc_errors` | Quality control errors | element_code, nature_code, error_amount |
| `ref_*` (25+ tables) | Code lookups | Maps codes to descriptions |
| `mv_state_error_rates` | Pre-computed state error rates | payment_error_rate, overpayment_rate |
| `mv_error_element_rollup` | Error element dollar impact | weighted_error_dollars by element |
| `mv_demographic_profile` | SNAP participant demographics | age, race, citizenship, education |

**Storage**: All data is stored in Docker volumes that persist between restarts:
- `snapanalyst_postgres_data` - PostgreSQL database
- `snapanalyst_snapanalyst_data` - Downloaded CSV files

### Data Flow

1. **User Query** → Chainlit UI captures natural language question
2. **AI Processing** → LLM generates SQL from question + schema context
3. **Query Execution** → FastAPI executes SQL against PostgreSQL (read-only)
4. **Code Enrichment** → Numeric codes translated to descriptions
5. **AI Summary** → LLM analyzes results and provides insights
6. **Response** → Formatted results + SQL + analysis returned to user

## Configuration

### Environment Variables

Configuration is managed through a `.env` file in the project root (or environment variables).

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment mode: `production` or `development` | `production` |
| `LLM_PROVIDER` | LLM provider: `openai`, `anthropic`, `ollama`, `azure_openai` | `ollama` |
| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI) | - |
| `ANTHROPIC_API_KEY` | Anthropic API key (if using Anthropic) | - |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://host.docker.internal:11434` |
| `DATABASE_PASSWORD` | PostgreSQL password | Set in `.env` |
| `SECRET_KEY` | Application secret key | Change in production! |
| `API_PORT` | API port mapping | `8000` |
| `CHAINLIT_PORT` | UI port mapping | `8001` |
| `POSTGRES_PORT` | PostgreSQL port mapping | `5432` |
| `SQL_TRAINING_DATA_PATH` | Training data folder (docs, query examples) | `./datasets/snap/training` |
| `SYSTEM_PROMPTS_PATH` | System prompts folder (SQL & KB prompts) | `./datasets/snap/prompts` |

**Note**: Set `ENVIRONMENT=development` to enable API documentation at `/docs` and `/redoc`

See `.env.example` for all available options.

### LLM Provider Setup

**OpenAI (Recommended for best results)**
```bash
# In .env file:
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-your-key-here
```

**Anthropic Claude**
```bash
# In .env file:
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Azure OpenAI**
```bash
# In .env file:
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/openai/v1/
AZURE_OPENAI_API_KEY=your-azure-api-key
```
See [docs/AZURE_OPENAI_SETUP.md](docs/AZURE_OPENAI_SETUP.md) for detailed Azure configuration.

**Ollama (Free, Local)**
```bash
# Install Ollama first: https://ollama.ai
ollama pull llama3.1:8b

# In .env file (or use defaults):
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

## Docker Commands

```bash
# Start all services
docker-compose up -d

# View logs (all services)
docker-compose logs -f

# View specific service logs
docker-compose logs -f data-loader    # Data download/load progress
docker-compose logs -f backend-server # API logs
docker-compose logs -f frontend-server # UI logs

# Check status
docker-compose ps

# Stop services
docker-compose down

# Stop and remove volumes (reset database and downloaded data)
docker-compose down -v

# Rebuild after code changes
docker-compose up -d --build
```

## Local Development

For development without Docker:

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Your preferred LLM provider

### Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements/base.txt

# Copy environment file
cp .env.example .env
# Edit .env with your settings

# Start PostgreSQL (if using Docker for DB only)
docker-compose up -d postgres

# Download data
./scripts/download_data.sh

# Start all services
./start_all.sh

# Or start individually:
# Terminal 1: API
PYTHONPATH=. python src/api/main.py

# Terminal 2: Chainlit UI
chainlit run chainlit_app.py --port 8001
```

### Stop Services

```bash
./stop_all.sh
```

## System Requirements

### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 4 GB (8 GB recommended)
- **Disk**: 5 GB free space
- **OS**: macOS, Linux, or Windows with WSL2
- **Docker**: 20.10+ with Docker Compose

### Recommended for Production
- **CPU**: 4+ cores
- **RAM**: 16 GB
- **Disk**: 20 GB SSD
- **Network**: Stable internet for LLM API calls (if using OpenAI/Anthropic)

### LLM Provider Requirements
- **OpenAI**: API key + internet connection
- **Anthropic**: API key + internet connection
- **Ollama**: 8 GB RAM for llama3.1:8b model (runs locally, no internet needed)


## API Usage

For complete API documentation, see [docs/API.md](docs/API.md).

```python
import requests

# Ask the AI a question
response = requests.post(
    "http://localhost:8000/api/v1/chat/data",
    json={
        "question": "What's the average SNAP benefit?",
        "execute": True
    }
)
result = response.json()
print(result["sql"])      # Generated SQL
print(result["results"])  # Query results
```

```bash
# Set a filter
curl -X POST http://localhost:8000/api/v1/filter/set \
  -H "Content-Type: application/json" \
  -d '{"state": "Connecticut"}'

# Download filtered data
curl "http://localhost:8000/api/v1/data/export/excel" -o data.xlsx
```

## Project Structure

```
SnapAnalyst/
├── docker-compose.yml    # Docker orchestration
├── .env.example          # Environment template
├── docker/
│   ├── Dockerfile        # Container build instructions
│   └── .dockerignore     # Docker ignore patterns
├── src/
│   ├── api/              # FastAPI REST API
│   ├── services/         # LLM, AI summary, code enrichment
│   ├── database/         # SQLAlchemy models, DDL
│   ├── etl/              # Data transformation pipeline
│   └── core/             # Configuration, logging, prompts
├── ui/                   # Chainlit UI handlers
├── datasets/snap/        # Dataset configuration and data
├── scripts/              # Utility scripts
│   ├── download_data.sh       # Data download script
│   └── docker_init_data.py    # Docker initialization
├── start_all.sh          # Start local development
├── stop_all.sh           # Stop local development
└── requirements/         # Python dependencies
```

## Troubleshooting

**View Logs**
```bash
docker-compose logs -f                    # All services
docker-compose logs data-loader           # Data download issues
docker-compose logs postgres              # Database issues
```

**Common Issues**
- **Port in use**: Change `API_PORT` or `CHAINLIT_PORT` in `.env`
- **Data download fails**: Check `docker-compose logs data-loader` and internet connection
- **Database errors**: Ensure PostgreSQL is healthy with `docker-compose ps postgres`
- **Reset everything**: `docker-compose down -v && docker-compose up -d --build`

**Ollama Connection**
- Mac/Windows: Use `OLLAMA_BASE_URL=http://host.docker.internal:11434`
- Linux: Use host IP (e.g., `http://172.17.0.1:11434`)

## FAQ

**Do I need SQL knowledge?**
No. Ask questions in plain English—the AI generates SQL automatically.

**Is my data safe?**
Yes. All queries are read-only and data stays in your local Docker containers.

**Which LLM provider is best?**
OpenAI GPT-4 (best quality), Anthropic Claude (excellent), or Ollama (free, local, good).

**What does it cost?**
Docker and Ollama are free. OpenAI/Anthropic: ~$0.01-0.10 per query.

**Can I query multiple fiscal years?**
Yes. Remove year filters or ask: "Compare FY2021 to FY2023".

## Data Source

SNAP Quality Control data is downloaded from:
- **Primary Source**: https://snapqcdata.net/data
  - FY2021, FY2022, FY2023 ZIP archives
  - Automatically downloaded on first Docker startup

Original data provided by the USDA Food and Nutrition Service:
- https://www.fns.usda.gov/snap/quality-control-data

### Data Files

| Fiscal Year | Compressed (ZIP) | Uncompressed (CSV) | Households |
|-------------|------------------|-----------------------|------------|
| FY2021 | ~1.1 MB | ~13.7 MB | ~10,000 * |
| FY2022 | ~4.4 MB | ~57.8 MB | ~41,000 |
| FY2023 | ~4.8 MB | ~62.7 MB | ~44,000 |

\* FY2021 reflects a reduced national sample due to COVID-19 pandemic QC review flexibilities. See FNS release notes for that year.

The data includes:
- **Households**: Demographics, income, benefits, case status
- **Household Members**: Age, employment, income sources
- **QC Errors**: Error findings, amounts, responsible agencies

**Note on sampling weights**: The SNAP QC public use files are stratified random samples, not a census of all SNAP cases. Accurate national and state error rate calculations require applying FNS-provided sampling weights (`household_weight`). SnapAnalyst's pre-computed views (`mv_state_error_rates`, `mv_error_element_rollup`) use weighted calculations. Raw row counts and unweighted averages should not be used for policy conclusions.

### Pre-populated Data

SnapAnalyst comes pre-populated with the latest SNAP QC data from **FY2021, FY2022, and FY2023**. On first Docker startup, the system automatically downloads and loads this data into the PostgreSQL database, giving you immediate access to ~95,000 household records across all 53 SNAP reporting jurisdictions (50 states, DC, Guam, and the U.S. Virgin Islands).

### Adding Custom Data (Advanced Users)

States and analysts can augment the federal QC public use data with their own datasets — state-specific error analysis, internal reviews, regional breakdowns, or any supplemental tables. Custom tables are loaded into the same PostgreSQL database alongside the public data, and the AI automatically learns to query across both. This means analysts can ask questions that combine federal and state data in a single query.

SnapAnalyst automatically discovers and trains Vanna.AI on custom tables and views that follow naming conventions:

#### Naming Conventions

All public schema tables are included in Vanna AI training by default (unless excluded in config). However, using consistent prefixes is recommended for organization:

**Custom Tables**: Use `snap_*` prefix
```sql
CREATE TABLE snap_state_analysis (
    state_code VARCHAR(2),
    metric_value DECIMAL,
    analysis_year INT
);
```

**Reference/Lookup Tables**: Use `ref_*` prefix
```sql
-- ref_* tables with a 'description' column get sample data
-- automatically extracted for AI training
CREATE TABLE ref_county_codes (
    code VARCHAR(3) PRIMARY KEY,
    description VARCHAR(200),
    state_code VARCHAR(2)
);
```

**State-Specific Tables**: Use a state abbreviation prefix (e.g., `md_*`, `ca_*`)
```sql
-- The md_* tables shipped with SnapAnalyst are Maryland-specific examples
CREATE TABLE md_error_cases (
    fiscal_year INT,
    jurisdiction VARCHAR(100),
    review_finding VARCHAR(50),
    ...
);
```

**Custom Views**: Use `v_*` or `snap_v_*` prefix
```sql
CREATE VIEW v_monthly_summary AS SELECT ...;
CREATE VIEW snap_v_state_comparison AS SELECT ...;
```

If you later want to restrict AI training to only certain prefixes, update `include_table_prefixes` in `datasets/snap/config.yaml`.

#### Discovery Rules

Table discovery is config-driven via `datasets/snap/config.yaml`:

```yaml
# Default: include ALL tables except excluded ones
include_table_prefixes:
  - "*"

# Tables always excluded from AI training
exclude_tables:
  - alembic_version
  - data_load_history
  - elements        # Chainlit internal
  - feedbacks       # Chainlit internal
  - steps           # Chainlit internal
  - threads         # Chainlit internal
  - users           # Chainlit internal

exclude_table_prefixes:
  - pg_
  - sql_
  - information_
```

By default, **all** public schema tables are included in AI training except the excluded ones above. To restrict training to specific prefixes, change `include_table_prefixes` (e.g., `["ref_", "md_", "snap_"]`).

#### Best Practices: Table & Column Comments

PostgreSQL `COMMENT ON` statements are the **most important way** to help the AI understand your schema. When Vanna extracts DDL, comments are included and directly influence SQL generation quality.

**Table comments** should include:
- A one-line description of what the table contains
- JOIN instructions (what tables to join with and on which keys)
- 3-5 example queries showing common usage patterns

```sql
-- Table comment with description and example queries
COMMENT ON TABLE state_error_rates IS
'State-level SNAP QC error rates by fiscal year with rankings and liability status.
Use state_name to join with households.state_name for cross-referencing.

COMMON QUERIES:
- Error rates by state: SELECT state_name, error_rate FROM state_error_rates WHERE fiscal_year = 2023 ORDER BY error_rate DESC
- States above national average: WITH national AS (SELECT SUM(error_dollars) / NULLIF(SUM(total_benefits), 0) * 100 AS national_rate FROM state_error_rates WHERE fiscal_year = 2023) SELECT s.state_name, s.error_rate FROM state_error_rates s CROSS JOIN national n WHERE s.fiscal_year = 2023 AND s.error_rate > n.national_rate
- Liability states: SELECT state_name, error_rate FROM state_error_rates WHERE liability_status IS NOT NULL';
```

**Column comments** clarify ambiguous or coded columns:

```sql
COMMENT ON COLUMN state_error_rates.liability_status IS 'Whether the state faces fiscal liability for high error rates (NULL = no liability)';
COMMENT ON COLUMN state_error_rates.error_rate IS 'Combined payment error rate as a decimal (e.g., 11.54 = 11.54%)';
```

**Reference tables** with a `description` column get sample data extracted automatically (e.g., `ref_status`: `1 = 'Amount correct', 2 = 'Overissuance'`). Adding a table comment on top of that further improves AI accuracy.

See the existing comments on `households`, `household_members`, and `qc_errors` for examples of well-documented tables.

#### Applying Changes

After adding custom tables or views:

1. **Add your schema to the database**:
   ```sql
   -- Connect to database
   psql -U snapanalyst -d snapanalyst_db

   -- Create your tables/views
   CREATE TABLE snap_my_analysis (...);

   -- Add comments to help the AI (strongly recommended)
   COMMENT ON TABLE snap_my_analysis IS
   'Description of what this table contains.

   COMMON QUERIES:
   - Example: SELECT ... FROM snap_my_analysis WHERE ...';
   ```

2. **Retrain Vanna.AI**: Open the `/memsql` panel and click **Reset**. This clears Vanna's SQL training data and re-extracts DDL from the database schema, automatically discovering your new tables and their comments. With the "Reload SNAP training data" checkbox checked (default), documentation and query examples from the training folder are also reloaded.

#### Example: Adding State-Specific Analysis

```sql
-- 1. Create custom analysis table
CREATE TABLE snap_california_errors (
    case_id VARCHAR(50),
    error_category VARCHAR(100),
    severity_score DECIMAL,
    fiscal_year INT,
    FOREIGN KEY (case_id, fiscal_year)
        REFERENCES households(case_id, fiscal_year)
);

-- 2. Create summary view
CREATE VIEW v_california_error_summary AS
SELECT
    error_category,
    COUNT(*) as error_count,
    AVG(severity_score) as avg_severity
FROM snap_california_errors
GROUP BY error_category;

-- 3. Load your data
COPY snap_california_errors FROM '/path/to/data.csv' CSV HEADER;
```

Then in the chat interface, open `/memsql` and click **Reset**, then ask:
- "What are the most common error categories in California?"
- "Show me cases with high severity scores"
- "Compare California error patterns to national trends"

## Getting Help

- **API Documentation**: Available in development mode at http://localhost:8000/docs
  - Enable by setting `ENVIRONMENT=development` in `.env`
  - In production, API docs are disabled for security
- **Database Schema**: Use `/schema` command in chat
- **Issues**: [GitHub Issues](https://github.com/stperic/SnapAnalyst/issues)
- **Discussions**: [GitHub Discussions](https://github.com/stperic/SnapAnalyst/discussions)

## Contributing

Contributions welcome! Fork the repo, create a feature branch, and submit a PR.

**Code Standards**: PEP 8, type hints, docstrings, tests required.

**Testing**: `pytest tests/` before committing.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Data Source**: [USDA Food and Nutrition Service SNAP QC Database](https://www.fns.usda.gov/snap/quality-control-data)

### Open Source Libraries

SnapAnalyst is built with these excellent open source projects:

| Library | Purpose | License |
|---------|---------|---------|
| [Vanna.AI](https://vanna.ai/) | Natural language to SQL generation | MIT |
| [FastAPI](https://fastapi.tiangolo.com/) | REST API framework | MIT |
| [Chainlit](https://chainlit.io/) | Chat UI framework | Apache 2.0 |
| [SQLAlchemy](https://www.sqlalchemy.org/) | Database ORM | MIT |
| [ChromaDB](https://www.trychroma.com/) | Vector database for AI memory | Apache 2.0 |
| [Polars](https://pola.rs/) | Data processing | MIT |
| [PostgreSQL](https://www.postgresql.org/) | Database | PostgreSQL License |
| [OpenAI SDK](https://github.com/openai/openai-python) | LLM integration | MIT |
| [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) | LLM integration | MIT |

We are grateful to the maintainers and contributors of these projects.

---

**Version**: 0.1.0 | **Status**: Active Development
