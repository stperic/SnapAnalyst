#!/bin/bash
# SnapAnalyst - Stop All Services
# This script stops both backend and frontend services

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping SnapAnalyst Services...${NC}"
echo ""

# Track if any services were stopped
STOPPED_ANY=false

# Kill backend (FastAPI)
if pgrep -f "python src/api/main.py" > /dev/null 2>&1; then
    echo -e "  Stopping Backend API..."
    pkill -9 -f "python src/api/main.py" || true
    STOPPED_ANY=true
fi

# Kill frontend (Chainlit)
if pgrep -f "chainlit run" > /dev/null 2>&1; then
    echo -e "  Stopping Chainlit UI..."
    pkill -9 -f "chainlit run" || true
    STOPPED_ANY=true
fi

# Kill by port (backup)
if lsof -ti :8000 > /dev/null 2>&1; then
    echo -e "  Stopping process on port 8000..."
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
    STOPPED_ANY=true
fi

if lsof -ti :8001 > /dev/null 2>&1; then
    echo -e "  Stopping process on port 8001..."
    lsof -ti :8001 | xargs kill -9 2>/dev/null || true
    STOPPED_ANY=true
fi

echo ""

if [ "$STOPPED_ANY" = true ]; then
    echo -e "${GREEN}All SnapAnalyst services stopped.${NC}"
else
    echo -e "${YELLOW}No SnapAnalyst services were running.${NC}"
fi

echo ""
echo -e "To start services again, run: ${GREEN}./start_all.sh${NC}"
