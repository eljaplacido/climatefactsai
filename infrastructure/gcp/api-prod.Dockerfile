# syntax=docker/dockerfile:1
# Production Dockerfile for ClimateNews API (FastAPI)
# Build context: repository root
# Target platform: linux/amd64 for Cloud Run compatibility

FROM --platform=linux/amd64 python:3.11-slim AS builder

WORKDIR /build

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests from repo root and api/ subfolder
COPY requirements.txt ./requirements.txt
COPY api/requirements.txt ./api-requirements.txt

# Install Python dependencies into a local user directory for easy copy
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt -r api-requirements.txt

# -----------------------------------------------------------------------------
# Production runtime stage
# -----------------------------------------------------------------------------
FROM --platform=linux/amd64 python:3.11-slim AS runner

WORKDIR /app

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security (Cloud Run best practice)
RUN groupadd -r appuser && \
    useradd -r -g appuser appuser && \
    mkdir -p /home/appuser/.local && \
    chown -R appuser:appuser /home/appuser

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:${PATH}

# Copy application source code
COPY api ./api
COPY src/backend ./src/backend
COPY schemas ./schemas

# Ensure correct ownership
RUN chown -R appuser:appuser /app

# Environment configuration
ENV PYTHONPATH=/app:/app/src/backend
ENV ENVIRONMENT=production
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cloud Run provides PORT at runtime; default to 8000 for local testing
ENV PORT=8000

# Switch to non-root user
USER appuser

EXPOSE 8000

# Lightweight health check (curl is available)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

# Use a single worker — Cloud Run horizontally scales instances, not workers within them.
# Uvicorn handles concurrency via async/ASGI underneath.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
