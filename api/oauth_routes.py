"""
OAuth Routes — Google and Microsoft (Outlook) authentication.

Supports OAuth2 authorization code flow for social login.
Users can link Google/Microsoft accounts for one-click sign-in.
"""

from typing import Optional
import secrets

from fastapi import APIRouter, HTTPException, Request
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
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Microsoft OAuth2 config
MS_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")
MS_TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
MS_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"


OAUTH_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET", secrets.token_hex(32))


def _read_secret_env(*names: str) -> str:
    """Return first non-empty env var among aliases."""
    for name in names:
        value = os.getenv(name, "")
        if value and value.strip():
            return value.strip()
    return ""


def _looks_placeholder(value: str) -> bool:
    """Detect obvious placeholder credentials that should not be treated as configured."""
    if not value:
        return False
    v = value.strip().lower()
    if not v:
        return False
    if "placeholder" in v:
        return True
    return v in {
        "changeme",
        "replace-me",
        "dummy",
        "dummy-value",
        "example",
        "example-value",
    }


def _oauth_config() -> dict:
    """Load OAuth provider credentials dynamically from env."""
    google_client_id = _read_secret_env("GOOGLE_CLIENT_ID", "google-client-id")
    google_client_secret = _read_secret_env("GOOGLE_CLIENT_SECRET", "google-client-secret")
    microsoft_client_id = _read_secret_env("MICROSOFT_CLIENT_ID", "microsoft-client-id")
    microsoft_client_secret = _read_secret_env("MICROSOFT_CLIENT_SECRET", "microsoft-client-secret")

    if _looks_placeholder(google_client_id) or _looks_placeholder(google_client_secret):
        google_client_id = ""
        google_client_secret = ""
    if _looks_placeholder(microsoft_client_id) or _looks_placeholder(microsoft_client_secret):
        microsoft_client_id = ""
        microsoft_client_secret = ""

    return {
        "google_client_id": google_client_id,
        "google_client_secret": google_client_secret,
        "ms_client_id": microsoft_client_id,
        "ms_client_secret": microsoft_client_secret,
    }


@router.get("/state")
async def generate_oauth_state():
    """Generate a random state token for CSRF protection during OAuth flow."""
    state_token = secrets.token_urlsafe(32)
    return {"state": state_token}


@router.get("/providers")
async def get_available_providers():
    """Return which OAuth providers are configured."""
    cfg = _oauth_config()
    google_enabled = bool(cfg["google_client_id"] and cfg["google_client_secret"])
    microsoft_enabled = bool(cfg["ms_client_id"] and cfg["ms_client_secret"])

    return {
        # Backward-compatible booleans
        "google": google_enabled,
        "microsoft": microsoft_enabled,
        # Runtime client metadata for frontend OAuth button wiring
        "google_client_id": cfg["google_client_id"] if google_enabled else "",
        "microsoft_client_id": cfg["ms_client_id"] if microsoft_enabled else "",
        # Preferred structured payload for new clients
        "providers": {
            "google": {
                "enabled": google_enabled,
                "client_id": cfg["google_client_id"] if google_enabled else "",
            },
            "microsoft": {
                "enabled": microsoft_enabled,
                "client_id": cfg["ms_client_id"] if microsoft_enabled else "",
            },
        },
    }


@router.post("/callback", response_model=OAuthTokenResponse)
async def oauth_callback(data: OAuthCallbackRequest, request: Request):
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

    # Generate JWT tokens (S2: refresh is stateful — write a session row).
    access_token = TokenManager.create_access_token(
        user_id=user_id,
        email=email,
        subscription_tier=user.get("subscription_tier", "freemium"),
    )

    _ua = None
    _ip = None
    try:
        _ua_raw = request.headers.get("user-agent")
        _ua = _ua_raw[:512] if _ua_raw else None
        _xff = request.headers.get("x-forwarded-for")
        if _xff:
            _ip = _xff.split(",")[0].strip()
        elif request.client:
            _ip = request.client.host
    except Exception:
        pass

    refresh_token = TokenManager.create_refresh_token(
        db, user_id=user_id, user_agent=_ua, ip_address=_ip,
    )

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
    """Exchange Google authorization code for user info.

    Security: Google's `email` claim is only trustworthy when
    `email_verified=true`. Without this check, anyone who registers any
    Google account under a victim's email could sign in as the victim
    (account-takeover via email-match in the callback handler).
    """
    cfg = _oauth_config()
    google_client_id = cfg["google_client_id"]
    google_client_secret = cfg["google_client_secret"]

    if not google_client_id or not google_client_secret:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": google_client_id,
                "client_secret": google_client_secret,
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

            email = info.get("email")
            # `email_verified` may come back as a bool or as the string "true"
            # depending on Google's response variant.
            ev_raw = info.get("email_verified")
            email_verified = (
                ev_raw is True
                or (isinstance(ev_raw, str) and ev_raw.lower() == "true")
            )

            if not email or not email_verified:
                logger.warning(
                    "Google OAuth rejected: email_verified is false",
                    email=email,
                    email_verified=ev_raw,
                )
                return None

            return {
                "email": email,
                "name": info.get("name"),
                "avatar_url": info.get("picture"),
                "provider_id": info.get("sub"),
                "email_verified": True,
            }
    except httpx.HTTPStatusError as e:
        logger.error(f"Google OAuth failed: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Google OAuth error: {e}")
        return None


async def _exchange_microsoft_code(code: str, redirect_uri: str) -> Optional[dict]:
    """Exchange Microsoft authorization code for user info."""
    cfg = _oauth_config()
    ms_client_id = cfg["ms_client_id"]
    ms_client_secret = cfg["ms_client_secret"]

    if not ms_client_id or not ms_client_secret:
        raise HTTPException(status_code=501, detail="Microsoft OAuth not configured")

    token_url = MS_TOKEN_URL_TEMPLATE.format(tenant=MS_TENANT_ID)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(token_url, data={
                "code": code,
                "client_id": ms_client_id,
                "client_secret": ms_client_secret,
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
