#!/bin/bash
# SnapAnalyst - Stop All Services

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🛑 SnapAnalyst - Stopping All Services${NC}"
echo ""

# Kill backend (FastAPI)
if pgrep -f "python src/api/main.py" > /dev/null; then
    echo "  Stopping Backend API..."
    pkill -9 -f "python src/api/main.py"
    echo -e "${GREEN}✅ Backend stopped${NC}"
else
    echo "  Backend API not running"
fi

# Kill frontend (Chainlit)
if pgrep -f "chainlit run" > /dev/null; then
    echo "  Stopping Chainlit UI..."
    pkill -9 -f "chainlit run"
    echo -e "${GREEN}✅ Chainlit stopped${NC}"
else
    echo "  Chainlit UI not running"
fi

# Kill by port (backup)
if lsof -ti :8000 > /dev/null 2>&1; then
    echo "  Cleaning up port 8000..."
    lsof -ti :8000 | xargs kill -9 2>/dev/null
fi

if lsof -ti :8001 > /dev/null 2>&1; then
    echo "  Cleaning up port 8001..."
    lsof -ti :8001 | xargs kill -9 2>/dev/null
fi

echo ""
echo -e "${GREEN}✅ All services stopped${NC}"
