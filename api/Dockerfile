FROM python:3.11-slim

WORKDIR /app

# Copy dependencies
COPY api/requirements.txt /app/api/requirements.txt
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/api/requirements.txt

# Copy source code
COPY api /app/api
COPY src/backend /app/src/backend
COPY schemas /app/schemas

# Configure PYTHONPATH to find both api and src.backend modules
ENV PYTHONPATH=/app:/app/src/backend

EXPOSE 8000

# Start the API
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
