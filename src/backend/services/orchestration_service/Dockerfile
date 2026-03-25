# =============================================================================
# ORCHESTRATION SERVICE DOCKERFILE
# =============================================================================

FROM python:3.11-slim

LABEL maintainer="CliLens.AI Team"
LABEL description="Orchestration Service - Workflow Coordinator"
LABEL version="1.0.0"

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src/backend

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY src/backend/shared/ /app/src/backend/shared/
COPY src/backend/services/orchestration_service/src/ /app/src/backend/services/orchestration_service/src/
COPY schemas/ /app/schemas/

# Create user
RUN useradd -m -u 1000 serviceuser && \
    chown -R serviceuser:serviceuser /app

USER serviceuser

WORKDIR /app/src/backend/services/orchestration_service/src

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "main.py"]
