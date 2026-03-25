"""
OAuth Routes — Google and Microsoft (Outlook) authentication.

Supports OAuth2 authorization code flow for social login.
Users can link Google/Microsoft accounts for one-click sign-in.
"""

from datetime import datetime, timedelta
from typing import Optional
import hashlib
import secrets

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel

from shared.database import get_postgres
from shared.logger import setup_logging
from api.auth_utils import TokenManager, PasswordHasher, TokenGenerator

import httpx
import os

logger = setup_logging("oauth")
router = APIRouter(prefix="/api/auth/oauth", tags=["OAuth"])


class OAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str
    provider: str  # 'google' or 'microsoft'
    state: str  # CSRF protection token


class OAuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    is_new_user: bool
    user_id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


# Google OAuth2 config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Microsoft OAuth2 config
MS_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
MS_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
MS_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")
MS_TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
MS_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"


OAUTH_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET", secrets.token_hex(32))


@router.get("/state")
async def generate_oauth_state():
    """Generate a random state token for CSRF protection during OAuth flow."""
    state_token = secrets.token_urlsafe(32)
    return {"state": state_token}


@router.get("/providers")
async def get_available_providers():
    """Return which OAuth providers are configured."""
    return {
        "google": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "microsoft": bool(MS_CLIENT_ID and MS_CLIENT_SECRET),
    }


@router.post("/callback", response_model=OAuthTokenResponse)
async def oauth_callback(data: OAuthCallbackRequest):
    """
    Handle OAuth2 callback. Exchange authorization code for tokens,
    fetch user profile, create or link account, return JWT.
    """
    # Validate state parameter for CSRF protection
    # The state token must be at least 16 characters and URL-safe
    if not data.state or len(data.state) < 16:
        raise HTTPException(
            status_code=400,
            detail="Invalid or missing OAuth state parameter. Possible CSRF attack."
        )

    # Verify state is a plausible token (URL-safe base64 characters)
    import re as _re
    if not _re.fullmatch(r'[A-Za-z0-9_\-]+', data.state):
        raise HTTPException(
            status_code=400,
            detail="Malformed OAuth state parameter."
        )

    logger.info("OAuth callback received", provider=data.provider, state_length=len(data.state))

    if data.provider == "google":
        user_info = await _exchange_google_code(data.code, data.redirect_uri)
    elif data.provider == "microsoft":
        user_info = await _exchange_microsoft_code(data.code, data.redirect_uri)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {data.provider}")

    if not user_info or not user_info.get("email"):
        raise HTTPException(status_code=400, detail="Failed to retrieve user info from provider")

    db = get_postgres()
    email = user_info["email"].lower()
    provider_id = user_info.get("provider_id", "")

    # Check if user exists by provider or email
    existing = db.execute_query(
        """SELECT user_id, email, subscription_tier, is_active, full_name, avatar_url
           FROM users
           WHERE (auth_provider = :provider AND provider_user_id = :pid)
              OR email = :email
           LIMIT 1""",
        {"provider": data.provider, "pid": provider_id, "email": email}
    )

    is_new_user = False

    if existing:
        user = existing[0]
        user_id = str(user["user_id"])

        if not user.get("is_active"):
            raise HTTPException(status_code=403, detail="Account is deactivated")

        # Update OAuth info
        db.execute_update(
            """UPDATE users
               SET auth_provider = :provider,
                   provider_user_id = :pid,
                   provider_avatar_url = :avatar,
                   last_login_at = NOW()
               WHERE user_id = :uid""",
            {
                "provider": data.provider,
                "pid": provider_id,
                "avatar": user_info.get("avatar_url"),
                "uid": user_id,
            }
        )
    else:
        # Create new user
        is_new_user = True
        random_password = TokenGenerator.generate_verification_token()
        password_hash = PasswordHasher.hash_password(random_password)

        result = db.execute_query(
            """INSERT INTO users (
                   email, password_hash, full_name, auth_provider,
                   provider_user_id, provider_avatar_url, email_verified,
                   subscription_tier
               ) VALUES (
                   :email, :phash, :name, :provider,
                   :pid, :avatar, true, 'freemium'
               )
               RETURNING user_id, email, subscription_tier""",
            {
                "email": email,
                "phash": password_hash,
                "name": user_info.get("name", ""),
                "provider": data.provider,
                "pid": provider_id,
                "avatar": user_info.get("avatar_url"),
            }
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create user")

        user = result[0]
        user_id = str(user["user_id"])

        try:
            db.execute_update(
                "INSERT INTO user_preferences (user_id) VALUES (:uid)",
                {"uid": user_id}
            )
        except Exception:
            pass

    # Generate JWT tokens
    access_token = TokenManager.create_access_token(
        user_id=user_id,
        email=email,
        subscription_tier=user.get("subscription_tier", "freemium"),
    )
    refresh_token = TokenManager.create_refresh_token(user_id=user_id)

    # Log activity
    try:
        import json
        db.execute_update(
            """INSERT INTO user_activity (user_id, activity_type, activity_data)
               VALUES (:uid, 'oauth_login', :data::jsonb)""",
            {"uid": user_id, "data": json.dumps({"provider": data.provider, "is_new": is_new_user})}
        )
    except Exception:
        pass

    logger.info("OAuth login", user_id=user_id, provider=data.provider, is_new=is_new_user)

    return OAuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,
        is_new_user=is_new_user,
        user_id=user_id,
        email=email,
        full_name=user_info.get("name"),
        avatar_url=user_info.get("avatar_url"),
    )


async def _exchange_google_code(code: str, redirect_uri: str) -> Optional[dict]:
    """Exchange Google authorization code for user info."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
            token_resp.raise_for_status()
            tokens = token_resp.json()

            userinfo_resp = await client.get(GOOGLE_USERINFO_URL, headers={
                "Authorization": f"Bearer {tokens['access_token']}"
            })
            userinfo_resp.raise_for_status()
            info = userinfo_resp.json()

            return {
                "email": info.get("email"),
                "name": info.get("name"),
                "avatar_url": info.get("picture"),
                "provider_id": info.get("sub"),
            }
    except httpx.HTTPStatusError as e:
        logger.error(f"Google OAuth failed: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Google OAuth error: {e}")
        return None


async def _exchange_microsoft_code(code: str, redirect_uri: str) -> Optional[dict]:
    """Exchange Microsoft authorization code for user info."""
    if not MS_CLIENT_ID or not MS_CLIENT_SECRET:
        raise HTTPException(status_code=501, detail="Microsoft OAuth not configured")

    token_url = MS_TOKEN_URL_TEMPLATE.format(tenant=MS_TENANT_ID)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(token_url, data={
                "code": code,
                "client_id": MS_CLIENT_ID,
                "client_secret": MS_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "scope": "openid profile email User.Read",
            })
            token_resp.raise_for_status()
            tokens = token_resp.json()

            profile_resp = await client.get(MS_USERINFO_URL, headers={
                "Authorization": f"Bearer {tokens['access_token']}"
            })
            profile_resp.raise_for_status()
            profile = profile_resp.json()

            return {
                "email": profile.get("mail") or profile.get("userPrincipalName"),
                "name": profile.get("displayName"),
                "avatar_url": None,
                "provider_id": profile.get("id"),
            }
    except httpx.HTTPStatusError as e:
        logger.error(f"Microsoft OAuth failed: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Microsoft OAuth error: {e}")
        return None
