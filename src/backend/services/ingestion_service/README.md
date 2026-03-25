# Ingestion Service (Content Discovery)

## Purpose
The Ingestion Service is responsible for discovering, collecting, and processing climate news content from various sources. It acts as the entry point for content in the CliLens.AI pipeline.

## Core Responsibilities
1. **Source Monitoring**: Scan configured news sources (RSS feeds, APIs) for new climate-related content
2. **Content Extraction**: Scrape and extract article text, metadata, and structured data
3. **Claim Extraction**: Use NLP to identify factual claims within articles
4. **Data Handoff**: Send extracted content and claims to the Verification Service via Kafka

## Architecture

### Components
- `main.py`: Main service entry point and Content Discovery Agent
- `scraper.py`: News scraper pool for concurrent web scraping
- `claim_extractor.py`: NLP-based claim extraction
- `perplexity_news_discovery.py`: Perplexity AI integration for content discovery

### Dependencies
- **Shared Modules**: `shared.config`, `shared.logger`, `shared.kafka_client`, `shared.database`
- **External APIs**: RSS feeds, news source APIs
- **NLP Libraries**: spaCy, transformers (for claim extraction)
- **Web Scraping**: BeautifulSoup, Scrapy, or custom scrapers

## Data Flow

```
News Sources (RSS/API)
  → Scraper Pool
  → Article Extraction
  → Claim Extraction
  → Kafka (factcheck_queue)
  → Verification Service
```

## Kafka Integration

### Consumes From
- `discovery_queue`: Commands to initiate content discovery tasks

### Produces To
- `factcheck_queue`: Extracted articles with claims for verification
  - Schema: `schemas/discovery_to_factcheck.json`

## Configuration
Service configuration is managed via the shared config module:
- `scraper.scraper_max_concurrent_requests`: Max parallel scraping operations
- `scraper.scraper_rate_limit_delay`: Delay between requests (in ms)
- `scraper.scraper_user_agent`: User agent string for web requests
- `location.news_sources`: List of news source URLs

## Database Schema
### Tables Used
- `articles`: Stores discovered articles with metadata
- `source_credibility`: News source credibility scores

## API Contract

### Input (Kafka Message)
```json
{
  "command": "discover_content",
  "taskId": "task-20251022-001",
  "parameters": {
    "targetLocation": {
      "name": "Finland",
      "coordinates": [60.1699, 24.9384]
    },
    "dateRange": {
      "start": "2025-10-01",
      "end": "2025-10-22"
    }
  }
}
```

### Output (Kafka Message)
```json
{
  "schemaVersion": "1.0",
  "taskId": "task-20251022-001",
  "articleId": "uuid",
  "sourceArticle": {
    "url": "https://...",
    "title": "Article Title",
    "publishedDate": "2025-10-22T10:00:00Z",
    "author": "Author Name",
    "source": "Source Name",
    "sourceCredibilityScore": 75,
    "extractedText": "Full article text...",
    "language": "fi",
    "tags": ["climate", "emissions"]
  },
  "claims": [
    {
      "claimText": "Global temperature increased by 1.5°C",
      "confidence": 0.9,
      "claimType": "factual"
    }
  ],
  "metadata": {
    "discoveryTimestamp": "2025-10-22T12:00:00Z",
    "processingTimeMs": 1500,
    "discoveryAgentVersion": "1.0.0"
  }
}
```

## Running the Service

### Development
```bash
cd src/backend/services/ingestion_service
python src/main.py
```

### Docker
```bash
docker build -t clilens-ingestion-service .
docker run -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 clilens-ingestion-service
```

## Testing
```bash
pytest tests/test_content_discovery.py
```

## Logging
Structured logging via `shared.logger` with context:
- `task_id`: Task identifier
- `article_url`: Article being processed
- `source_count`: Number of sources scanned

## Error Handling
- Failed scrapes are logged but don't halt the pipeline
- Invalid articles are filtered out before Kafka publish
- Retry logic for transient failures (network issues)
- Schema validation before publishing to Kafka

## Future Enhancements
- Perplexity AI integration for intelligent source discovery
- Multi-language support
- Advanced NLP claim extraction with fine-tuned models
- Real-time monitoring of social media sources
