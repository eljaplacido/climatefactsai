# =============================================================================
# CONTENT DISCOVERY AGENT DOCKERFILE
# =============================================================================

FROM python:3.11-slim

LABEL maintainer="Climate News Team"
LABEL description="Content Discovery Agent - Web Scraping & Content Extraction"
LABEL version="1.0.0"

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/app/ms-playwright

# Asenna system-tason riippuvuudet (Playwright tarvitsee lisää)
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

# Kopioi requirements
COPY agents/requirements.txt /app/

# Asenna Python-riippuvuudet
RUN pip install --no-cache-dir -r requirements.txt

# Asenna Playwright-selaimet
RUN playwright install chromium

# Lataa spaCy-malli NLP:lle
RUN python -m spacy download fi_core_news_sm || python -m spacy download en_core_web_sm

# Kopioi agenttikoodit
COPY agents/shared/ /app/shared/
COPY agents/content_discovery/ /app/content_discovery/
COPY schemas/ /app/schemas/

# Luo data-hakemisto
RUN mkdir -p /data/scraped && \
    useradd -m -u 1000 agentuser && \
    chown -R agentuser:agentuser /app /data

USER agentuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-m", "content_discovery.main"]

