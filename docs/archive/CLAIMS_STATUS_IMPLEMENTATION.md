# Claims Status Implementation Guide

## Overview

This document describes the implementation of the `claims_status` field tracking system for articles in the CliLens Climate News platform.

**Reference**: `docs/CURRENT_STATE.md` lines 206-224

**Date**: 2025-12-18

---

## Table of Contents

1. [Database Schema](#database-schema)
2. [Backend Models](#backend-models)
3. [API Integration](#api-integration)
4. [Frontend Types](#frontend-types)
5. [Usage Examples](#usage-examples)
6. [Testing](#testing)
7. [Migration Guide](#migration-guide)

---

## Database Schema

### Migration File

**Location**: `migrations/versions/002_add_claims_status.sql`

### New Columns

The following columns were added to the `articles` table:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `claims_status` | VARCHAR(50) | 'pending' | Status of claims extraction process |
| `claims_error_message` | TEXT | NULL | Error message if extraction failed |
| `claims_processed_at` | TIMESTAMP | NULL | Timestamp when processing completed or failed |

### Status Values

- **pending**: Article awaiting claims extraction
- **processing**: Claims extraction in progress
- **completed**: Claims successfully extracted
- **failed**: Claims extraction failed with error

### Indexes

```sql
-- Index for filtering by status
CREATE INDEX idx_articles_claims_status ON articles(claims_status);

-- Composite index for status + count queries
CREATE INDEX idx_articles_claims_status_count ON articles(claims_status, claims_count);
```

### Helper Function

```sql
-- Function to determine if claims are available
CREATE FUNCTION article_has_claims_available(
    p_claims_status VARCHAR(50),
    p_claims_count INTEGER
) RETURNS BOOLEAN
```

Returns `true` if `claims_status = 'completed'` AND `claims_count > 0`

### View

```sql
-- View with computed claims_available field
CREATE VIEW articles_claims_status_view AS
SELECT
    a.article_id,
    a.title,
    a.claims_status,
    a.claims_count,
    article_has_claims_available(a.claims_status, a.claims_count) as claims_available,
    ...
FROM articles a
```

---

## Backend Models

### Location

`src/backend/app/domains/content/models.py`

### Article Model

```python
class Article(BaseModel):
    # ... existing fields ...

    # Claims processing status
    claims_status: Optional[str] = Field(
        default="pending",
        description="Status: pending, processing, completed, failed"
    )
    claims_error_message: Optional[str] = Field(
        default=None,
        description="Error message if extraction failed"
    )
    claims_processed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when processing completed/failed"
    )
```

### ArticleDetail Model

```python
class ArticleDetail(Article):
    # ... existing fields ...

    claims_available: bool = Field(
        default=False,
        description="Computed: true if completed with claims"
    )

    def model_post_init(self, __context):
        """Compute claims_available based on status and count"""
        claims_available = (
            self.claims_status == 'completed' and
            self.claim_count > 0
        )
        object.__setattr__(self, 'claims_available', claims_available)
```

### Repository Updates

**Location**: `src/backend/app/domains/content/repository.py`

The repository was updated to:
1. Include `claims_status`, `claims_error_message`, and `claims_processed_at` in all SELECT queries
2. Map these fields in `_row_to_article()` method
3. Support the new fields in both trust-aware and legacy query paths

---

## API Integration

### Response Format

#### GET /api/v1/articles

```json
{
  "items": [
    {
      "article_id": "uuid",
      "title": "Article Title",
      "claims_status": "completed",
      "claims_count": 5,
      "verified_claim_count": 3,
      "claims_error_message": null,
      "claims_processed_at": "2025-12-18T10:30:00Z"
    }
  ]
}
```

#### GET /api/v1/articles/{article_id}

```json
{
  "article_id": "uuid",
  "title": "Article Title",
  "claims_status": "completed",
  "claims_count": 5,
  "verified_claim_count": 3,
  "claims_available": true,
  "claims_error_message": null,
  "claims_processed_at": "2025-12-18T10:30:00Z",
  "claims": [...]
}
```

---

## Frontend Types

### Location

`src/frontend/src/types/index.ts`

### Article Interface

```typescript
export interface Article {
  article_id: string;
  title: string;
  // ... existing fields ...

  claims_status?: "pending" | "processing" | "completed" | "failed";
  claims_error_message?: string;
  claims_processed_at?: string;
}
```

### ArticleDetail Interface

```typescript
export interface ArticleDetail extends Article {
  full_text?: string;
  language_code: string;
  claims: ClaimDetail[];
  claims_available: boolean;
}
```

---

## Usage Examples

### Claims Status Manager

**Location**: `src/backend/shared/claims_status_manager.py`

#### Basic Usage

```python
from shared.claims_status_manager import get_claims_status_manager

manager = get_claims_status_manager()

# 1. Start processing
manager.set_processing(article_id)

# 2. Complete successfully
manager.set_completed(
    article_id,
    claims_count=5,
    verified_claims_count=3
)

# 3. Handle failure
manager.set_failed(
    article_id,
    error_message="API timeout after 3 retries"
)

# 4. Check status
status = manager.get_status(article_id)
print(status["claims_status"])  # 'completed'
print(status["claims_count"])   # 5
```

### Integration with Verification Service

```python
from shared.claims_status_manager import get_claims_status_manager

class VerificationService:
    def __init__(self):
        self.status_manager = get_claims_status_manager()

    async def process_article(self, article_id: UUID):
        try:
            # Mark as processing
            self.status_manager.set_processing(article_id)

            # Extract claims
            claims = await self.extract_claims(article_id)

            if not claims:
                # No claims found, but extraction succeeded
                self.status_manager.set_completed(
                    article_id,
                    claims_count=0
                )
                return

            # Verify claims
            verified_count = await self.verify_claims(claims)

            # Mark as completed
            self.status_manager.set_completed(
                article_id,
                claims_count=len(claims),
                verified_claims_count=verified_count
            )

        except Exception as e:
            # Mark as failed with error
            self.status_manager.set_failed(
                article_id,
                error_message=str(e)
            )
            raise
```

---

## Testing

### Migration Tests

**Location**: `tests/test_claims_status_migration.py`

Tests verify:
- ✅ Column existence and types
- ✅ Index creation
- ✅ Helper function logic
- ✅ Status transitions
- ✅ Default values

Run with:
```bash
pytest tests/test_claims_status_migration.py -v
```

### API Tests

**Location**: `tests/test_claims_status_api.py`

Tests verify:
- ✅ Fields in list endpoint
- ✅ Fields in detail endpoint
- ✅ `claims_available` computation
- ✅ Error message handling
- ✅ Status filtering

Run with:
```bash
pytest tests/test_claims_status_api.py -v
```

---

## Migration Guide

### Running the Migration

1. **Backup database**:
   ```bash
   pg_dump climatenews > backup_$(date +%Y%m%d).sql
   ```

2. **Run migration**:
   ```bash
   psql -U climatenews_user -d climatenews -f migrations/versions/002_add_claims_status.sql
   ```

3. **Verify migration**:
   ```sql
   -- Check column exists
   SELECT column_name, data_type, column_default
   FROM information_schema.columns
   WHERE table_name = 'articles'
   AND column_name = 'claims_status';

   -- Check index exists
   SELECT indexname
   FROM pg_indexes
   WHERE tablename = 'articles'
   AND indexname = 'idx_articles_claims_status';
   ```

### Rollback (if needed)

The migration file includes a commented rollback script:

```sql
DROP VIEW IF EXISTS articles_claims_status_view;
DROP FUNCTION IF EXISTS article_has_claims_available(VARCHAR, INTEGER);
DROP INDEX IF EXISTS idx_articles_claims_status_count;
DROP INDEX IF EXISTS idx_articles_claims_status;

ALTER TABLE articles DROP COLUMN IF EXISTS claims_processed_at;
ALTER TABLE articles DROP COLUMN IF EXISTS claims_error_message;
ALTER TABLE articles DROP COLUMN IF EXISTS claims_status;

DROP TYPE IF EXISTS claims_status_enum;
```

---

## Status Transition Diagram

```
┌─────────┐
│ pending │
└────┬────┘
     │
     ▼
┌────────────┐    Success    ┌───────────┐
│ processing │──────────────>│ completed │
└────────────┘                └───────────┘
     │
     │ Failure
     ▼
┌────────┐
│ failed │
└────────┘
```

**Transitions**:
- `pending` → `processing`: When extraction starts
- `processing` → `completed`: When extraction succeeds
- `processing` → `failed`: When extraction fails
- `failed` → `pending`: Manual retry
- `completed` → `pending`: Manual reset

---

## Benefits

1. **Transparency**: Users can see the status of claims extraction
2. **Debugging**: Error messages help diagnose issues
3. **Performance**: Indexed fields enable efficient filtering
4. **Reliability**: Status tracking prevents duplicate processing
5. **User Experience**: Frontend can show loading states and errors

---

## Future Enhancements

1. **Retry Logic**: Automatically retry failed extractions
2. **Progress Tracking**: Add percentage completion for large articles
3. **Notifications**: Alert users when claims become available
4. **Analytics**: Track success/failure rates by source
5. **Queue Management**: Priority queue based on status

---

## Related Files

### Backend
- `migrations/versions/002_add_claims_status.sql`
- `src/backend/app/domains/content/models.py`
- `src/backend/app/domains/content/repository.py`
- `src/backend/shared/claims_status_manager.py`

### Frontend
- `src/frontend/src/types/index.ts`

### Tests
- `tests/test_claims_status_migration.py`
- `tests/test_claims_status_api.py`

### Documentation
- `docs/CURRENT_STATE.md` (lines 206-224)
- `docs/CLAIMS_STATUS_IMPLEMENTATION.md` (this file)

---

## Support

For questions or issues, contact the development team or create an issue in the repository.
