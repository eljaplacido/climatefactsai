# =============================================================================
# INGESTION SERVICE DOCKERFILE
# =============================================================================

FROM python:3.11-slim

LABEL maintainer="CliLens.AI Team"
LABEL description="Ingestion Service - Content Discovery & Web Scraping"
LABEL version="1.0.0"

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src/backend \
    PLAYWRIGHT_BROWSERS_PATH=/app/ms-playwright

# Install system dependencies (Playwright requires additional packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Download spaCy models for NLP
RUN python -m spacy download fi_core_news_sm || python -m spacy download en_core_web_sm

# Copy backend code
COPY src/backend/shared/ /app/src/backend/shared/
COPY src/backend/services/ingestion_service/src/ /app/src/backend/services/ingestion_service/src/
COPY schemas/ /app/schemas/

# Create data directory
RUN mkdir -p /data/scraped && \
    useradd -m -u 1000 serviceuser && \
    chown -R serviceuser:serviceuser /app /data

USER serviceuser

WORKDIR /app/src/backend/services/ingestion_service/src

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "main.py"]

