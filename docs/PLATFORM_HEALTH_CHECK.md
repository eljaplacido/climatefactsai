# CliLens.AI Platform Health Check

**Last Updated:** 2025-12-22
**Purpose:** Verify all platform components are operational

---

## ⚡ Quick Health Check (2 minutes)

### 1. Start Docker Desktop

**Windows:**
```powershell
# Open Docker Desktop from Start Menu
# Wait for "Docker Desktop is running" notification
```

**Verify Docker is ready:**
```bash
docker --version
# Expected: Docker version 20.10.x or higher

docker ps
# Expected: 4 running containers or "no containers" if not started
```

---

### 2. Start All Containers

```bash
cd C:\Users\35845\Desktop\DIGICISU\climatenews

# Start infrastructure first
docker-compose up -d postgres redis

# Wait 10 seconds for databases to initialize
timeout /t 10

# Start application services
docker-compose up -d api frontend
```

**Expected Output:**
```
Creating climatenews-postgres ... done
Creating climatenews-redis    ... done
Creating clilens-api          ... done
Creating clilens-frontend     ... done
```

---

### 3. Container Status Check

```bash
docker ps
```

**✅ Success Criteria:**
```
CONTAINER ID   IMAGE              STATUS         PORTS
xxxxx          clilens-frontend   Up X minutes   0.0.0.0:5300->3000/tcp
xxxxx          clilens-api        Up X minutes   0.0.0.0:5200->8000/tcp
xxxxx          postgres:16        Up X minutes   0.0.0.0:5433->5432/tcp
xxxxx          redis:7            Up X minutes   0.0.0.0:5379->6379/tcp
```

**❌ Troubleshooting:**

If a container shows "Exited" or "Restarting":
```bash
# Check logs for the failing container
docker logs clilens-api --tail 50
docker logs clilens-frontend --tail 50

# Common issues:
# - API: Missing ANTHROPIC_API_KEY in .env
# - Frontend: Missing NEXT_PUBLIC_API_URL in .env
# - Postgres: Port 5433 already in use
# - Redis: Port 5379 already in use
```

---

### 4. API Health Check

```bash
# Test health endpoint
curl http://localhost:5200/healthz
```

**✅ Expected Response:**
```json
{"status":"ok"}
```

**Test articles endpoint:**
```bash
curl http://localhost:5200/api/articles?limit=3
```

**✅ Expected:** JSON array with articles (may be empty if no data loaded)
**❌ If fails:** Check `docker logs clilens-api`

---

### 5. Database Connectivity Check

```bash
# Windows (PowerShell)
docker exec -it climatenews-postgres psql -U postgres -d climatenews -c "SELECT count(*) FROM articles;"
```

**✅ Expected:**
```
 count
-------
     X
(1 row)
```

**Check database schema:**
```bash
docker exec -it climatenews-postgres psql -U postgres -d climatenews -c "\dt"
```

**✅ Expected tables:**
- articles
- claims
- fact_checks
- countries
- publishers
- users
- subscriptions
- api_keys
- article_feedback
- workflow_logs

---

### 6. Frontend Accessibility Check

**Open in browser:**
```
http://localhost:5300
```

**✅ Success Criteria:**
- Homepage loads without errors
- No console errors in browser DevTools (F12)
- Can see navigation bar and layout
- If articles exist, they display correctly

**❌ Common Issues:**
- **White screen:** Check browser console (F12) for JavaScript errors
- **"API Error":** API not running or wrong URL in NEXT_PUBLIC_API_URL
- **Articles not showing:** Database empty (need to load sample data)

---

### 7. API Documentation Check

**Open in browser:**
```
http://localhost:5200/docs
```

**✅ Expected:** Swagger UI with all API endpoints listed

**Key endpoints to verify:**
- `GET /api/articles` - List articles
- `GET /api/articles/{id}` - Article detail
- `POST /api/auth/login` - User login
- `GET /api/countries` - List countries
- `GET /healthz` - Health check

---

## 🚨 Known Issues to Watch For

### Issue 1: High Reliability Score + 0 Claims

**Symptom:**
```json
{
  "reliability_score": 85,
  "claims_count": 0,
  "claims_status": "pending"
}
```

**Expected Behavior:** Frontend should show "Pending analysis" badge
**Status:** Fixed in Phase 1 (claims_status field added)

---

### Issue 2: Markdown Not Rendered

**Symptom:** Article text shows `**bold**` instead of **bold** formatting

**Status:** ⏸️ Fix in progress (agent afaea77, resumes 1pm Helsinki)

**Temporary Workaround:** Ignore formatting for now

---

### Issue 3: Search Unavailable

**Symptom:** Search returns "Service unavailable" error

**Status:** ⏸️ Investigation in progress (agent a7f56b7)

**Temporary Workaround:** Use filters instead of search

---

### Issue 4: Empty Country Results

**Symptom:** Selecting countries other than Finland shows no articles

**Cause:** Limited test data (only Finland populated)

**Status:** Expected behavior until EU expansion (Phase 3)

---

### Issue 5: Kafka Workers Crash

**Symptom:** `docker logs` shows errors from orchestration/ingestion/verification services

**Cause:** Kafka infrastructure not operational (architecture decision pending)

**Status:** ❌ Known limitation - services will crash, this is expected

**Impact:** No automated article ingestion or background processing

---

## 📊 Full System Test (15 minutes)

### Test 1: View Articles

**Steps:**
1. Navigate to http://localhost:5300
2. Verify article cards display
3. Click on an article
4. Verify article detail page loads with claims

**✅ Pass Criteria:**
- Articles visible on homepage
- Article detail page shows full content
- Claims section visible (even if empty)
- No JavaScript errors in console

---

### Test 2: Filter Articles

**Steps:**
1. On homepage, select a country filter
2. Change credibility filter
3. Change date range

**✅ Pass Criteria:**
- Filters update URL query parameters
- Article list updates based on filters
- Empty state shows when no matches

---

### Test 3: Search Functionality

**Steps:**
1. Type in search box
2. Check if suggestions appear
3. Submit search

**✅ Pass Criteria:**
- Search suggestions work
- Search results display (or clear error if search broken)

**⚠️ Known Issue:** Full-text search may return errors (investigation in progress)

---

### Test 4: User Registration/Login

**Steps:**
1. Navigate to http://localhost:5300/auth/register
2. Create test account
3. Login with credentials

**✅ Pass Criteria:**
- Registration succeeds
- Login returns JWT token
- Protected routes accessible after login

**Test API directly:**
```bash
# Register
curl -X POST http://localhost:5200/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123","full_name":"Test User"}'

# Login
curl -X POST http://localhost:5200/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'
```

---

### Test 5: Admin Dashboard

**Steps:**
1. Navigate to http://localhost:5300/admin
2. Click "Discover News" (if PERPLEXITY_API_KEY set)
3. Check workflow logs

**✅ Pass Criteria:**
- Admin page loads
- Stats display correctly
- Trigger buttons visible

**⚠️ Note:** Discovery requires PERPLEXITY_API_KEY in .env

---

## 🔐 Environment Check

### Required for Basic Functionality

```bash
# Check .env file exists
cat .env | findstr "DATABASE_URL REDIS_URL JWT_SECRET_KEY"
```

**✅ Must have:**
- `DATABASE_URL` (auto-configured by Docker)
- `REDIS_URL` (auto-configured by Docker)
- `JWT_SECRET_KEY` (for authentication)

---

### Required for Advanced Features

```bash
cat .env | findstr "ANTHROPIC_API_KEY PERPLEXITY_API_KEY"
```

**Optional but recommended:**
- `ANTHROPIC_API_KEY` - For claim extraction (without it, claims won't be analyzed)
- `PERPLEXITY_API_KEY` - For news discovery (optional)

---

## 🧹 Clean Restart (If Things Are Broken)

```bash
# Stop all containers
docker-compose down

# Remove volumes (WARNING: Deletes all data)
docker-compose down -v

# Restart from scratch
docker-compose up -d postgres redis
timeout /t 10
docker-compose up -d api frontend

# Check logs
docker-compose logs -f
```

---

## 📈 Performance Checks

### API Response Time

```bash
# Test API latency
curl -w "@-" -o /dev/null -s http://localhost:5200/api/articles <<'EOF'
   time_namelookup:  %{time_namelookup}s\n
      time_connect:  %{time_connect}s\n
   time_appconnect:  %{time_appconnect}s\n
  time_pretransfer:  %{time_pretransfer}s\n
     time_redirect:  %{time_redirect}s\n
time_starttransfer:  %{time_starttransfer}s\n
                   ----------\n
        time_total:  %{time_total}s\n
EOF
```

**✅ Target:** Total time < 200ms for simple queries

---

### Database Query Performance

```bash
docker exec -it climatenews-postgres psql -U postgres -d climatenews
```

```sql
-- Check article count
SELECT count(*) FROM articles;

-- Check query performance
EXPLAIN ANALYZE SELECT * FROM articles WHERE country_code = 'FI' LIMIT 10;

-- Check index usage
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE tablename IN ('articles', 'claims', 'fact_checks');
```

---

## ✅ Health Check Summary

**Quick Checklist:**

- [ ] Docker Desktop running
- [ ] All 4 containers running (postgres, redis, api, frontend)
- [ ] API health check returns `{"status":"ok"}`
- [ ] Database accessible (`SELECT count(*) FROM articles` works)
- [ ] Frontend loads at http://localhost:5300
- [ ] API docs accessible at http://localhost:5200/docs
- [ ] No critical errors in logs
- [ ] Articles display in UI (if data loaded)

**If all checked:** ✅ Platform is healthy!

**If issues found:** Check logs and reference "Known Issues" section above.

---

## 🆘 Troubleshooting Quick Reference

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| `docker ps` fails | Docker not running | Start Docker Desktop |
| API container exits | Missing env vars | Check `.env` file, add required keys |
| Frontend white screen | API not reachable | Check `NEXT_PUBLIC_API_URL` in `.env` |
| Database connection failed | Port conflict | Change `5433` to another port in `docker-compose.yml` |
| No articles showing | Empty database | Run sample data script |
| Search unavailable | Known bug | Use filters instead (fix in progress) |
| Kafka errors in logs | Expected | Kafka not operational (ignore for now) |

---

**Created:** 2025-12-22
**Purpose:** Platform health verification and troubleshooting guide
**Audience:** Developers, testers, AI agents

**Next Steps After Verification:**
1. If healthy → Proceed with development tasks
2. If issues → Use troubleshooting section
3. Update CURRENT_STATE.md if major changes made
