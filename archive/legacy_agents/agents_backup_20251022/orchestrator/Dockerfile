# =============================================================================
# ORCHESTRATOR AGENT DOCKERFILE
# =============================================================================

FROM python:3.11-slim

# Metadata
LABEL maintainer="Climate News Team"
LABEL description="Orchestrator Agent - Multi-Agent System Supervisor"
LABEL version="1.0.0"

# Aseta työhakemisto
WORKDIR /app

# Aseta ympäristömuuttujat
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Asenna system-tason riippuvuudet
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Kopioi requirements
COPY agents/requirements.txt /app/

# Asenna Python-riippuvuudet
RUN pip install --no-cache-dir -r requirements.txt

# Kopioi agenttikoodit
COPY agents/shared/ /app/shared/
COPY agents/orchestrator/ /app/orchestrator/

# Kopioi JSON-skeemat
COPY schemas/ /app/schemas/

# Luo ei-root käyttäjä
RUN useradd -m -u 1000 agentuser && \
    chown -R agentuser:agentuser /app

USER agentuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Käynnistyskomento
CMD ["python", "-m", "orchestrator.main"]

