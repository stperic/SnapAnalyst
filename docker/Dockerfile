# SnapAnalyst Dockerfile
# Multi-stage build for FastAPI Backend + Chainlit UI

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    gcc \
    python3-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ==============================================================================
# Dependencies stage
# ==============================================================================
FROM base AS dependencies

# Copy requirements
COPY requirements/base.txt requirements/base.txt

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements/base.txt

# ==============================================================================
# Application stage
# ==============================================================================
FROM dependencies AS app

# Copy application source code
COPY src/ /app/src/
COPY ui/ /app/ui/
COPY datasets/ /app/datasets/
COPY scripts/ /app/scripts/

# Copy Chainlit configuration
COPY chainlit_app.py /app/
COPY chainlit.md /app/
COPY .chainlit/ /app/.chainlit/
COPY public/ /app/public/

# Create necessary directories
RUN mkdir -p /app/logs /data /app/chromadb

# Make scripts executable
RUN chmod +x /app/scripts/*.sh 2>/dev/null || true

# Expose ports
# 8000 - FastAPI API
# 8001 - Chainlit UI
EXPOSE 8000 8001

# Health check for API
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
