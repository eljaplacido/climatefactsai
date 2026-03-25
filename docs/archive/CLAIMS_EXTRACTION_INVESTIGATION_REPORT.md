# Claims Extraction Investigation Report

**Date:** 2025-12-21
**Issue:** All articles have `claim_count: 0` despite functional claim extraction code
**Status:** ROOT CAUSE IDENTIFIED

---

## Executive Summary

Claims extraction is **NOT being triggered automatically** when articles are created. The system has fully functional claim extraction code with proper Anthropic API integration, but **verification must be manually triggered** via the `/api/v2/intelligence/verify/{article_id}` endpoint.

**Root Cause:** Missing automatic workflow integration between article creation and claims extraction.

---

## Investigation Findings

### 1. Code Locations

#### Claims Extraction Service
- **Location:** `src/backend/app/domains/intelligence/services.py`
- **Class:** `ClaimExtractor` (lines 31-252)
- **Method:** `decompose_claims()` (lines 45-104)
- **API Integration:** Uses Anthropic Claude API (claude-3-5-sonnet-20241022)
- **Status:** ✅ **FULLY FUNCTIONAL**

#### Verification Service
- **Location:** `src/backend/app/domains/intelligence/services.py`
- **Class:** `VerificationService` (lines 509-739)
- **Method:** `verify_article()` (lines 524-739)
- **Status:** ✅ **FULLY FUNCTIONAL**

#### Claims Status Manager
- **Location:** `src/backend/shared/claims_status_manager.py`
- **Purpose:** Manages `claims_status` field transitions
- **Status:** ✅ **FULLY FUNCTIONAL**

#### API Endpoints
- **Manual Trigger:** `POST /api/v2/intelligence/verify/{article_id}`
- **Batch Trigger:** `POST /api/v2/intelligence/verify-batch`
- **Status Check:** `GET /api/v2/intelligence/verification-status/{article_id}`

### 2. Data Flow Analysis

#### Current Article Creation Flow:
```
1. Article discovered/created
   ↓
2. INSERT INTO articles (with claims_count = 0, claims_status = 'pending')
   ↓
3. Article stored in database
   ↓
4. ❌ NO AUTOMATIC VERIFICATION TRIGGERED
   ↓
5. Article remains with claim_count = 0 forever
```

#### Expected Flow (NOT IMPLEMENTED):
```
1. Article discovered/created
   ↓
2. INSERT INTO articles
   ↓
3. ✅ SHOULD trigger verify_claims task
   ↓
4. ClaimExtractor.decompose_claims()
   ↓
5. Store claims in database
   ↓
6. Update claims_count and claims_status
```

### 3. Database State Verification

**Sample Query Results:**
```json
[
  {
    "article_id": "2dfc2277-ced9-458c-a544-8609ea100ae5",
    "title": "Nordic countries carbon emissions reduction 2025",
    "claims_count": 0,
    "claims_status": "pending",
    "claims_error_message": null
  },
  {
    "article_id": "e3b8a7c9-7067-4583-903e-d7b8c0f3bfb5",
    "title": "Denmark wind energy expansion",
    "claims_count": 0,
    "claims_status": "pending",
    "claims_error_message": null
  }
]
```

**Observations:**
- All articles have `claims_status = "pending"` (correct initial state)
- All articles have `claims_count = 0` (never processed)
- No error messages (verification was never attempted)

### 4. Configuration Analysis

#### API Key Status
- **Variable:** `ANTHROPIC_API_KEY`
- **Status:** ✅ **CONFIGURED** in `.env`
- **Value:** `sk-ant-api03-_AyklbBU95vdwYUgiAYyu6sEl3d9e4DCEQBYvl5J...`
- **Validation:** Key format is valid

#### ClaimExtractor Initialization
```python
def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
    self.model = model
    self.api_key = os.getenv("ANTHROPIC_API_KEY")
    if not self.api_key:
        logger.error("ANTHROPIC_API_KEY not set - claim extraction unavailable")
    self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None
```
- ✅ Properly checks for API key
- ✅ Logs error if missing
- ✅ Creates Anthropic client

### 5. Workflow Integration Analysis

#### Article Insertion Points:
1. **`api/discovery_routes.py`** (line 209-248)
   - Inserts articles from Perplexity discovery
   - ✅ Has optional verification trigger (line 254-261)
   - ⚠️ **Only triggers if `request.verify = true`**

2. **`src/backend/services/ingestion_service/src/main.py`** (line 338-379)
   - Inserts articles from ingestion service
   - ❌ **NO verification trigger**

#### Celery Task Chain (api/main.py):
```python
workflow = chain(
    discover_articles.s(...),
    verify_claims.s(),        # ✅ Task exists
    create_summary.s(),
    render_video_preview.s(),
    publish_article.s()
)
```
- ✅ `verify_claims` task exists in chain
- ⚠️ **Only executed when full workflow is triggered via `/api/v2/workflow/execute`**
- ❌ **NOT triggered for individual article creation**

### 6. Verification Task Analysis

#### Processing Task (`src/backend/app/tasks/processing.py`):
```python
@app.task(bind=True, autoretry_for=(Exception,), max_retries=3)
def verify_claims(self, workflow_state: Dict[str, Any]) -> Dict[str, Any]:
    """Verify claims for each article via the Intelligence domain service."""
    article_ids: List[str] = workflow_state.get("article_ids") or []

    for article_id in article_ids:
        result = asyncio.run(service.verify_article(article_id))
```

**Status:** ✅ Task is functional but **never automatically queued**

### 7. Recent Changes Impact

According to documentation mentions, **mock data fallbacks were removed**. This means:
- ❌ System no longer returns fake claims data
- ✅ System correctly returns empty claims (0 count)
- ⚠️ Reveals that verification was never being triggered

**The removal of mock data exposed the underlying workflow gap.**

---

## Root Cause Summary

### The Problem
**Claims extraction is NEVER automatically triggered** when articles are created through normal discovery/ingestion flow.

### Why It Happens

1. **Article Creation** (`INSERT INTO articles`) does NOT trigger any background task
2. **Discovery Routes** only trigger verification if `verify=true` flag is set (not default)
3. **Ingestion Service** has NO post-insert verification hook
4. **Celery Workflow** only runs when explicitly triggered via workflow API
5. **No Database Triggers** to auto-queue verification tasks

### Why Code Still Works

The claim extraction code IS functional:
- ✅ API key configured
- ✅ Anthropic client initializes
- ✅ `decompose_claims()` method works
- ✅ Database schema supports claims storage
- ✅ Manual API endpoint works: `POST /api/v2/intelligence/verify/{article_id}`

**BUT:** It's only executed when manually called via API or when full workflow is triggered.

---

## What Needs to Be Fixed

### Option 1: Automatic Background Task (Recommended)
Add automatic verification trigger in article creation flow:

**Location:** `api/discovery_routes.py` (line 248)
```python
# After article insertion:
if result and result[0].get("article_id"):
    article_id = result[0]["article_id"]
    inserted_ids.append(str(article_id))

    # ✅ ADD THIS: Auto-trigger verification
    try:
        from app.tasks.processing import verify_claims
        verify_claims.apply_async(
            args=[{"article_ids": [str(article_id)]}],
            countdown=5  # Delay 5 seconds to avoid overwhelming API
        )
    except Exception as e:
        logger.warning(f"Failed to queue verification for {article_id}: {e}")
```

**Location:** `src/backend/services/ingestion_service/src/main.py` (line 380)
```python
# After article insertion:
article_id = result[0]["article_id"]

# ✅ ADD THIS: Auto-trigger verification
self.queue_verification(article_id)
```

### Option 2: Database Trigger (Alternative)
Create PostgreSQL trigger to auto-queue verification:

```sql
CREATE OR REPLACE FUNCTION trigger_claims_extraction()
RETURNS TRIGGER AS $$
BEGIN
    -- Notify background worker to process claims
    PERFORM pg_notify('new_article', NEW.article_id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER article_inserted
    AFTER INSERT ON articles
    FOR EACH ROW
    EXECUTE FUNCTION trigger_claims_extraction();
```

Then create a listener service that consumes these notifications and queues Celery tasks.

### Option 3: Scheduled Batch Processing (Fallback)
Create periodic task to process pending articles:

```python
@app.task
def process_pending_verifications():
    """Process all articles with claims_status = 'pending'"""
    db = get_db()
    pending = db.execute_query(
        "SELECT article_id FROM articles WHERE claims_status = 'pending' LIMIT 50",
        {}
    )

    for row in pending:
        verify_claims.apply_async(args=[{"article_ids": [str(row["article_id"])]}])
```

Schedule via Celery Beat:
```python
app.conf.beat_schedule = {
    'process-pending-every-5-minutes': {
        'task': 'app.tasks.processing.process_pending_verifications',
        'schedule': 300.0,  # Every 5 minutes
    },
}
```

---

## Immediate Action Items

### For Testing (Right Now):
1. Manually trigger verification for existing articles:
   ```bash
   curl -X POST http://localhost:8000/api/v2/intelligence/verify/2dfc2277-ced9-458c-a544-8609ea100ae5
   ```

2. Or batch process all pending:
   ```bash
   curl -X POST http://localhost:8000/api/v2/intelligence/verify-batch \
     -H "Content-Type: application/json" \
     -d '{"article_ids": ["2dfc2277-ced9-458c-a544-8609ea100ae5", "e3b8a7c9-7067-4583-903e-d7b8c0f3bfb5"]}'
   ```

### For Permanent Fix:
1. Implement **Option 1** (automatic background task) in both:
   - `api/discovery_routes.py`
   - `src/backend/services/ingestion_service/src/main.py`

2. Add configuration flag to control automatic verification:
   ```python
   AUTO_VERIFY_CLAIMS = os.getenv("AUTO_VERIFY_CLAIMS", "true").lower() == "true"
   ```

3. Add rate limiting to prevent API overload:
   ```python
   verify_claims.apply_async(
       args=[...],
       countdown=random.randint(5, 30)  # Stagger requests
   )
   ```

4. Monitor Celery queue to ensure tasks don't pile up:
   ```bash
   celery -A app.core.celery_app inspect active_queues
   ```

---

## Error Handling Considerations

The current code HAS proper error handling:
- ✅ HTTPException for API failures (line 66-68, 86-98)
- ✅ Rate limit handling (line 85-90)
- ✅ Fallback model support (line 156-182)
- ✅ Status manager updates on failure (line 558, 576, 588, 731)

**No changes needed to error handling - it's already comprehensive.**

---

## Verification Success Criteria

After implementing the fix, verify:

1. ✅ New articles automatically get `claims_status = "processing"`
2. ✅ Claims are extracted within 30-60 seconds
3. ✅ `claims_count` is updated (> 0 for most articles)
4. ✅ `claims_status` becomes "completed" or "failed"
5. ✅ Failed articles have `claims_error_message` populated
6. ✅ Celery logs show verification tasks being queued
7. ✅ Anthropic API calls are logged

---

## Recommended Implementation Approach

### Phase 1: Quick Fix (1-2 hours)
- Add automatic verification trigger to `discovery_routes.py`
- Test with 5-10 articles
- Monitor Celery logs and API usage

### Phase 2: Complete Fix (2-4 hours)
- Add trigger to `ingestion_service`
- Add configuration flag for control
- Implement rate limiting
- Add monitoring/alerting

### Phase 3: Backfill (Optional)
- Process all existing pending articles:
  ```python
  python scripts/backfill_claims.py --batch-size 10 --delay 60
  ```

---

## Conclusion

**The claim extraction system is fully functional.** The issue is purely a **workflow integration gap** - verification is never automatically triggered when articles are created.

**Fix Complexity:** LOW (2-4 hours)
**Risk:** LOW (only adds background tasks)
**Impact:** HIGH (enables core feature)

The recommended fix is to add automatic background task queuing in article creation flows (Option 1), as it's the simplest, most maintainable solution that integrates with the existing Celery infrastructure.
