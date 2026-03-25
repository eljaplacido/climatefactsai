<!-- DEPRECATED DOCUMENT -->
> **⚠️ DEPRECATED:** This document is archived and kept for historical reference only.
>
> **Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) for setup instructions.
>
> **Archive notice:** See [DEPRECATED_NOTICE.md](DEPRECATED_NOTICE.md) for more information.

---

# 🚀 CliLens.AI v2.0 - Quick Start Guide

**Platform Version:** 2.0.0 - Information Portal with Authentication & Premium Features

---

## ✅ What's New in v2.0

- 🔐 **User Authentication** - Register, login, JWT tokens
- 💎 **Premium Tiers** - Freemium, Basic (€9.99), Professional (€29.99), Enterprise
- 📊 **Usage Tracking** - Rate limiting based on subscription tier
- 🔍 **Advanced Search** - Ready for semantic search (Professional+)
- 🌐 **URL Analysis** - On-demand fact-checking for any news URL (Premium)
- 📈 **User Dashboard** - Usage stats, subscription management

---

## 🛠️ Setup Instructions

### **Step 1: Apply New Database Schema**

```bash
# From project root
psql -h localhost -U climatenews_user -d climatenews_db -f infrastructure/database/03_users_and_subscriptions.sql
```

**This creates 8 new tables:**
- `users`, `subscriptions`, `user_usage`, `user_preferences`
- `url_analyses`, `api_keys`, `notifications`, `payment_history`

---

### **Step 2: Update Environment Variables**

Add to your `.env` file:

```bash
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production-min-32-chars

# Stripe Configuration (Get from https://dashboard.stripe.com)
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Email Configuration (SendGrid - https://sendgrid.com)
SENDGRID_API_KEY=SG.your_api_key_here
FROM_EMAIL=noreply@clilens.ai

# Frontend URL (for email links)
FRONTEND_URL=http://localhost:5173
```

---

### **Step 3: Install New Python Dependencies**

```bash
cd api
pip install -r requirements.txt
```

**New packages installed:**
- `bcrypt` - Password hashing
- `PyJWT` - JWT token generation
- `stripe` - Payment processing
- `python-dotenv` - Environment variables

---

### **Step 4: Start the API**

```bash
cd api
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

---

### **Step 5: Test Authentication**

#### **Register a New User**

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@clilens.ai",
    "password": "DemoPass123!",
    "full_name": "Demo User"
  }'
```

**Response:**
```json
{
  "access_token": "eyJ0eXAi...",
  "refresh_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### **Login**

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@clilens.ai",
    "password": "DemoPass123!"
  }'
```

#### **Get User Profile**

```bash
# Use the access_token from login/register response
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

**Response:**
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "demo@clilens.ai",
  "full_name": "Demo User",
  "subscription_tier": "freemium",
  "email_verified": false,
  "created_at": "2025-10-31T12:00:00Z"
}
```

---

## 📚 API Endpoints Overview

### **Authentication** (`/api/auth/*`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/register` | Register new user | No |
| POST | `/auth/login` | Login with email/password | No |
| POST | `/auth/refresh` | Refresh access token | No (refresh token) |
| POST | `/auth/verify-email` | Verify email with token | No |
| POST | `/auth/forgot-password` | Request password reset | No |
| POST | `/auth/reset-password` | Reset password with token | No |
| POST | `/auth/change-password` | Change password | Yes |
| GET | `/auth/me` | Get current user profile | Yes |
| PUT | `/auth/me` | Update user profile | Yes |

### **Articles** (Existing + Enhanced)

| Method | Endpoint | Description | Auth Required | Limits |
|--------|----------|-------------|---------------|--------|
| GET | `/api/articles` | List articles | Optional | Freemium: 5/day, Basic: 50/day |
| GET | `/api/articles/{id}` | Get article detail | Optional | Counts toward daily limit |

---

## 🔒 Testing Rate Limits

### **Freemium User (5 articles/day)**

```bash
# View 5 articles (should work)
for i in {1..5}; do
  curl -X GET "http://localhost:8000/api/articles" \
    -H "Authorization: Bearer YOUR_TOKEN"
done

# 6th article (should return 429 - Too Many Requests)
curl -X GET "http://localhost:8000/api/articles" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected Response (6th request):**
```json
{
  "detail": "Daily article limit exceeded (5/5). Upgrade to access more articles."
}
```

---

## 📊 Subscription Tiers & Limits

| Feature | Freemium | Basic | Professional | Enterprise |
|---------|----------|-------|-------------|------------|
| **Price** | €0 | €9.99/mo | €29.99/mo | Custom |
| **Articles/day** | 5 | 50 | Unlimited | Unlimited |
| **Countries** | 5 | All 31 | All 31 | All 31 |
| **URL Analysis** | ❌ | 5/month | 20/month | Unlimited |
| **Searches/day** | 10 | 50 | Unlimited | Unlimited |
| **API Access** | ❌ | ❌ | 1000 calls/day | Unlimited |
| **Export (PDF/CSV)** | ❌ | ❌ | ✅ | ✅ |
| **Saved Searches** | ❌ | ✅ | ✅ | ✅ |

---

## 🧪 Testing Checklist

### **Authentication Tests**
```bash
# 1. Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test1@example.com","password":"Test123!","full_name":"Test User"}'

# 2. Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test1@example.com","password":"Test123!"}'

# 3. Get profile
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# 4. Update profile
curl -X PUT http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Updated Name"}'

# 5. Test wrong password (should fail)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test1@example.com","password":"WrongPassword"}'
```

### **Rate Limiting Tests**
```bash
# Create freemium user and try to exceed limits
# (see example above)
```

---

## 🌐 Interactive API Documentation

Once the API is running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

You can test all endpoints directly from the browser!

---

## 🐛 Troubleshooting

### **Issue: "JWT_SECRET_KEY not found"**
**Solution:** Add `JWT_SECRET_KEY` to your `.env` file

### **Issue: "bcrypt import error"**
**Solution:** Reinstall bcrypt:
```bash
pip uninstall bcrypt
pip install bcrypt==4.1.2
```

### **Issue: "Table 'users' does not exist"**
**Solution:** Run the database migration:
```bash
psql -h localhost -U climatenews_user -d climatenews_db -f infrastructure/database/03_users_and_subscriptions.sql
```

### **Issue: "CORS error in frontend"**
**Solution:** Add your frontend URL to CORS origins in `api/main.py`:
```python
allow_origins=["http://localhost:3000", "http://localhost:5173", "YOUR_FRONTEND_URL"]
```

---

## 📈 Next Steps

### **Immediate Priorities**

1. **URL Analysis Service** (2-3 days)
   - Create `/api/analyze-url` endpoint
   - Integrate with fact-checking pipeline
   - Add async processing with Kafka

2. **Advanced Search** (2-3 days)
   - Semantic search with pgvector
   - Saved searches for Premium users
   - Auto-complete suggestions

3. **Stripe Integration** (3-4 days)
   - Payment flow
   - Subscription management
   - Webhook handling

4. **Frontend Dashboard** (5-7 days)
   - Login/Register pages
   - User dashboard
   - URL analyzer tool
   - Subscription management

---

## 💡 Quick Tips

1. **Generate JWT Secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. **Check User in Database:**
```sql
SELECT user_id, email, subscription_tier, created_at FROM users;
```

3. **Check Usage Logs:**
```sql
SELECT user_id, usage_type, created_at FROM user_usage ORDER BY created_at DESC LIMIT 10;
```

4. **Reset User's Daily Limit (for testing):**
```sql
DELETE FROM user_usage WHERE user_id = 'USER_UUID' AND DATE(created_at) = CURRENT_DATE;
```

---

## 📞 Support

For questions or issues:
- Check `PLATFORM_ENHANCEMENT_SUMMARY.md` for detailed documentation
- Review API logs in console
- Check PostgreSQL logs for database errors

---

**Last Updated:** 2025-10-31
**Version:** 2.0.0
**Status:** Ready for Testing ✅
