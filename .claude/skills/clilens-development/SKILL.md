---
title: CliLens Development Skill
description: Domain-specific development knowledge for CliLens.AI climate news platform
category: project-specific
version: 1.0.0
author: CliLens Team
tags: [climate-news, fastapi, nextjs, fact-checking, domain-driven-design]
---

# CliLens Development Skill

Master the specific patterns, constraints, and workflows for developing the CliLens.AI platform.

## 🎯 Overview

CliLens.AI is a climate news intelligence platform that aggregates, fact-checks, and distributes climate news across Europe. This skill provides domain-specific knowledge that generic agents lack.

---

## 📐 Architecture Rules

### Current Reality (December 2025)

```yaml
working_architecture:
  containers: [api, frontend, postgres, redis]
  communication: "Direct HTTP → API → SQL"
  scaling: "Vertical (single API instance)"
  async: "None (all synchronous)"

planned_but_not_operational:
  - Kafka event streaming
  - Microservices workers
  - LangGraph HITL workflows
  - Remotion video pipeline
```

### ⚠️ **Critical Rule: NO KAFKA ASSUMPTIONS**

```python
# ❌ WRONG - Don't write code assuming Kafka exists
from kafka import KafkaProducer
producer = KafkaProducer(bootstrap_servers='kafka:9092')

# ✅ CORRECT - Use direct database writes or future Celery tasks
from shared.database import get_postgres
db = get_postgres()
db.execute_query("INSERT INTO articles ...")
```

### Data Flow Pattern

```
User Request → Frontend → API → PostgreSQL → API → Frontend
                           ↓
                        Redis (caching/rate-limiting only)
```

**No event buses, no message queues currently operational.**

---

## 🚫 Mock Data Detection & Prevention

### The Problem

Previous implementations silently fell back to mock data when APIs failed, resulting in:
- High credibility scores with 0 claims assessed (confusing UI)
- Placeholder text appearing in production
- Users unable to distinguish real from fake data

### Rule: Fail Explicitly, Never Mock Silently

```python
# ❌ WRONG - Silent fallback to mock data
async def extract_claims(text: str):
    try:
        return await anthropic_api.extract(text)
    except Exception:
        return _generate_mock_claims(text)  # BAD!

# ✅ CORRECT - Fail with clear error
async def extract_claims(text: str):
    if not self.api_key:
        raise HTTPException(
            status_code=503,
            detail="Claim extraction unavailable: Anthropic API key not configured"
        )
    
    try:
        return await anthropic_api.extract(text)
    except RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit reached. Try again later."
        )
```

### Detection Checklist

Before claiming a feature is "done", verify:

```bash
# 1. No mock/placeholder comments in modified files
grep -r "placeholder\|TODO\|FIXME\|mock" src/

# 2. API keys are valid and tested
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" https://api.anthropic.com/v1/messages

# 3. Database has real data, not empty results
psql -c "SELECT count(*) FROM claims WHERE claim_type != 'mock';"

# 4. Frontend displays data correctly
curl http://localhost:5200/api/articles/test-id | jq .claims_count
# Should be > 0 if article processed, or claims_status should explain why not
```

---

## 📋 Definition of "Done" for Common Tasks

### Frontend ↔ Backend Sync

✅ **Complete when ALL of these pass:**

1. **Type Definitions Match**
   ```typescript
   // src/frontend/src/types/index.ts
   interface Article {
     article_id: string;
     claims_count: number;
     // ...
   }
   ```
   ```python
   # api/models.py
   class Article(BaseModel):
       article_id: str
       claims_count: int
       # ...
   ```

2. **API Returns Real Data**
   ```bash
   curl http://localhost:5200/api/articles?limit=1 | jq '.[0].claims_count'
   # Must return actual count, not null/0 from empty database
   ```

3. **Frontend Renders Correctly**
   - Visit http://localhost:5300
   - See real article with claims
   - No "undefined" or "null" displayed
   - Loading states work
   - Error states work

4. **Error Handling Works**
   ```bash
   # Stop API
   docker stop clilens-api
   
   # Frontend should show clear error, not crash
   # Visit http://localhost:5300 → should see "API unavailable" message
   ```

### New API Endpoint

✅ **Complete when ALL of these pass:**

1. **OpenAPI Documentation Auto-Generated**
   - Visit http://localhost:5200/docs
   - New endpoint visible with correct schema

2. **Tests Pass**
   ```bash
   pytest tests/api/test_your_new_route.py -v
   ```

3. **Frontend Integration**
   ```typescript
   // Added to src/lib/api.ts
   export const api = {
     yourNewEndpoint: async () => { ... }
   }
   ```

4. **Error Cases Handled**
   - 400 Bad Request (validation)
   - 401 Unauthorized (auth)
   - 404 Not Found (resource)
   - 503 Service Unavailable (dependencies)

### Claim Extraction Feature

✅ **Complete when ALL of these pass:**

1. **Anthropic API Key Verified**
   ```bash
   # In .env
   ANTHROPIC_API_KEY=sk-ant-api03-...
   
   # Test it works
   python -c "from anthropic import Anthropic; c=Anthropic(); print('OK')"
   ```

2. **Database Schema Updated**
   ```sql
   ALTER TABLE articles ADD COLUMN claims_status VARCHAR(50);
   -- Possible values: 'pending', 'processing', 'completed', 'failed'
   ```

3. **API Response Includes Status**
   ```json
   {
     "article_id": "123",
     "claims_count": 5,
     "claims_status": "completed",
     "claims_available": true
   }
   ```

4. **Frontend Handles All States**
   - `claims_status: "pending"` → Show "Analysis pending..."
   - `claims_status: "completed"` → Show claims
   - `claims_status: "failed"` → Show "Analysis failed" with reason

---

## 🧪 Testing Requirements

### Every Feature Must Have

```python
# tests/test_your_feature.py

def test_happy_path():
    """Feature works with valid inputs"""
    pass

def test_api_key_missing():
    """Feature fails gracefully when API key not set"""
    # Should return HTTP 503, not crash
    pass

def test_database_unavailable():
    """Feature handles database errors"""
    # Should return HTTP 503, not crash
    pass

def test_invalid_input():
    """Feature validates input correctly"""
    # Should return HTTP 400 with clear error message
    pass

def test_rate_limit_reached():
    """Feature handles rate limiting"""
    # Should return HTTP 429 with retry-after header
    pass
```

### No Kafka Dependency in Tests

```python
# ❌ WRONG - Test assumes Kafka running
@pytest.fixture
def kafka_consumer():
    return KafkaConsumer('test-topic')

# ✅ CORRECT - Test works with current architecture
@pytest.fixture
def db_connection():
    return get_postgres()  # Actually works
```

---

## 🌍 Multi-Country Support Patterns

### Database Design

```sql
-- Articles are country-specific
CREATE TABLE articles (
    article_id UUID PRIMARY KEY,
    country_code VARCHAR(2) NOT NULL,  -- ISO 3166-1 alpha-2
    language_code VARCHAR(2),          -- ISO 639-1
    -- ...
);

-- Countries are pre-populated
CREATE TABLE countries (
    country_code VARCHAR(2) PRIMARY KEY,
    country_name VARCHAR(100),
    country_name_native VARCHAR(100),
    flag_emoji VARCHAR(10),
    language_code VARCHAR(2),
    is_eu_member BOOLEAN,
    enabled BOOLEAN DEFAULT false  -- Only enabled countries shown in UI
);
```

### API Filtering Pattern

```python
# Always support country filtering in list endpoints
@app.get("/api/articles")
async def list_articles(
    country: Optional[str] = Query(None, min_length=2, max_length=2)
):
    filters = []
    if country:
        filters.append("country_code = :country")
        params["country"] = country.upper()
    # ...
```

### Frontend Pattern

```typescript
// Always normalize country codes to uppercase
const normalizeCountryCode = (code: string): string => {
  return code.toUpperCase().slice(0, 2);
};

// Always provide fallback for missing country data
const getCountryName = (code: string, countries: Country[]): string => {
  const country = countries.find(c => c.country_code === code);
  return country?.country_name || code;
};
```

---

## 🔐 Security Rules

### API Keys

```python
# ✅ CORRECT - Never log API keys
logger.info("Calling Anthropic API", key_length=len(api_key))

# ❌ WRONG - Don't log the actual key
logger.info(f"Using API key: {api_key}")
```

### User Input

```python
# ✅ CORRECT - Always validate and sanitize
from pydantic import BaseModel, Field, validator

class ArticleCreate(BaseModel):
    url: str = Field(..., max_length=2048)
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v
```

### SQL Queries

```python
# ✅ CORRECT - Use parameterized queries
query = "SELECT * FROM articles WHERE article_id = :id"
result = db.execute_query(query, params={"id": article_id})

# ❌ WRONG - Never use string formatting for SQL
query = f"SELECT * FROM articles WHERE article_id = '{article_id}'"
```

---

## 📝 Code Style

### Python (Backend)

```python
# Use type hints everywhere
def process_article(article_id: str, verify: bool = False) -> ArticleDetail:
    pass

# Use structured logging
logger.info(
    "Processing article",
    article_id=article_id,
    verify=verify,
    timestamp=datetime.utcnow()
)

# Use Pydantic for validation
class ArticleDetail(BaseModel):
    article_id: str
    title: str
    claims: List[ClaimDetail]
```

### TypeScript (Frontend)

```typescript
// Use explicit types
interface Article {
  article_id: string;
  title: string;
  claims_count: number;
}

// Use async/await, not promises
const fetchArticles = async (): Promise<Article[]> => {
  const response = await api.getArticles();
  return response.data;
};

// Handle errors explicitly
try {
  const articles = await fetchArticles();
} catch (error) {
  console.error('Failed to fetch articles:', error);
  setError('Unable to load articles. Please try again.');
}
```

---

## 🚀 Deployment Constraints

### Development Environment

```bash
# Always use Docker Compose for local development
docker-compose up -d

# Never assume system packages installed
# Everything runs in containers
```

### Environment Variables

```python
# Always have defaults for development
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/climatenews"
)

# But require critical keys in production
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY and os.getenv("ENVIRONMENT") == "production":
    raise ValueError("ANTHROPIC_API_KEY required in production")
```

---

## 🎨 UI/UX Patterns

### Credibility Badges

```typescript
// Always use consistent color coding
const getBadgeColor = (score: number): string => {
  if (score >= 80) return 'bg-green-500';  // High
  if (score >= 50) return 'bg-yellow-500'; // Medium
  return 'bg-red-500';                     // Low
};
```

### Loading States

```typescript
// Always show loading states for async operations
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);
const [data, setData] = useState<Article[]>([]);

// Pattern: loading → data OR error
if (loading) return <LoadingSpinner />;
if (error) return <ErrorMessage message={error} />;
return <ArticleList articles={data} />;
```

### Empty States

```typescript
// Always handle empty data gracefully
if (articles.length === 0) {
  return (
    <div className="text-center py-12">
      <p className="text-gray-500">No articles found.</p>
      <p className="text-sm text-gray-400 mt-2">
        Try adjusting your filters or check back later.
      </p>
    </div>
  );
}
```

---

## 🔄 Common Pitfalls & Solutions

### Pitfall 1: Assuming Kafka Exists

```python
# ❌ Code that will fail
from kafka import KafkaProducer
producer.send('topic', message)

# ✅ Current solution
from shared.database import get_postgres
db.execute_query("INSERT INTO ...")

# ✅ Future solution (when Celery configured)
from celery_app import process_article
process_article.delay(article_id)
```

### Pitfall 2: Mock Data Fallbacks

```python
# ❌ Silent mock fallback
try:
    real_data = api_call()
except:
    return mock_data()  # BAD!

# ✅ Explicit failure
try:
    real_data = api_call()
except APIError as e:
    raise HTTPException(503, f"Service unavailable: {e}")
```

### Pitfall 3: Incomplete Error Handling

```python
# ❌ Generic error
except Exception as e:
    return {"error": "Something went wrong"}

# ✅ Specific, actionable errors
except AnthropicAPIError as e:
    raise HTTPException(503, "AI service unavailable. Try again in 1 minute.")
except RateLimitError:
    raise HTTPException(429, "Rate limit exceeded. Retry after 60 seconds.")
except ValidationError as e:
    raise HTTPException(400, f"Invalid input: {e.errors()}")
```

---

## 📚 Required Reading Before Coding

1. **`docs/CURRENT_STATE.md`** - What exists now (10 min read)
2. **`New_plan.md`** - Future vision (20 min read)
3. **This skill file** - Development patterns (5 min read)

**Total: 35 minutes to get context**

---

## ✅ Pre-Commit Checklist

Before marking work as "done":

- [ ] No `TODO`, `FIXME`, `placeholder`, `mock` comments in new code
- [ ] All API keys tested and work
- [ ] Database migrations applied (if any)
- [ ] Tests pass: `pytest tests/`
- [ ] Linting passes: `ruff check .`
- [ ] Type checking passes: `mypy .`
- [ ] Frontend builds: `npm run build`
- [ ] Manual test in browser works
- [ ] Error cases handled gracefully
- [ ] Logs are structured and informative
- [ ] Updated `docs/CURRENT_STATE.md` if architecture changed

---

## 🎯 Success Metrics

### Code Quality

- **No mock data in production paths**
- **Explicit error handling** (no bare `except:`)
- **Type hints on all functions** (Python)
- **Strict TypeScript** (no `any` types)

### Feature Completeness

- **Works end-to-end** (frontend → API → database → frontend)
- **All states handled** (loading, error, empty, success)
- **Mobile responsive** (test on 375px width)
- **Accessible** (keyboard navigation, screen readers)

### Performance

- **API response < 200ms** (simple queries)
- **Frontend initial load < 2s** (on 3G)
- **Database queries optimized** (use EXPLAIN ANALYZE)

---

## 🆘 When Stuck

1. **Check `docs/CURRENT_STATE.md`** - Is the feature you need actually implemented?
2. **Check terminal logs** - `docker logs clilens-api` often reveals the issue
3. **Check database** - `psql -d climatenews -c "SELECT count(*) FROM articles"`
4. **Verify API keys** - Most "doesn't work" issues are missing/expired keys
5. **Simplify** - If feature assumes Kafka, redesign for direct API/DB

---

**This skill was created to prevent the "Documentation-Reality Mismatch" problem.**

**Last Updated:** 2025-12-18  
**Next Review:** After Phase 1 completion

