FROM python:3.11-slim

WORKDIR /app

# Copy dependencies
COPY api/requirements.txt /app/api/requirements.txt
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/api/requirements.txt

# Download spaCy English NER model so HallucinationDetector._extract_simple_entities
# uses real PERSON/ORG/GPE/LOC NER (not the regex fallback). Without this download
# the entity-overlap check silently degrades to capitalised-token matching, which
# the End2End audit (2026-05-26) flagged as the #3 truth-engine gap.
RUN python -m spacy download en_core_web_sm

# Copy source code
COPY api /app/api
COPY src/backend /app/src/backend
COPY schemas /app/schemas

# Configure PYTHONPATH to find both api and src.backend modules
ENV PYTHONPATH=/app:/app/src/backend

EXPOSE 8000

# Start the API
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
