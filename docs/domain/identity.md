# Identity Domain

## Overview

The Identity domain handles user authentication, authorization, subscriptions, API key management, and usage tracking for the CliLens.AI platform.

## Responsibilities

- User registration and authentication (JWT)
- Subscription tier management (Freemium, Basic, Professional, Enterprise)
- API key lifecycle for B2B integrations
- Usage tracking and rate limiting
- User preferences and notifications

## Data Models

### User
```python
class User(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    subscription_tier: str  # 'freemium', 'basic', 'professional', 'enterprise'
    email_verified: bool
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
```

### Subscription
```python
class Subscription(BaseModel):
    id: UUID
    user_id: UUID
    tier: str
    status: str  # 'active', 'canceled', 'expired'
    current_period_start: datetime
    current_period_end: datetime
    stripe_subscription_id: str | None
```

### APIKey
```python
class APIKey(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    key_hash: str  # Never store plain keys!
    key_prefix: str  # First 15 chars for display
    scopes: list[str]  # ['read', 'write', 'admin']
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
```

## Services

- **AuthService**: Login, registration, JWT tokens, password reset
- **SubscriptionService**: Tier upgrades, Stripe integration
- **APIKeyService**: Key generation, validation, revocation
- **UsageService**: Track API calls, article views, feature usage

## Subscription Tiers

| Tier | Price | Features |
|------|-------|----------|
| Freemium | $0 | 5 articles/day, basic search |
| Basic | $9/mo | 50 articles/day, saved searches, 5 URL analyses/mo |
| Professional | $29/mo | Unlimited articles, semantic search, 20 URL analyses/mo, API access, PDF export |
| Enterprise | Custom | Unlimited everything, dedicated support, SSO, SLA |

## Rate Limits

| Action | Freemium | Basic | Professional | Enterprise |
|--------|----------|-------|--------------|------------|
| Articles/day | 5 | 50 | Unlimited | Unlimited |
| URL Analyses/month | 0 | 5 | 20 | Unlimited |
| API Calls/day | 0 | 0 | 1,000 | Custom |
| Saved Searches | 0 | 3 | 10 | Unlimited |

## API Endpoints

- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - Login (returns JWT)
- `POST /api/auth/refresh` - Refresh access token
- `GET /api/user/profile` - User profile
- `GET /api/user/usage` - Usage stats
- `POST /api/subscription/create` - Start subscription
- `POST /api/api-keys` - Generate API key
- `GET /api/api-keys` - List user's API keys
- `DELETE /api/api-keys/{id}` - Revoke API key

## Future Enhancements
- SSO (Google, Microsoft, Okta)
- Multi-factor authentication
- Team accounts with role-based access
- Usage-based pricing tiers
- Referral program

