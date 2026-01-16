# SnapAnalyst

**AI-Powered SNAP Quality Control Data Analysis Platform**

SnapAnalyst transforms complex SNAP (Supplemental Nutrition Assistance Program) Quality Control data into actionable insights through natural language queries. Ask questions in plain English and get instant SQL-powered answers.

## Features

- **Natural Language Queries**: Ask questions like "How many households in Texas have errors?" without writing SQL
- **Multi-LLM Support**: OpenAI GPT-4, Anthropic Claude, or free local Ollama
- **Beautiful Web UI**: Modern chat interface built with Chainlit
- **Smart Filtering**: Filter all queries by state and fiscal year
- **Excel Export**: Download complete data packages with documentation
- **Normalized Database**: 1,200+ CSV columns transformed into optimized PostgreSQL schema

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
git clone https://github.com/yourusername/snapanalyst.git
cd snapanalyst

# Copy environment template
cp docker/.env.example docker/.env

# Edit docker/.env with your settings:
# - Set your LLM provider (openai, anthropic, or ollama)
# - Add your API key if using OpenAI or Anthropic
# - Change SECRET_KEY for production
```

### 2. Start Services

```bash
cd docker
docker-compose up -d
```

On first run, Docker will automatically:
- Download SNAP QC data for FY2021, FY2022, FY2023 (~750MB total from USDA FNS)
- Load all data into the PostgreSQL database
- Start the API and Chat UI

This may take 5-10 minutes on first run.

### 3. Access the Application

- **Chat UI**: http://localhost:8001
- **API Docs**: http://localhost:8000/docs
- **API**: http://localhost:8000

### First Steps

1. Open http://localhost:8001
2. Ask a question: "How many households are in the database?"
3. Set filters: Click the settings icon to filter by state/year
4. Export data: Type `/download`

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
| `ref_*` (12 tables) | Code lookups | Maps codes to descriptions |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider: `openai`, `anthropic`, `ollama` | `ollama` |
| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI) | - |
| `ANTHROPIC_API_KEY` | Anthropic API key (if using Anthropic) | - |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://host.docker.internal:11434` |
| `DATABASE_PASSWORD` | PostgreSQL password | `snapanalyst_dev_password` |
| `SECRET_KEY` | Application secret key | Change in production! |

See `docker/.env.example` for all available options.

### LLM Provider Setup

**OpenAI (Recommended for best results)**
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-your-key-here
```

**Anthropic Claude**
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Ollama (Free, Local)**
```bash
# Install Ollama first: https://ollama.ai
ollama pull llama3.1:8b

# In docker/.env:
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

## Docker Commands

```bash
# Start all services
cd docker && docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes (reset database)
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
cd docker && docker-compose up -d postgres

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

## Chat Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/download` | Export data to Excel |
| `/filter status` | Check current filters |
| `/database` | Database statistics |
| `/schema` | View database structure |
| `/provider` | LLM configuration info |

## Example Queries

- "How many households received SNAP benefits in Connecticut?"
- "What's the average benefit amount by state?"
- "Show me households with children under 5 years old"
- "Which states have the most quality control errors?"
- "What are the most common error types?"
- "Compare overissuance vs underissuance by state"

## API Usage

```python
import requests

# Ask the AI a question
response = requests.post(
    "http://localhost:8000/api/v1/chat/query",
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
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── .env.example
├── src/
│   ├── api/              # FastAPI REST API
│   ├── services/         # LLM, AI summary, code enrichment
│   ├── database/         # SQLAlchemy models, DDL
│   ├── etl/              # Data transformation pipeline
│   └── core/             # Configuration, logging, prompts
├── ui/                   # Chainlit UI handlers
├── datasets/snap/        # Dataset configuration and data
├── scripts/              # Utility scripts
├── start_all.sh          # Start local development
├── stop_all.sh           # Stop local development
└── requirements/         # Python dependencies
```

## Troubleshooting

### Database Connection Error

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# View PostgreSQL logs
docker logs snapanalyst-postgres
```

### Port Already in Use

```bash
# Find process using port
lsof -i :8000
lsof -i :8001

# Kill process
kill -9 <PID>
```

### Docker Issues

```bash
# Reset everything
cd docker
docker-compose down -v
docker-compose up -d --build

# View container logs
docker-compose logs -f api
docker-compose logs -f chainlit
```

### Ollama Connection (Docker)

On Mac/Windows, use `host.docker.internal` to connect to Ollama running on the host:
```bash
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

On Linux, you may need to use the host's IP address or configure host networking.

## Data Source

SNAP Quality Control data is sourced from the USDA Food and Nutrition Service:
- https://www.fns.usda.gov/snap/quality-control-data

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Data Source**: USDA Food and Nutrition Service SNAP QC Database
- **Built with**: FastAPI, Vanna.AI, Chainlit, SQLAlchemy, Polars, PostgreSQL

---

**Version**: 1.0.0
