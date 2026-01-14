#!/bin/bash
# SnapAnalyst - Start All Services
# This script kills any existing instances and starts both backend and frontend

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔧 SnapAnalyst - Starting Services${NC}"
echo ""

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 1. Kill existing processes
echo -e "${YELLOW}🛑 Stopping existing services...${NC}"

# Kill backend (FastAPI)
if pgrep -f "python src/api/main.py" > /dev/null; then
    echo "  Killing backend API..."
    pkill -9 -f "python src/api/main.py" || true
    sleep 1
fi

# Kill frontend (Chainlit)
if pgrep -f "chainlit run" > /dev/null; then
    echo "  Killing Chainlit UI..."
    pkill -9 -f "chainlit run" || true
    sleep 1
fi

# Kill by port (backup)
if lsof -ti :8000 > /dev/null 2>&1; then
    echo "  Killing process on port 8000..."
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
fi

if lsof -ti :8001 > /dev/null 2>&1; then
    echo "  Killing process on port 8001..."
    lsof -ti :8001 | xargs kill -9 2>/dev/null || true
fi

sleep 2
echo -e "${GREEN}✅ Old processes stopped${NC}"
echo ""

# 2. Activate virtual environment
echo -e "${YELLOW}🔧 Activating virtual environment...${NC}"
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements/base.txt"
    exit 1
fi

source venv/bin/activate
echo -e "${GREEN}✅ Virtual environment activated${NC}"
echo ""

# 3. Check if PostgreSQL is running
echo -e "${YELLOW}🔧 Checking PostgreSQL...${NC}"
if ! nc -z localhost 5432 2>/dev/null; then
    echo -e "${RED}❌ PostgreSQL is not running on port 5432${NC}"
    echo "Please start PostgreSQL with: docker-compose up -d"
    exit 1
fi
echo -e "${GREEN}✅ PostgreSQL is running${NC}"
echo ""

# 4. Start Backend (FastAPI)
echo -e "${YELLOW}🚀 Starting Backend API (port 8000)...${NC}"
export PYTHONPATH=.
nohup python src/api/main.py > logs/api.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Check if backend is running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend API started (PID: $BACKEND_PID)${NC}"
else
    echo -e "${RED}❌ Backend API failed to start. Check logs/api.log${NC}"
    exit 1
fi
echo ""

# 5. Start Frontend (Chainlit)
echo -e "${YELLOW}🚀 Starting Chainlit UI (port 8001)...${NC}"
export API_BASE_URL=http://localhost:8000
nohup chainlit run chainlit_app.py --port 8001 > logs/chainlit.log 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 3

# Check if frontend is running
if curl -s http://localhost:8001 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Chainlit UI started (PID: $FRONTEND_PID)${NC}"
else
    echo -e "${RED}❌ Chainlit UI failed to start. Check logs/chainlit.log${NC}"
    exit 1
fi
echo ""

# 6. Summary
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ✅ All Services Started Successfully!  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📊 Service URLs:${NC}"
echo -e "  🔹 Backend API:  http://localhost:8000"
echo -e "  🔹 API Docs:     http://localhost:8000/docs"
echo -e "  🔹 Chainlit UI:  http://localhost:8001"
echo ""
echo -e "${YELLOW}📝 Logs:${NC}"
echo -e "  🔹 Backend:  tail -f logs/api.log"
echo -e "  🔹 Frontend: tail -f logs/chainlit.log"
echo ""
echo -e "${YELLOW}🛑 To stop all services:${NC}"
echo -e "  ./stop_all.sh"
echo ""
echo -e "${GREEN}🎉 Ready to use! Open http://localhost:8001 in your browser${NC}"
