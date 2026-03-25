# Climate News Platform - REAL MVP Completion Plan

## Current State (2025-12-26)

### ✅ Working Infrastructure
- PostgreSQL database with 25 articles (all dummy data)
- 88 claims extracted
- 88 fact-checks created
- FastAPI backend (http://localhost:5200)
- Next.js frontend (http://localhost:5300)
- Admin pipeline endpoints functional

### ❌ Critical Gaps

1. **NO REAL DATA** - All articles are fake example.com URLs
2. **NO INGESTION WORKFLOW** - Can't add real climate news articles
3. **MARKDOWN RENDERING** - May have raw markdown showing
4. **MISSING UI** - URL analysis not visible to users
5. **NO END-TO-END TEST** - Never tested with real article

## Phase 1: Make It Real (Priority 1)

### Step 1: Create Article Ingestion Endpoint
- [ ] Backend endpoint to accept real URLs
- [ ] Scrape article content from URL
- [ ] Extract text and metadata
- [ ] Store in database

### Step 2: Add Real Climate News Articles
- [ ] Find 10-15 real climate news URLs
- [ ] Ingest them via API
- [ ] Verify they appear in UI
- [ ] Process claims/verification

### Step 3: Fix Frontend Display
- [ ] Fix markdown rendering (use proper React component)
- [ ] Show URL analysis prominently
- [ ] Add "Submit Article" button
- [ ] Display claim verification status clearly

### Step 4: End-to-End Test
- [ ] Submit a real climate article URL
- [ ] Wait for claim extraction (30 sec)
- [ ] Verify claims display
- [ ] Check fact-checking results
- [ ] Confirm scoring visible

## Phase 2: Polish (Priority 2)

- [ ] Search with real data
- [ ] Proper error messages
- [ ] Loading states
- [ ] Mobile responsive
- [ ] Rate limiting

## Success Criteria

MVP is complete when:
1. ✅ User can submit a real climate news URL
2. ✅ Article gets scraped and displayed
3. ✅ Claims are extracted automatically
4. ✅ Claims get fact-checked
5. ✅ Results visible in UI with proper markdown
6. ✅ Search works with real data
7. ✅ NO dummy data remains
8. ✅ All end-to-end workflows tested

## Estimated Time

- Real ingestion: 30 min
- Frontend fixes: 20 min
- Real data: 15 min
- Testing: 15 min

**Total: ~80 minutes to working MVP**
