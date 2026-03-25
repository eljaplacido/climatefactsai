<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# CliLens.AI - Priority Action Plan

**Generated:** November 10, 2025  
**Based On:** Comprehensive Code Review 2025  
**Status:** Ready for Execution

---

## 🎯 Quick Win Priorities (Do First)

### ✅ COMPLETED
- [x] Comprehensive code review
- [x] Architecture analysis
- [x] Created `.env.example` template
- [x] Created cleanup scripts (Bash + PowerShell)
- [x] Created test templates

### 🚀 NEXT STEPS (Start Immediately)

---

## Week 1: Critical Security Fixes (URGENT)

**Goal:** Fix security vulnerabilities before any deployment

### Day 1 (2-3 hours)

#### Task 1.1: Fix JWT Secret Key ⚠️ CRITICAL
**Priority:** 🔴 CRITICAL  
**File:** `api/auth_utils.py`

**Current Code (LINE 18):**
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
```

**Fix:**
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY environment variable is required. "
        "Generate with: openssl rand -hex 32"
    )
```

**Test:**
```bash
# Should fail without env var
python -c "from api.auth_utils import SECRET_KEY"

# Should work with env var
export JWT_SECRET_KEY=$(openssl rand -hex 32)
python -c "from api.auth_utils import SECRET_KEY; print('OK')"
```

---

#### Task 1.2: Create Production .env File
**Priority:** 🔴 CRITICAL

**Steps:**
```bash
# 1. Copy template
cp .env.example .env

# 2. Generate secrets
openssl rand -hex 32  # For JWT_SECRET_KEY
openssl rand -base64 32  # For POSTGRES_PASSWORD

# 3. Fill in API keys
# Edit .env and add your actual keys:
# - ANTHROPIC_API_KEY
# - OPENAI_API_KEY
# - PERPLEXITY_API_KEY
# - STRIPE_SECRET_KEY (test mode)
```

**Verify:**
```bash
# Check all required vars are set
grep -E "^[A-Z_]+=" .env | wc -l
# Should be > 20
```

---

#### Task 1.3: Update CORS Configuration
**Priority:** 🟡 HIGH  
**File:** `api/main.py`

**Current Code (LINES 133-139):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Fix:**
```python
# Allow origins from environment variable
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    max_age=600,  # Cache preflight requests for 10 minutes
)
```

**Add to .env:**
```bash
# Development
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Production (example)
CORS_ORIGINS=https://clilens.ai,https://www.clilens.ai
```

---

### Day 2 (3-4 hours)

#### Task 2.1: Enable Disabled API Features
**Priority:** 🔴 CRITICAL  
**File:** `api/main.py`

**Step 1: Add Missing Dependencies**
```bash
cd api
pip install stripe==11.1.1 reportlab==4.2.5 sendgrid==6.11.0
```

**Step 2: Update requirements.txt**
Add these lines to `api/requirements.txt`:
```txt
stripe==11.1.1
reportlab==4.2.5
sendgrid==6.11.0
```

**Step 3: Uncomment Routes (LINES 149-171)**
```python
# Current (commented out):
# from api.url_analysis_routes import router as url_analysis_router
# app.include_router(url_analysis_router)

# Fix: Uncomment these
from api.url_analysis_routes import router as url_analysis_router
app.include_router(url_analysis_router)

from api.search_routes import router as search_router
app.include_router(search_router)

from api.subscription_routes import router as subscription_router
app.include_router(subscription_router)
```

**Test All Endpoints:**
```bash
# Start API
cd api
uvicorn main:app --reload

# Test in another terminal
curl http://localhost:8000/health
curl http://localhost:8000/api/stats
curl http://localhost:8000/api/countries

# Check disabled endpoints now work
curl http://localhost:8000/docs
# Scroll through Swagger UI - should see URL Analysis, Search, Subscriptions
```

---

#### Task 2.2: Run Security Audit
**Priority:** 🟡 HIGH

```bash
# Install security tools
pip install safety bandit pip-audit

# 1. Check for known vulnerabilities
safety check -r requirements.txt
safety check -r api/requirements.txt

# 2. Scan code for security issues
bandit -r api/ -ll
bandit -r agents/ -ll

# 3. Audit dependencies
pip-audit -r requirements.txt

# Fix any HIGH or CRITICAL issues found
```

---

### Day 3-4 (6-8 hours)

#### Task 3.1: Execute Code Cleanup
**Priority:** 🟡 HIGH

**Step 1: Dry Run**
```bash
# Linux/Mac
./cleanup_script.sh --dry-run

# Windows PowerShell
.\cleanup_script.ps1 -WhatIf
```

**Step 2: Review Output**
- Check what will be deleted
- Verify no essential files in deletion list

**Step 3: Execute Cleanup**
```bash
# Linux/Mac
./cleanup_script.sh

# Windows PowerShell
.\cleanup_script.ps1
```

**Step 4: Commit Changes**
```bash
git status
git add .
git commit -m "chore: cleanup obsolete files and documentation

- Removed duplicate /agents/ directory
- Archived 20+ obsolete documentation files
- Deleted test/demo scripts
- Removed empty placeholder directories
- Deleted virtual environments (regenerate from requirements)

Estimated cleanup: ~500KB freed, 60+ files removed

See: COMPREHENSIVE_CODE_REVIEW_2025.md"
```

---

#### Task 3.2: Fix Import Paths
**Priority:** 🟡 HIGH

**Issue:** Multiple files use `sys.path.insert()` hacks

**Find all instances:**
```bash
grep -r "sys.path.insert" src/backend/services/
grep -r "sys.path.insert" api/
```

**Fix Pattern:**
```python
# BAD (current):
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
from shared.database import get_postgres

# GOOD (fix):
from src.backend.shared.database import get_postgres
```

**Test After Fix:**
```bash
# All services should still import correctly
cd src/backend/services/ingestion_service
python src/main.py --help
# Should not crash with import errors
```

---

### Day 5 (4-6 hours)

#### Task 5.1: Create Test Configuration
**Priority:** 🟡 HIGH

**File:** `pytest.ini` (create at root)
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Coverage
addopts =
    --verbose
    --tb=short
    --cov=api
    --cov=src/backend
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=60

# Test markers
markers =
    unit: Unit tests (fast)
    integration: Integration tests (requires DB)
    e2e: End-to-end tests (requires all services)
    slow: Slow tests

# Test environment
env =
    ENVIRONMENT=test
    LOG_LEVEL=DEBUG
```

**File:** `tests/conftest.py` (update)
```python
"""
Pytest configuration and shared fixtures
"""

import pytest
import os
from fastapi.testclient import TestClient

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-do-not-use-in-production"

from api.main import app

@pytest.fixture
def client():
    """Test client for API"""
    return TestClient(app)

@pytest.fixture
def test_db():
    """Test database connection"""
    # TODO: Set up test database
    # TODO: Run migrations
    # TODO: Seed with test data
    yield
    # TODO: Cleanup after test

@pytest.fixture
def auth_token(client):
    """Get valid auth token for tests"""
    response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "TestPass123!",
        "full_name": "Test User"
    })
    return response.json()["access_token"]

@pytest.fixture
def auth_headers(auth_token):
    """Get auth headers for requests"""
    return {"Authorization": f"Bearer {auth_token}"}
```

---

#### Task 5.2: Run Initial Test Suite
**Priority:** 🟡 HIGH

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-env

# Run tests
pytest tests/ -v

# Expected: ~30 tests should pass (existing + new)
# Current coverage: <5% → Target: 15-20% after this

# Generate HTML coverage report
pytest --cov-report=html
# Open htmlcov/index.html in browser
```

**Fix Failing Tests:**
- Database connection issues → use test DB
- Missing test data → add fixtures
- Import errors → fix paths

---

## Week 2: Test Coverage & Quality (IMPORTANT)

**Goal:** Increase test coverage from <5% to 60%+

### Day 1-2: API Endpoint Tests

**Target:** 50 tests covering authentication and articles

**Tasks:**
1. Complete `tests/api/test_auth_routes.py` (already created)
2. Complete `tests/api/test_article_routes.py` (already created)
3. Create `tests/api/test_admin_routes.py`
4. Create `tests/api/test_user_routes.py`

**Run After Each File:**
```bash
pytest tests/api/test_auth_routes.py -v
pytest tests/api/ -v
pytest --cov=api --cov-report=term-missing
```

---

### Day 3-4: Integration Tests

**Target:** 20 integration tests

**Create:**
- `tests/integration/test_database.py` - DB operations
- `tests/integration/test_kafka_messaging.py` - Message passing
- `tests/integration/test_workflow.py` - Full pipeline

**Example Test:**
```python
# tests/integration/test_workflow.py
def test_article_ingestion_to_publication():
    """Test complete workflow from discovery to publication"""
    # 1. Submit discovery task
    # 2. Wait for Kafka processing
    # 3. Verify article in database
    # 4. Check fact-checks created
    # 5. Verify article published
    pass
```

---

### Day 5: E2E Tests

**Target:** 10 E2E tests using Playwright

**Install:**
```bash
pip install playwright pytest-playwright
playwright install chromium
```

**Create:** `tests/e2e/test_user_flows.py`
```python
def test_user_registration_flow(page):
    """Test complete user registration"""
    page.goto("http://localhost:3000/register")
    page.fill("#email", "test@example.com")
    page.fill("#password", "SecurePass123!")
    page.click("button[type=submit]")
    page.wait_for_url("**/dashboard")
    assert "Dashboard" in page.content()
```

---

## Week 3: Documentation & Production Prep

### Day 1-2: Documentation Consolidation

**Tasks:**
1. Update `README.md` with accurate status
2. Update `docs/ARCHITECTURE.md` with hybrid pattern
3. Consolidate quick start guides
4. Create `docs/DEPLOYMENT.md`

**Checklist:**
- [ ] README reflects actual architecture
- [ ] All quick starts in one place
- [ ] Deployment guide complete
- [ ] API documentation generated

---

### Day 2-3: Docker Builds

**Fix Docker containers (currently failing)**

**Test Each Service:**
```bash
# Build ingestion service
docker build -f src/backend/services/ingestion_service/Dockerfile .

# Fix path issues in Dockerfile
# Update COPY commands
# Test service runs
docker run ingestion-service

# Repeat for all 5 services
```

---

### Day 4-5: Production Deployment

**Checklist:**
- [ ] All environment variables in `.env`
- [ ] Database migrations run
- [ ] Docker containers build successfully
- [ ] All 51 API endpoints functional
- [ ] Test coverage >60%
- [ ] Security audit passing
- [ ] Documentation up to date
- [ ] Monitoring configured (optional)

**Deploy to Staging:**
```bash
# Using Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# Test all endpoints
pytest tests/e2e/ --base-url=https://staging.clilens.ai
```

---

## 📊 Success Metrics

### Week 1 Targets
- ✅ Critical security fixes: 3/3
- ✅ Disabled features enabled: 20+ endpoints
- ✅ Code cleanup: 60+ files removed
- ✅ Test coverage: 5% → 20%

### Week 2 Targets
- ✅ Test coverage: 20% → 60%
- ✅ Tests passing: 100+
- ✅ Integration tests: 20+
- ✅ E2E tests: 10+

### Week 3 Targets
- ✅ Documentation consolidated
- ✅ Docker builds fixed
- ✅ Staging deployed
- ✅ Production ready

---

## 🚨 Blocker Resolution

### If Tests Fail
1. Check database connection
2. Verify environment variables
3. Check import paths
4. Review test logs

### If Docker Builds Fail
1. Check COPY paths in Dockerfile
2. Verify build context in docker-compose.yml
3. Check dependencies in requirements.txt
4. Review Docker logs

### If API Endpoints Fail
1. Check route imports in main.py
2. Verify dependencies installed
3. Check database schema
4. Review API logs

---

## 📞 Support Resources

**Documentation:**
- COMPREHENSIVE_CODE_REVIEW_2025.md - Full review
- RESTRUCTURING_PLAN_ANALYSIS.md - Architecture analysis
- README.md - Project overview
- docs/ARCHITECTURE.md - System design

**Quick Commands:**
```bash
# Start development
docker-compose up -d postgres redis kafka
cd api && uvicorn main:app --reload
cd frontend && npm run dev

# Run tests
pytest tests/ -v

# Check security
safety check && bandit -r api/

# Cleanup
./cleanup_script.sh --dry-run
```

---

## ✅ Daily Checklist Template

**Morning:**
- [ ] Pull latest changes: `git pull`
- [ ] Check task list above
- [ ] Review test failures from yesterday

**During Work:**
- [ ] Make incremental commits
- [ ] Run tests after each change
- [ ] Update documentation as you go

**End of Day:**
- [ ] Run full test suite
- [ ] Push changes: `git push`
- [ ] Update progress in this file

---

**Next Update:** After Week 1 completion  
**Progress Tracking:** Mark tasks complete as you finish them

**Good luck! 🚀**

