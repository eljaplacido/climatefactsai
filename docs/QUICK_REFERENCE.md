# CliLens.AI - Quick Reference Card

**Essential commands and file locations for immediate action**

---

## 🚨 CRITICAL: First 3 Things to Do

### 1. Fix JWT Secret (2 minutes)
```bash
# Generate secure key
openssl rand -hex 32

# Add to .env file
echo "JWT_SECRET_KEY=<paste-generated-key-here>" >> .env
```

**File to edit:** `api/auth_utils.py` line 18
```python
# Remove the default value:
SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # No default!
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY required")
```

---

### 2. Enable Disabled Features (5 minutes)
```bash
# Install missing dependencies
pip install stripe reportlab sendgrid

# Edit api/main.py lines 149-159
# Uncomment these 6 lines:
from api.url_analysis_routes import router as url_analysis_router
app.include_router(url_analysis_router)

from api.search_routes import router as search_router
app.include_router(search_router)

from api.subscription_routes import router as subscription_router
app.include_router(subscription_router)
```

---

### 3. Create .env File (10 minutes)
```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

**Minimum required:**
- JWT_SECRET_KEY (generate with openssl)
- ANTHROPIC_API_KEY
- PERPLEXITY_API_KEY
- POSTGRES_PASSWORD

---

## 📁 File Locations

### Documentation (Read These)
| File | Purpose |
|------|---------|
| `COMPREHENSIVE_CODE_REVIEW_2025.md` | Full security & code review |
| `RESTRUCTURING_PLAN_ANALYSIS.md` | Architecture analysis |
| `PRIORITY_ACTION_PLAN.md` | Week-by-week tasks |
| `QUICK_REFERENCE.md` | This file - quick commands |
| `README.md` | Project overview |

### Configuration Files (Edit These)
| File | What to Change |
|------|----------------|
| `.env` | All API keys and secrets |
| `api/main.py` | Uncomment lines 149-159 |
| `api/auth_utils.py` | Remove default JWT secret |
| `api/requirements.txt` | Add: stripe, reportlab, sendgrid |

### Scripts (Run These)
| File | Purpose |
|------|---------|
| `cleanup_script.sh` | Delete obsolete files (Linux/Mac) |
| `cleanup_script.ps1` | Delete obsolete files (Windows) |
| `.env.example` | Template for environment variables |

### Tests (Create/Run These)
| File | Status |
|------|--------|
| `tests/api/test_auth_routes.py` | ✅ Created - ready to run |
| `tests/api/test_article_routes.py` | ✅ Created - ready to run |
| `tests/conftest.py` | ⚠️ Needs update |
| `pytest.ini` | ❌ Need to create |

---

## ⚡ Quick Commands

### Start Development Environment
```bash
# 1. Infrastructure
docker-compose up -d postgres redis kafka zookeeper

# 2. Backend API (in new terminal)
cd api
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload

# 3. Frontend (in new terminal)
cd frontend
npm install
npm run dev

# Access:
# API: http://localhost:8000
# Swagger: http://localhost:8000/docs
# Frontend: http://localhost:3000
```

---

### Run Tests
```bash
# Install test tools
pip install pytest pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=api --cov-report=html

# Run specific test file
pytest tests/api/test_auth_routes.py -v

# Open coverage report
open htmlcov/index.html  # Mac
start htmlcov/index.html  # Windows
```

---

### Code Cleanup
```bash
# IMPORTANT: Dry run first to see what will be deleted
# Linux/Mac:
./cleanup_script.sh --dry-run

# Windows PowerShell:
.\cleanup_script.ps1 -WhatIf

# If output looks good, execute:
# Linux/Mac:
./cleanup_script.sh

# Windows PowerShell:
.\cleanup_script.ps1
```

---

### Security Checks
```bash
# Install security tools
pip install safety bandit pip-audit

# Check for vulnerabilities
safety check -r requirements.txt

# Scan code for security issues
bandit -r api/ -ll

# Audit dependencies
pip-audit -r requirements.txt
```

---

### Database Operations
```bash
# Connect to PostgreSQL
docker exec -it climatenews-postgres psql -U postgres -d climatenews

# Common queries:
# List all tables
\dt

# Count articles
SELECT COUNT(*) FROM articles;

# Check countries
SELECT country_code, country_name, articles_count FROM countries;

# Exit
\q
```

---

### Docker Operations
```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f api

# Restart service
docker-compose restart api

# Rebuild service
docker-compose build api
docker-compose up -d api

# Stop all
docker-compose down

# Stop and remove volumes (DANGER - deletes data)
docker-compose down -v
```

---

## 🔍 Troubleshooting

### API Won't Start
```bash
# Check if port is in use
netstat -ano | findstr :8000  # Windows
lsof -i :8000  # Linux/Mac

# Check environment variables
python -c "import os; print(os.getenv('JWT_SECRET_KEY'))"

# Check dependencies
pip list | grep stripe
```

### Tests Failing
```bash
# Check test database connection
pytest tests/ -v -s  # Show print statements

# Run single test for debugging
pytest tests/api/test_auth_routes.py::TestUserRegistration::test_register_user_success -v
```

### Docker Build Fails
```bash
# Check Docker is running
docker ps

# Clean Docker cache
docker system prune -a

# Rebuild from scratch
docker-compose build --no-cache
```

### Frontend Build Fails
```bash
# Clear node_modules
rm -rf node_modules package-lock.json
npm install

# Check Node version
node -v  # Should be 18+

# Try different package manager
npm install  # or yarn install
```

---

## 📊 Current Status Summary

### ✅ What Works
- ✅ Database schema (excellent design)
- ✅ 28 API endpoints functional
- ✅ Frontend (Vite + React)
- ✅ Authentication system
- ✅ Docker infrastructure

### ⚠️ What Needs Fixing
- 🔴 Default JWT secret (CRITICAL)
- 🔴 20+ endpoints disabled (missing deps)
- 🔴 Test coverage <5%
- 🟡 Duplicate code (500KB)
- 🟡 60+ obsolete docs

### 📈 Progress Tracking
- [ ] Week 1: Security fixes
- [ ] Week 2: Test coverage
- [ ] Week 3: Production prep

---

## 🎯 Today's Priorities

**If you have 30 minutes:**
1. Fix JWT secret
2. Create .env file
3. Run cleanup script (dry run)

**If you have 2 hours:**
1. All of the above
2. Enable disabled features
3. Run test suite
4. Fix failing tests

**If you have 1 day:**
1. All of the above
2. Complete Week 1 tasks from PRIORITY_ACTION_PLAN.md
3. Write 20 new tests
4. Run security audit

---

## 📞 Get Help

**Files to check:**
1. `COMPREHENSIVE_CODE_REVIEW_2025.md` - Detailed analysis
2. `PRIORITY_ACTION_PLAN.md` - Step-by-step tasks
3. `RESTRUCTURING_PLAN_ANALYSIS.md` - Architecture info
4. This file - Quick reference

**Common issues documented in review:**
- Security vulnerabilities → Section "Critical Issues"
- Missing tests → Section "Testing & Quality Assurance"
- Duplicate files → Section "Code Quality & Architecture"
- Documentation conflicts → Section "Documentation Issues"

---

## 🚀 Success Checklist

**Ready for Production when:**
- [ ] All security fixes applied
- [ ] Test coverage >60%
- [ ] All 51 endpoints working
- [ ] Docker builds successful
- [ ] Documentation accurate
- [ ] .env configured for production
- [ ] Staging environment tested

**Current Status:** ⚠️ NOT READY (but fixable in 2-3 weeks)

---

**Last Updated:** November 10, 2025  
**Version:** 1.0  
**Next Review:** After Week 1 completion

