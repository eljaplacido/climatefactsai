# Content Domain

## Overview

The Content domain manages the lifecycle of verified climate articles, search functionality, tagging, and user feedback. It serves as the primary interface between verified intelligence and user-facing features.

## Responsibilities

- Store and retrieve verified articles with claims and fact-checks
- Implement search (keyword, semantic, filtered)
- Manage article tags and categorization
- Handle user feedback and ratings
- Export articles (PDF, CSV) for premium users
- Track article engagement metrics

## Data Models

### Article (Verified)
```python
class Article(BaseModel):
    id: int
    title: str
    url: str
    source: str
    author: str | None
    published_at: datetime | None
    full_text: str
    excerpt: str | None
    
    # Credibility
    credibility_score: float  # 0-1
    credibility_level: str  # 'high', 'medium', 'low'
    
    # Classification
    country: str | None
    language_code: str
    tags: list[str]
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
```

### ArticleDetail (with Claims)
Extends `Article` with:
- `claims: list[Claim]`
- `fact_checks: list[FactCheck]`
- `feedback_summary: FeedbackSummary`

## Services

- **ArticleService**: CRUD, search, stats
- **FeedbackService**: User ratings, comments
- **ExportService**: PDF/CSV generation
- **TagService**: Tag management, suggestions

## API Endpoints

- `GET /api/articles` - List/search articles
- `GET /api/articles/{id}` - Article detail with claims
- `GET /api/articles/{id}/feedback` - Feedback summary
- `POST /api/articles/{id}/feedback` - Submit feedback
- `POST /api/export/pdf` - Export to PDF
- `GET /api/tags` - Popular tags

## Search Features

### Keyword Search
- Full-text search on title + excerpt
- PostgreSQL `ts_vector` with relevance ranking

### Semantic Search (Premium)
- pgvector cosine similarity on embeddings
- Query: "Show me disputed claims about Arctic ice"
- Returns conceptually similar articles

### Filters
- Country
- Credibility level
- Date range
- Tags
- Source

## Future Enhancements
- Personalized recommendations
- Article watch lists
- Collaborative tagging
- Citation network graph

