# Multi-stage Dockerfile for FastAPI Backend
FROM python:3.11-slim

# System dependencies for building packages (psycopg2, cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pyproject.toml first for layer caching
COPY pyproject.toml .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy backend application source code
COPY . .

# Create directory for generated hyper extracts and app storage
RUN mkdir -p /app/hyper_output /app/data

# Expose port
EXPOSE 8000

# Run FastAPI backend with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
