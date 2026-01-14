#!/bin/bash

# SnapAnalyst Chainlit UI Startup Script
# Starts the Chainlit web interface for the AI chatbot

set -e

echo "🚀 Starting SnapAnalyst Chainlit UI..."
echo ""

# Check if in virtual environment
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Check if API is running
echo "🔍 Checking if API is running..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo ""
    echo "⚠️  WARNING: SnapAnalyst API is not running!"
    echo ""
    echo "Please start the API first:"
    echo "  PYTHONPATH=. python src/api/main.py"
    echo ""
    echo "Or in a separate terminal:"
    echo "  cd /Users/eric/Devl/Cursor/_private/SnapAnalyst"
    echo "  source venv/bin/activate"
    echo "  PYTHONPATH=. python src/api/main.py"
    echo ""
    read -p "Press Enter to continue anyway (Chainlit will start but chatbot won't work)..."
fi

# Set environment variables
export API_BASE_URL=${API_BASE_URL:-"http://localhost:8000"}
export CHAINLIT_PORT=${CHAINLIT_PORT:-8001}

echo ""
echo "✅ Configuration:"
echo "   API URL: $API_BASE_URL"
echo "   Chainlit Port: $CHAINLIT_PORT"
echo ""
echo "🌐 Starting Chainlit on http://localhost:$CHAINLIT_PORT"
echo ""
echo "Press Ctrl+C to stop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start Chainlit
chainlit run chainlit_app.py --port $CHAINLIT_PORT
