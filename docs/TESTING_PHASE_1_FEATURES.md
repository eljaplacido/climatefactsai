# Testing Phase 1 Features - CliLens.AI

**Platform Status:** ✅ Running and Healthy
**Last Updated:** 2025-12-26

---

## ✅ **Platform is Already Running!**

All 4 essential containers are up and healthy:

```bash
✅ clilens-api            - Up 2 hours (port 5200)
✅ clilens-frontend       - Up 2 hours (port 5300)
✅ climatenews-postgres   - Up 1 hour (port 5433)
✅ climatenews-redis      - Up 1 hour (port 5379)
```

**System Stats:**
- 25 articles in database
- 9 countries with data
- 22 fact-checks performed
- 4 verified claims

---

## 🧪 **Quick Health Check**

Run these commands to verify everything is working:

```bash
# Check all containers are running
docker ps

# API health check
curl http://localhost:5200/healthz
# Expected: {"status":"ok"}

# Database check
docker exec climatenews-postgres psql -U postgres -d climatenews -c "SELECT COUNT(*) FROM articles"
# Expected: 25 articles

# Redis check
docker exec climatenews-redis redis-cli PING
# Expected: PONG

# Frontend check (browser)
open http://localhost:5300
# Expected: Homepage loads
```

---

## 🎯 **Testing Phase 1 Features**

### **Feature 1: Claims Status Tracking**

**What Changed:**
- Articles now show claim processing status (pending/processing/completed/failed)
- No more confusing "high reliability + 0 claims" scenarios
- Clear error messages when claim extraction fails

**How to Test:**

#### **A. Via API**
```bash
# Get an article with claims status
curl -s "http://localhost:5200/api/v2/articles/3df2a603-fbf7-4d50-b09b-d2f1ff8dd30a" | python -m json.tool | grep -A 5 "claims_status"

# Expected fields:
# "claims_status": "completed" or "pending" or "failed"
# "claims_error_message": null (or error message if failed)
# "claims_processed_at": timestamp (if completed)
```

#### **B. Via Frontend**
1. Open http://localhost:5300
2. Click any article card
3. Look for claim status indicators:
   - ✅ "Claims assessed" (completed)
   - ⏳ "Analysis pending..." (pending)
   - ❌ "Analysis failed" (failed with reason)

**Expected Result:**
- Articles show **clear status** about claim processing
- No misleading scores (high reliability with 0 claims)
- Error messages when API keys missing or rate limited

---

### **Feature 2: Markdown Rendering**

**What Changed:**
- Article text now properly renders **bold**, *italic*, lists, etc.
- No more raw markdown symbols (`**bold**` → **bold**)
- Supports GitHub Flavored Markdown

**How to Test:**

#### **A. Via Frontend**
1. Open http://localhost:5300
2. Look at article excerpts on homepage
3. Click an article to view full detail
4. Check if formatting is rendered (not raw markdown)

**What to Look For:**
- **Bold text** appears bold (not `**bold**`)
- *Italic text* appears italic (not `*italic*`)
- Lists are properly formatted
- Links are clickable
- Headings are styled

**Test Article:**
```bash
# This article has rich formatting
curl -s "http://localhost:5200/api/v2/articles/3df2a603-fbf7-4d50-b09b-d2f1ff8dd30a"
```

**Expected Result:**
- All markdown is rendered as formatted HTML
- No raw `**` or `*` symbols visible to users
- Clean, readable article presentation

---

### **Feature 3: Search Functionality**

**What Changed:**
- Full-text search across article titles and excerpts
- Autocomplete suggestions (tags, countries, sources)
- Keyboard navigation (arrow keys, enter, escape)
- Category filters (all/tag/country/source)

**How to Test:**

#### **A. Search Suggestions API**
```bash
# Search for "climate"
curl -s "http://localhost:5200/api/search/suggestions?q=climate" | python -m json.tool

# Expected: JSON array of suggestions
# [
#   {"text": "climate", "category": "tag", "count": 15},
#   {"text": "climate-finance", "category": "tag", "count": 2},
#   {"text": "Nature Climate Change", "category": "source", "count": 1}
# ]
```

#### **B. Article Search API**
```bash
# Search articles
curl -s "http://localhost:5200/api/articles?search=climate&limit=3" | python -m json.tool | head -40

# Expected: Articles matching "climate" in title or excerpt
```

#### **C. Frontend Interactive Search**
1. Open http://localhost:5300/search
2. Type "climate" in search box
3. **Watch autocomplete dropdown appear**
4. Use **arrow keys** to navigate suggestions
5. Press **Enter** to select
6. Try category filters: All / Tag / Country / Source
7. Apply filters: Country selector, Credibility, Tags

**Expected Result:**
- Suggestions appear as you type (debounced 300ms)
- Arrow keys navigate, Enter selects, Escape closes
- Filters work (country, credibility, tags)
- Results update in real-time
- No "search unavailable" errors

---

### **Feature 4: User URL Analysis (Premium Feature)**

**What Changed:**
- Users can submit custom URLs for fact-checking
- Background processing with status tracking
- Security: HTTPS only, no localhost/private IPs
- Rate limiting by subscription tier

**How to Test:**

#### **A. Check if Endpoint is Available**
```bash
# This will fail without authentication (expected)
curl -X POST http://localhost:5200/api/analyze-url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/climate-article"}'

# Expected: 401 Unauthorized (need JWT token)
```

#### **B. Test with Authentication** (if you have credentials)

**Step 1: Login**
```bash
# Register a test user
curl -X POST http://localhost:5200/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!",
    "full_name": "Test User"
  }'

# Login
curl -X POST http://localhost:5200/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!"
  }'

# Save the access_token from response
```

**Step 2: Submit URL for Analysis**
```bash
# Replace YOUR_TOKEN with the access_token from login
curl -X POST http://localhost:5200/api/analyze-url \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"url": "https://www.bbc.com/news/science-environment"}'

# Expected response:
# {
#   "job_id": "uuid-here",
#   "status": "processing",
#   "estimated_time": 30
# }
```

**Step 3: Check Analysis Status**
```bash
# Replace JOB_ID with the job_id from previous response
curl -X GET "http://localhost:5200/api/analyze-url/JOB_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Expected: Analysis details with status, claims, credibility
```

**Step 4: Check Usage Stats**
```bash
curl -X GET "http://localhost:5200/api/analyze-url/stats/usage" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Expected:
# {
#   "tier": "freemium",
#   "limit": 0,
#   "used": 0,
#   "remaining": 0,
#   "period": "monthly"
# }
```

#### **C. Frontend Testing** (when logged in)

1. Open http://localhost:5300
2. Login/Register
3. Look for "Analyze URL" or similar feature
4. Submit a URL for analysis
5. Watch processing status
6. View results when complete

**Expected Result:**
- URL validation works (HTTPS only)
- Background processing (30 seconds typical)
- Claims extracted and displayed
- Rate limiting enforced by tier
- Clear error messages for invalid URLs

**Security Features Tested:**
- ❌ HTTP URLs rejected (HTTPS only)
- ❌ localhost/127.0.0.1 rejected
- ❌ Private IPs (192.168.x.x, 10.x.x.x) rejected
- ✅ Valid HTTPS URLs accepted
- ✅ Content size limit (100KB)
- ✅ Fetch timeout (10 seconds)

---

### **Feature 5: No Mock Data Fallbacks**

**What Changed:**
- Removed silent fallback to fake claims
- Explicit HTTP errors when API unavailable
- Clear error messages for users

**How to Test:**

#### **A. Test with Missing API Key**

**Step 1: Check Current API Key**
```bash
# Check if ANTHROPIC_API_KEY is set
docker exec clilens-api printenv ANTHROPIC_API_KEY
```

**Step 2: Trigger Claim Extraction** (requires authenticated request)
```bash
# This would trigger claim extraction if API key is valid
# With no API key, should return HTTP 503 with clear message
# (Requires admin access to trigger)
```

**Expected Error Messages:**
- HTTP 503: "Claim extraction unavailable: Anthropic API key not configured"
- HTTP 429: "Rate limit reached. Try again later."
- HTTP 503: "Anthropic API temporarily unavailable"

**Expected Result:**
- **NO fake/mock claims** appear
- Clear error messages explain why claims unavailable
- Articles show `claims_status: "failed"` with error message
- Users understand what went wrong

---

## 🌐 **Browser Testing Checklist**

### **Homepage (http://localhost:5300)**

```
✅ Page loads without errors
✅ Article cards display correctly
✅ Credibility badges show (High/Medium/Low)
✅ Markdown is rendered (no raw ** symbols)
✅ Article excerpts are readable
✅ Tags are displayed
✅ Filters work (country, credibility)
✅ Search box is functional
✅ No "undefined" or "null" in UI
✅ Mobile responsive (resize window to 375px)
```

### **Search Page (http://localhost:5300/search)**

```
✅ Search input works
✅ Autocomplete suggestions appear
✅ Arrow keys navigate suggestions
✅ Enter selects suggestion
✅ Escape closes dropdown
✅ Category filters work (all/tag/country/source)
✅ Country selector works
✅ Credibility filter works
✅ Tag filters work (clickable chips)
✅ Results update in real-time
✅ No "search unavailable" errors
```

### **Article Detail Page**

```
✅ Click article card opens detail page
✅ Full article title displayed
✅ Source name and date shown
✅ Reliability score displayed
✅ Claims count shown
✅ Markdown content rendered properly
✅ Claim status visible (pending/processing/completed/failed)
✅ Fact-check badges displayed
✅ Evidence sources listed
✅ "View original article" link works
✅ Back button returns to search/home
```

---

## 🔧 **Troubleshooting**

### **Problem: API not responding**

```bash
# Check if API container is running
docker ps | grep clilens-api

# Check API logs
docker logs clilens-api --tail 50

# Restart API
docker restart clilens-api
```

### **Problem: Frontend shows blank page**

```bash
# Check frontend logs
docker logs clilens-frontend --tail 50

# Verify API_URL is correct
docker exec clilens-frontend printenv NEXT_PUBLIC_API_URL
# Should be: http://localhost:5200

# Restart frontend
docker restart clilens-frontend
```

### **Problem: Database connection errors**

```bash
# Check database is running
docker ps | grep climatenews-postgres

# Test connection
docker exec climatenews-postgres psql -U postgres -d climatenews -c "SELECT 1"

# Check logs
docker logs climatenews-postgres --tail 50
```

### **Problem: Search not working**

```bash
# Test search endpoint directly
curl -s "http://localhost:5200/api/search/suggestions?q=test"

# Check if articles have searchable content
docker exec climatenews-postgres psql -U postgres -d climatenews \
  -c "SELECT COUNT(*) FROM articles WHERE title IS NOT NULL"
```

---

## 📊 **Performance Testing**

### **API Response Times**

```bash
# Health check (should be < 50ms)
time curl -s http://localhost:5200/healthz

# Articles list (should be < 200ms)
time curl -s "http://localhost:5200/api/articles?limit=10"

# Article detail (should be < 300ms)
time curl -s "http://localhost:5200/api/v2/articles/3df2a603-fbf7-4d50-b09b-d2f1ff8dd30a"

# Search (should be < 500ms)
time curl -s "http://localhost:5200/api/articles?search=climate&limit=20"
```

### **Database Query Performance**

```bash
# Check article count query speed
docker exec climatenews-postgres psql -U postgres -d climatenews \
  -c "EXPLAIN ANALYZE SELECT * FROM articles LIMIT 10"
```

---

## ✅ **Success Criteria**

**All Phase 1 features pass if:**

- ✅ Claims status is visible and accurate (pending/processing/completed/failed)
- ✅ Markdown renders properly (no raw `**` symbols)
- ✅ Search works (suggestions + full-text search)
- ✅ URL analysis endpoint exists and is secured
- ✅ No mock data appears anywhere
- ✅ Clear error messages for all failure cases
- ✅ All API endpoints return expected responses
- ✅ Frontend loads without errors
- ✅ All 4 containers are healthy
- ✅ No crash loops or restarts

---

## 📝 **Test Results Template**

Copy and fill this out after testing:

```markdown
# Phase 1 Testing Results

**Date:** ___________
**Tester:** ___________

## Platform Status
- [ ] All 4 containers running
- [ ] API health check passes
- [ ] Frontend loads
- [ ] Database connected
- [ ] Redis connected

## Feature Tests
- [ ] Claims status tracking works
- [ ] Markdown rendering works
- [ ] Search functionality works
- [ ] URL analysis endpoint exists
- [ ] No mock data found
- [ ] Error messages are clear

## Browser Tests
- [ ] Homepage loads correctly
- [ ] Search page works
- [ ] Article detail page works
- [ ] Filters work (country, credibility, tags)
- [ ] Mobile responsive

## Performance
- [ ] API responses < 500ms
- [ ] Frontend initial load < 3s
- [ ] No errors in browser console
- [ ] No errors in API logs

## Issues Found
(List any issues here)

## Notes
(Additional observations)
```

---

## 🚀 **Next Steps After Testing**

1. **If all tests pass:** Move to Phase 2 (Celery workers)
2. **If issues found:** Document in GitHub issues
3. **Performance issues:** Check logs and optimize queries
4. **Feature requests:** Add to backlog

---

**Happy Testing! 🎉**

For questions or issues:
- Check logs: `docker logs clilens-api`
- Review documentation: `docs/CURRENT_STATE.md`
- Container guide: `docs/DOCKER_SETUP.md`
