# Ingestion Domain

## Overview

The Ingestion domain is responsible for discovering, fetching, and parsing climate news articles from various sources. It forms the entry point of the CliLens.AI content pipeline.

## Responsibilities

### 1. Content Discovery
- Monitor RSS feeds from trusted climate news sources
- Query Perplexity AI for trending climate topics
- Schedule periodic content fetches
- Track source reliability and freshness

### 2. Content Extraction
- Fetch full article content from URLs
- Extract structured metadata (title, author, publish date, source)
- Parse article body text while removing ads and boilerplate
- Handle various content formats (HTML, JSON, XML)

### 3. Initial Processing
- Detect article language
- Assign country/region tags based on content
- Extract initial topics and keywords
- Store raw content for pipeline processing

## Data Flow

```
[RSS Feeds / Perplexity AI]
         ↓
[Content Discovery Agent]
         ↓
[Celery Task: discover_articles (queue: celery)]
         ↓
[Content Scraper]
         ↓
[Article Parser]
         ↓
[PostgreSQL: articles table (raw)]
         ↓
[Celery Task: verify_claims triggered with article_ids]
```

## Key Components

### PerplexityNewsDiscovery
- **Purpose**: Query Perplexity AI for climate news
- **Inputs**: Search query, country filters, date range
- **Outputs**: List of article URLs and metadata
- **Configuration**: `PERPLEXITY_API_KEY`, rate limits

### ContentScraper
- **Purpose**: Fetch and extract article content
- **Inputs**: Article URL
- **Outputs**: Parsed article with full text and metadata
- **Technologies**: `requests`, `BeautifulSoup4`, `newspaper3k`

### ArticleParser
- **Purpose**: Structure raw HTML into clean article data
- **Inputs**: Raw HTML content
- **Outputs**: Article model with:
  - Title, author, source
  - Published date
  - Full text and excerpt
  - Source URL and domain
  - Language detection

## Data Models

### Article (Initial State)
```python
class ArticleIngested(BaseModel):
    """Article after ingestion, before verification."""
    id: int
    title: str
    url: str
    source: str
    author: str | None
    published_at: datetime | None
    full_text: str
    excerpt: str | None
    language_code: str = "en"
    country: str | None
    
    # Metadata
    discovered_via: str  # 'rss', 'perplexity', 'manual'
    scraped_at: datetime
    content_hash: str  # For deduplication
    
    # Status
    ingestion_status: str = "pending_verification"
```

## Celery Tasks

### discover_articles
**Trigger**: Scheduled or manually dispatched to begin ingestion
**Queue**: `celery` (default)
**Return payload**:
```json
{
  "task_id": "...",
  "country": "FI",
  "article_ids": ["..."],
  "discovery_method": "perplexity",
  "discovered_at": "2025-01-15T14:00:00"
}
```

### scheduled_rss_ingestion / poll_rss_feeds
**Trigger**: Article successfully fetched from RSS feed
**Return payload**:
```json
{
  "task_id": "...",
  "total_fetched": 12,
  "new_after_dedup": 5,
  "inserted": 5,
  "article_ids": ["..."]
}
```

### discover_articles (failure path)
**Trigger**: Scraping or parsing failure — Celery autoretry handles retries
**Retry policy**: `max_retries=3`, exponential backoff via Celery
**Return payload on exhaustion**:
```json
{
  "task_id": "...",
  "article_ids": [],
  "discovery_method": "database_fallback"
}
```

## Source Configuration

### RSS Feeds
```yaml
sources:
  - name: "BBC Climate"
    url: "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"
    reliability: "high"
    update_frequency: "1h"
    
  - name: "The Guardian Climate"
    url: "https://www.theguardian.com/environment/climate-crisis/rss"
    reliability: "high"
    update_frequency: "30m"
    
  - name: "Nature Climate Change"
    url: "https://www.nature.com/nclimate.rss"
    reliability: "very_high"
    update_frequency: "6h"
```

### Perplexity Search Queries
```python
CLIMATE_QUERIES = [
    "climate change policy EU",
    "renewable energy investments 2025",
    "arctic ice extent latest",
    "carbon emissions reduction",
    "climate adaptation strategies"
]
```

## Quality Controls

### Duplicate Detection
- Hash article content (SHA-256)
- Check against existing articles by URL and content hash
- Skip duplicates, log in monitoring

### Content Validation
- Minimum text length: 300 characters
- Maximum text length: 50,000 characters
- Valid URL format
- Published date within last 90 days (configurable)
- Language detection confidence > 0.8

### Source Reputation
- Maintain source reliability scores
- Block known misinformation sources
- Track source update frequency and uptime

## Error Handling

### Retry Strategy
- 3 retries with exponential backoff
- Rotate user agents on 403/429 errors
- Use proxy rotation for persistent blocks
- Dead letter queue after max retries

### Monitoring
- Track ingestion success rate by source
- Alert on >10% failure rate
- Monitor average processing time per article
- Track queue depths and lag

## Configuration

### Environment Variables
```
PERPLEXITY_API_KEY=pplx-xxx
SCRAPER_USER_AGENT=CliLensBot/1.0
SCRAPER_TIMEOUT=30
MAX_CONCURRENT_SCRAPES=5
INGESTION_CELERY_QUEUE=celery
```

## Future Enhancements

- [ ] Video content transcription support
- [ ] PDF/research paper parsing
- [ ] Social media post ingestion (Twitter/X, LinkedIn)
- [ ] Real-time news alerts via WebSocket
- [ ] Multi-language content translation pipeline

