# CliLens.AI Backend API Reference

## Base URL
- **Development**: `http://localhost:5200`
- **Production**: `https://api.clilens.ai`

## Authentication

### JWT Bearer Token
```http
Authorization: Bearer <access_token>
```

### API Key (for B2B)
```http
X-API-Key: clilens_<key>
```

## Core Endpoints

### Articles

#### List Articles
```http
GET /api/articles?q=climate&country=US&limit=20&offset=0
```

**Query Parameters:**
- `q` (optional): Search query
- `country` (optional): ISO country code
- `credibility` (optional): high, medium, low
- `tags` (optional): Comma-separated tags
- `date_from` (optional): ISO date
- `date_to` (optional): ISO date
- `limit` (default: 20, max: 100)
- `offset` (default: 0)

**Response:**
```json
[
  {
    "id": 1,
    "title": "Arctic Ice Decline Accelerates",
    "url": "https://example.com/article",
    "source": "BBC",
    "published_at": "2025-01-15T10:00:00Z",
    "excerpt": "New data shows...",
    "credibility_score": 0.89,
    "credibility_level": "high",
    "country": "US",
    "tags": ["arctic", "ice", "climate"],
    "created_at": "2025-01-15T11:00:00Z"
  }
]
```

#### Get Article Detail
```http
GET /api/articles/{id}
```

**Response:**
```json
{
  "id": 1,
  "title": "Arctic Ice Decline Accelerates",
  "url": "https://example.com/article",
  "source": "BBC",
  "full_text": "...",
  "credibility_score": 0.89,
  "credibility_level": "high",
  "claims": [
    {
      "id": "claim-uuid",
      "claim_text": "Arctic ice extent decreased by 13% per decade",
      "claim_type": "factual",
      "verification_status": "verified",
      "confidence_score": 0.92,
      "evidence": [...]
    }
  ]
}
```

### Search

#### Semantic Search (Professional+)
```http
POST /api/search/semantic
Content-Type: application/json

{
  "query": "renewable energy investments",
  "limit": 10,
  "country": "FI"
}
```

### URL Analysis

#### Submit URL for Verification (Basic+)
```http
POST /api/analyze-url
Content-Type: application/json

{
  "url": "https://example.com/article",
  "priority": "normal"
}
```

**Response:**
```json
{
  "id": "analysis-uuid",
  "user_id": "user-uuid",
  "url": "https://example.com/article",
  "status": "pending",
  "progress": 0,
  "created_at": "2025-01-15T12:00:00Z"
}
```

#### Get Analysis Result
```http
GET /api/analyze-url/{analysis_id}
```

### User & Auth

#### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### Get User Profile
```http
GET /api/user/profile
Authorization: Bearer <token>
```

#### Get Usage Stats
```http
GET /api/user/usage?period=monthly
Authorization: Bearer <token>
```

**Response:**
```json
{
  "tier": "professional",
  "period": "monthly",
  "articles_viewed": 127,
  "articles_limit": -1,
  "url_analyses": 8,
  "url_analyses_limit": 20,
  "api_calls": 342,
  "api_calls_limit": 1000
}
```

### Subscriptions

#### Create Subscription
```http
POST /api/subscription/create
Content-Type: application/json
Authorization: Bearer <token>

{
  "tier": "professional",
  "payment_method_id": "pm_xxx"
}
```

#### Get Current Subscription
```http
GET /api/subscription/current
Authorization: Bearer <token>
```

### API Keys

#### Create API Key (Professional+)
```http
POST /api/api-keys
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "Production API Key",
  "scopes": ["read", "write"],
  "expires_in_days": 90
}
```

**Response:**
```json
{
  "id": "key-uuid",
  "name": "Production API Key",
  "api_key": "clilens_abc123...",
  "scopes": ["read", "write"],
  "expires_at": "2025-04-15T00:00:00Z",
  "warning": "Save this key securely. It will not be shown again!"
}
```

#### List API Keys
```http
GET /api/api-keys
Authorization: Bearer <token>
```

#### Revoke API Key
```http
DELETE /api/api-keys/{key_id}
Authorization: Bearer <token>
```

### Export (Professional+)

#### Export Article to PDF
```http
POST /api/export/article/{article_id}/pdf
Authorization: Bearer <token>
```

**Response:** PDF file download

#### Export Search Results to CSV
```http
POST /api/export/search/csv?country=US&credibility=high
Authorization: Bearer <token>
```

**Response:** CSV file download

### Admin

#### Trigger Workflow (Admin only)
```http
POST /api/admin/trigger-workflow
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "task_id": "optional-task-id"
}
```

#### Get Stats
```http
GET /api/stats
```

**Response:**
```json
{
  "total_articles": 1523,
  "articles_today": 12,
  "total_fact_checks": 7856,
  "verified_claims": 6234,
  "average_confidence": 0.84,
  "last_updated": "2025-01-15T14:30:00Z"
}
```

## Error Responses

All endpoints return standard HTTP status codes:

- **200**: Success
- **201**: Created
- **400**: Bad Request (validation error)
- **401**: Unauthorized (missing/invalid token)
- **403**: Forbidden (insufficient permissions)
- **404**: Not Found
- **429**: Too Many Requests (rate limit exceeded)
- **500**: Internal Server Error

**Error Response Format:**
```json
{
  "detail": "Article not found"
}
```

## Rate Limiting

Rate limits are enforced per subscription tier. Headers included in response:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 987
X-RateLimit-Reset: 1642521600
```

## Pagination

List endpoints support cursor-based pagination:

```http
GET /api/articles?limit=20&offset=0
```

**Response includes:**
```json
{
  "items": [...],
  "total": 1523,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

## Interactive Documentation

Visit `/docs` for Swagger UI interactive documentation:
- **Development**: `http://localhost:5200/docs`
- **Production**: `https://api.clilens.ai/docs`

