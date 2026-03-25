<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# \U0001F680 CliLens.AI - Quick Start Guide

**CORRECT PORTS:**
- **Frontend:** http://localhost:3002 (Changed to avoid port conflicts)
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## \u26A1 Start Everything (2 Terminals)

### Terminal 1: Backend
```bash
cd C:\Users\35845\Desktop\DIGICISU\climatenews\api
uvicorn main:app --reload
```

### Terminal 2: Frontend
```bash
cd C:\Users\35845\Desktop\DIGICISU\climatenews\frontend
npm install
npm run dev
```

---

## \U0001F310 Access the Platform

### Frontend: http://localhost:3002
- Home page with articles
- Login/Register
- User dashboard
- URL analyzer
- Pricing page

### API Docs: http://localhost:8000/docs
- Interactive API testing
- All 51 endpoints
- Try authentication

---

## \U0001F3AF Complete Test Flow

1. **Visit:** http://localhost:3002
2. **Click "Sign Up"** \u2192 Register new account
3. **Login** with your credentials
4. **View Dashboard** \u2192 See usage stats
5. **Check Pricing** \u2192 Compare tiers
6. **Try URL Analyzer** \u2192 Premium feature (requires Basic+)
7. **Browse Articles** \u2192 Home page

---

## \U0001F527 Ports Summary

| Service | Port | URL |
|---------|------|-----|
| **Frontend (Vite)** | 3002 | http://localhost:3002 |
| **Backend API** | 8000 | http://localhost:8000 |
| **API Docs** | 8000 | http://localhost:8000/docs |
| **PostgreSQL** | 5433 | localhost:5433 |
| **Redis** | 6379 | localhost:6379 |
| **Kafka** | 9092 | localhost:9092 |
| **Grafana** | 3001 | http://localhost:3001 |
| **Prometheus** | 9090 | http://localhost:9090 |

**Note:** Port 5173 is Nexsus, Port 3000 is your other project. CliLens uses 3002!

---

## \U0001F9EA Test Premium Features

To test premium features, manually upgrade your account:

```bash
# Connect to database
psql -h localhost -p 5433 -U postgres -d climatenews

# Upgrade to Professional tier
UPDATE users SET subscription_tier = 'professional' WHERE email = 'your@email.com';

# Exit
\q
```

Then refresh the dashboard to see unlimited limits and access premium features.

---

## \U00002705 What's Working

- \u2705 User Registration
- \u2705 Login/Logout
- \u2705 User Dashboard with usage stats
- \u2705 Pricing page with 4 tiers
- \u2705 URL Analyzer (Basic+ only)
- \u2705 Protected routes
- \u2705 Tier-based feature gating
- \u2705 Dynamic navigation

---

## \U0001F4DA Documentation

- **This File** - Quick start
- **FRONTEND_COMPLETION_SUMMARY.md** - Complete frontend docs
- **BACKEND_COMPLETION_SUMMARY.md** - Complete backend docs
- **QUICK_START_BACKEND.md** - Detailed backend guide

---

## \U0001F389 You're Ready!

Visit **http://localhost:3002** and start testing!
