# SnapAnalyst - Startup Scripts

## Quick Start

### Start All Services
```bash
./start_all.sh
```

This script will:
1. ✅ Kill any existing backend/frontend processes
2. ✅ Activate the virtual environment
3. ✅ Check if PostgreSQL is running
4. ✅ Start the Backend API (port 8000)
5. ✅ Start the Chainlit UI (port 8001)

### Stop All Services
```bash
./stop_all.sh
```

---

## Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Chainlit UI** | http://localhost:8001 | Main chatbot interface |
| **Backend API** | http://localhost:8000 | FastAPI backend |
| **API Docs** | http://localhost:8000/docs | Interactive API documentation |
| **API Health** | http://localhost:8000/health | Health check endpoint |

---

## Logs

View real-time logs:

```bash
# Backend logs
tail -f logs/api.log

# Frontend logs
tail -f logs/chainlit.log

# Both logs side-by-side
tail -f logs/api.log logs/chainlit.log
```

---

## Prerequisites

Before running `start_all.sh`, ensure:

1. **Virtual environment exists:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements/base.txt
   ```

2. **PostgreSQL is running:**
   ```bash
   docker-compose up -d
   # Wait for it to be healthy
   docker-compose ps
   ```

3. **Environment variables are set** (`.env` file):
   ```bash
   DATABASE_URL=postgresql://snapanalyst:snapanalyst_dev_password@localhost:5432/snapanalyst_db
   OPENAI_API_KEY=your_key_here  # Or ANTHROPIC_API_KEY, or configure Ollama
   ```

---

## Troubleshooting

### Ports Already in Use
```bash
# Check what's using the ports
lsof -i :8000
lsof -i :8001

# Kill processes manually
lsof -ti :8000 | xargs kill -9
lsof -ti :8001 | xargs kill -9
```

### PostgreSQL Not Running
```bash
# Start PostgreSQL
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f postgres
```

### Services Won't Start
```bash
# Check logs for errors
cat logs/api.log
cat logs/chainlit.log

# Verify virtual environment
source venv/bin/activate
python --version
which python

# Test backend manually
PYTHONPATH=. python src/api/main.py

# Test frontend manually
export API_BASE_URL=http://localhost:8000
chainlit run chainlit_app.py --port 8001
```

---

## Development Workflow

```bash
# 1. Start services
./start_all.sh

# 2. Make code changes
# Edit files in src/, chainlit_app.py, etc.

# 3. Restart services to apply changes
./stop_all.sh
./start_all.sh

# 4. View logs
tail -f logs/api.log
```

---

## Production Deployment

For production, consider:
- Using a process manager (systemd, supervisor, pm2)
- Running behind a reverse proxy (nginx)
- Using environment-specific configs
- Setting up log rotation
- Enabling HTTPS
- Using production WSGI server (gunicorn/uvicorn workers)

---

## Environment Variables

Key environment variables (set in `.env`):

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# LLM Provider (choose one)
LLM_PROVIDER=openai  # or anthropic, ollama
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_API_BASE_URL=http://localhost:11434

# Application
APP_NAME=SnapAnalyst
APP_VERSION=0.1.0
ENVIRONMENT=development
DEBUG=true

# Paths
SNAPDATA_PATH=./snapdata
CHROMA_DB_PATH=./chroma_db
```

---

## Quick Commands Reference

```bash
# Start everything
./start_all.sh

# Stop everything
./stop_all.sh

# Check status
curl http://localhost:8000/health
curl http://localhost:8001

# View logs
tail -f logs/*.log

# Check processes
ps aux | grep -E "main.py|chainlit"

# Check ports
lsof -i :8000
lsof -i :8001
```

---

## Support

For issues or questions:
1. Check logs: `logs/api.log` and `logs/chainlit.log`
2. Verify PostgreSQL is running: `docker-compose ps`
3. Check environment variables: `cat .env`
4. Review documentation: `README.md`
