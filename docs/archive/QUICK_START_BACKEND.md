<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# 🚀 CliLens.AI Backend - Quick Start Guide

**Last Updated:** 2025-10-31
**Version:** 2.0.0

---

## 📋 Prerequisites

- **Docker Desktop** installed and running
- **Python 3.11+** (for local development)
- **Node.js 18+** (for frontend)
- **Git** for version control

### Required API Keys
- Anthropic API key (Claude)
- OpenAI API key (GPT-4)
- Perplexity API key
- Stripe test API keys (get free at stripe.com)

---

## ⚡ Quick Start (5 minutes)

### 1. Clone and Setup
```bash
cd C:\Users\35845\Desktop\DIGICISU\climatenews

# Copy environment template
copy .env.example .env

# Edit .env with your API keys (minimum required):
# - ANTHROPIC_API_KEY
# - OPENAI_API_KEY
# - PERPLEXITY_API_KEY
# - JWT_SECRET_KEY (generate: python -c "import secrets; print(secrets.token_urlsafe(32))")
# - STRIPE_SECRET_KEY (test mode)
```

### 2. Start Infrastructure
```bash
# Start PostgreSQL, Redis, Kafka
docker-compose up -d postgres redis kafka zookeeper
```

### 3. Install Dependencies
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt
```

### 4. Initialize Database
```bash
# Apply database schemas
psql -h localhost -p 5433 -U postgres -d climatenews -f infrastructure/database/01_schema.sql
psql -h localhost -p 5433 -U postgres -d climatenews -f infrastructure/database/02_indexes_and_constraints.sql
psql -h localhost -p 5433 -U postgres -d climatenews -f infrastructure/database/03_users_and_subscriptions.sql
```

### 5. Start API Server
```bash
cd api
uvicorn main:app --reload --port 8000
```

### 6. Verify Installation
```bash
# Check API health
curl http://localhost:8000/health

# View API documentation
start http://localhost:8000/docs
```

---

## 🧪 Test the New Features

### Test 1: User Registration & Login
```bash
# Register a new user
curl -X POST http://localhost:8000/api/auth/register ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"test@example.com\",\"password\":\"TestPass123!\",\"full_name\":\"Test User\"}"

# Login
curl -X POST http://localhost:8000/api/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"test@example.com\",\"password\":\"TestPass123!\"}"

# Copy the "access_token" from response
```

### Test 2: Get User Profile
```bash
# Replace YOUR_TOKEN with token from login
curl -X GET http://localhost:8000/api/auth/me ^
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test 3: View Dashboard
```bash
curl -X GET http://localhost:8000/api/user/dashboard ^
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test 4: URL Analysis (Upgrade to Basic tier first)
```bash
# First, manually upgrade user in database:
psql -h localhost -p 5433 -U postgres -d climatenews -c "UPDATE users SET subscription_tier = 'basic' WHERE email = 'test@example.com';"

# Submit URL for analysis
curl -X POST http://localhost:8000/api/analyze-url ^
  -H "Authorization: Bearer YOUR_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://www.reuters.com/climate-article\",\"priority\":\"normal\"}"

# Check analysis status (use ID from response)
curl -X GET http://localhost:8000/api/analyze-url/ANALYSIS_ID ^
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test 5: Search
```bash
# Basic search (all users)
curl -X GET "http://localhost:8000/api/articles?limit=5"

# Get search suggestions
curl -X GET "http://localhost:8000/api/search/suggestions?q=climate"
```

### Test 6: Create API Key (Professional tier)
```bash
# Upgrade to professional tier
psql -h localhost -p 5433 -U postgres -d climatenews -c "UPDATE users SET subscription_tier = 'professional' WHERE email = 'test@example.com';"

# Create API key
curl -X POST http://localhost:8000/api/api-keys ^
  -H "Authorization: Bearer YOUR_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"My First API Key\",\"scopes\":[\"read\",\"write\"]}"

# Save the api_key from response (shown only once!)
```

### Test 7: Use API Key
```bash
# List articles using API key (replace YOUR_API_KEY)
curl -X GET http://localhost:8000/api/articles ^
  -H "X-API-Key: YOUR_API_KEY"
```

### Test 8: Export Article to PDF
```bash
# Get article ID from articles list
curl -X GET http://localhost:8000/api/articles?limit=1

# Export to PDF (replace ARTICLE_ID)
curl -X POST http://localhost:8000/api/export/article/ARTICLE_ID/pdf ^
  -H "Authorization: Bearer YOUR_TOKEN" ^
  --output article.pdf
```

---

## 🔧 Configuration

### Minimum Required Environment Variables
```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/climatenews

# LLM APIs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...

# Authentication
JWT_SECRET_KEY=your-generated-secret-key

# Stripe (test mode)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
```

### Optional Configuration
```bash
# Frontend URL
FRONTEND_URL=http://localhost:3000

# Email (SendGrid) - for password reset
SENDGRID_API_KEY=SG...
FROM_EMAIL=noreply@clilens.ai

# Feature Flags
ENABLE_SEMANTIC_SEARCH=True
ENABLE_API_KEYS=True
ENABLE_EXPORT=True
```

---

## 📊 API Endpoints Overview

### Authentication (`/api/auth/*`)
- `POST /register` - Create account
- `POST /login` - Get JWT token
- `POST /refresh` - Refresh token
- `GET /me` - Get profile
- `PUT /me` - Update profile
- `POST /change-password` - Change password
- `POST /forgot-password` - Request reset
- `POST /reset-password` - Reset password
- `POST /verify-email` - Verify email

### URL Analysis (`/api/analyze-url/*`) 🔒 Basic+
- `POST /` - Submit URL
- `GET /{id}` - Get results
- `GET /` - History
- `DELETE /{id}` - Delete
- `GET /stats/usage` - Usage stats

### Search (`/api/search/*`)
- `POST /semantic` - Semantic search 🔒 Professional+
- `POST /save` - Save search 🔒 Basic+
- `GET /saved` - List saved 🔒 Basic+
- `DELETE /saved/{id}` - Delete saved 🔒 Basic+
- `GET /suggestions` - Auto-complete
- `GET /history` - Search history 🔒

### Subscriptions (`/api/subscription/*`) 🔒
- `GET /current` - Current plan
- `POST /create` - Start subscription
- `PUT /upgrade` - Change tier
- `DELETE /cancel` - Cancel
- `GET /history` - Payments
- `POST /webhooks/stripe` - Stripe events

### User Dashboard (`/api/user/*`) 🔒
- `GET /preferences` - Get settings
- `PUT /preferences` - Update settings
- `GET /usage` - Usage stats
- `GET /notifications` - Notifications
- `POST /notifications/{id}/read` - Mark read
- `GET /activity` - Activity log
- `GET /dashboard` - Full summary

### API Keys (`/api/api-keys/*`) 🔒 Professional+
- `POST /` - Create key
- `GET /` - List keys
- `GET /{id}/usage` - Key stats
- `DELETE /{id}` - Revoke key
- `PUT /{id}/rename` - Rename key

### Export (`/api/export/*`) 🔒 Professional+
- `POST /article/{id}/pdf` - PDF export
- `POST /search/csv` - CSV export
- `GET /history` - Export history

### Articles (`/api/articles/*`)
- `GET /` - List articles
- `GET /{id}` - Article detail
- `POST /{id}/feedback` - Submit feedback

### Admin (`/api/admin/*`) 🔒 Admin
- `GET /dashboard` - Admin stats
- `POST /trigger-workflow` - Start pipeline
- `GET /workflows` - Workflow status

🔒 = Authentication required

---

## 🐳 Docker Full Stack

### Start Everything
```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5433)
- Redis (port 6379)
- Kafka (port 9092)
- Zookeeper (port 2181)
- Schema Registry (port 8081)
- API (port 8000)
- Frontend (port 3000)
- Grafana (port 3001)
- Prometheus (port 9090)
- Jaeger (port 16686)

### Check Status
```bash
docker-compose ps
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
```

### Stop Everything
```bash
docker-compose down
```

---

## 🔍 Troubleshooting

### Issue: "Connection refused" to PostgreSQL
**Solution:**
```bash
# Check if PostgreSQL is running
docker ps | findstr postgres

# Restart PostgreSQL
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### Issue: "API key required"
**Solution:**
- Make sure you're sending `Authorization: Bearer YOUR_TOKEN` header
- Verify token is not expired (1 hour lifetime)
- Use `/api/auth/refresh` to get new token

### Issue: "403 Forbidden - Premium feature"
**Solution:**
```bash
# Check your tier
curl -X GET http://localhost:8000/api/auth/me -H "Authorization: Bearer YOUR_TOKEN"

# Upgrade manually for testing
psql -h localhost -p 5433 -U postgres -d climatenews -c "UPDATE users SET subscription_tier = 'professional' WHERE email = 'your@email.com';"
```

### Issue: Stripe webhook not working
**Solution:**
- Use Stripe CLI for local testing: `stripe listen --forward-to localhost:8000/api/subscription/webhooks/stripe`
- Get webhook secret: `stripe listen --print-secret`
- Add to `.env`: `STRIPE_WEBHOOK_SECRET=whsec_...`

### Issue: PDF export fails
**Solution:**
```bash
# Install ReportLab
pip install reportlab==4.2.5

# If still failing, check logs
docker-compose logs api | findstr -i "error"
```

---

## 📚 Next Steps

1. **Frontend Development**
   - Create authentication pages
   - Build user dashboard
   - Implement subscription checkout
   - Add URL analyzer UI

2. **Stripe Setup**
   - Create products in Stripe Dashboard
   - Configure webhook endpoint
   - Test payment flow
   - Set up production keys

3. **Testing**
   - Write unit tests
   - Integration tests
   - Load testing
   - Security audit

4. **Deployment**
   - Configure production environment
   - Set up CI/CD pipeline
   - Deploy to cloud (AWS/GCP)
   - Configure monitoring

---

## 📖 Additional Resources

- **Full Documentation:** `docs/archive/BACKEND_COMPLETION_SUMMARY.md`
- **API Docs (Interactive):** http://localhost:8000/docs
- **Architecture Guide:** `README.md`
- **Environment Variables:** `.env.example`
- **Platform Enhancement Plan:** `PLATFORM_ENHANCEMENT_SUMMARY.md`

---

## ✅ Quick Checklist

- [ ] Docker installed and running
- [ ] API keys added to `.env`
- [ ] JWT secret generated
- [ ] Database initialized
- [ ] Dependencies installed
- [ ] API server started
- [ ] Test user created
- [ ] Authentication tested
- [ ] Premium features tested
- [ ] API documentation viewed

---

**🎉 You're all set! The backend is ready for frontend development.**

For questions or issues, refer to:
- `docs/archive/BACKEND_COMPLETION_SUMMARY.md` - Full implementation details
- `http://localhost:8000/docs` - Interactive API documentation
- `README.md` - Project overview
