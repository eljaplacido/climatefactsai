# =============================================================================
# VIDEO PRODUCTION AGENT DOCKERFILE
# =============================================================================

FROM python:3.11-slim

LABEL maintainer="Climate News Team"
LABEL description="Video Production Agent - Short-form Video Generation"
LABEL version="1.0.0"

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# VideoEditointi tarvitsee lisäkirjastoja
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ /app/shared/
COPY video_production/ /app/video_production/
COPY ../schemas/ /app/schemas/

RUN mkdir -p /media/temp && \
    useradd -m -u 1000 agentuser && \
    chown -R agentuser:agentuser /app /media

USER agentuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-m", "video_production.main"]

