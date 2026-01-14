# SnapAnalyst Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements/base.txt requirements/base.txt
COPY requirements/dev.txt requirements/dev.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements/base.txt

# Copy application code
COPY src/ /app/src/
COPY migrations/ /app/migrations/
COPY pyproject.toml /app/

# Create logs directory
RUN mkdir -p /app/logs

# Expose port
EXPOSE 8000

# Default command (can be overridden)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
