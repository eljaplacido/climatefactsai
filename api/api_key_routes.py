"""
API Key Management Routes - Professional+ Feature

Allows Professional and Enterprise users to generate API keys for
programmatic access to CliLens.AI services.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from uuid import uuid4
import secrets
import hashlib
import json

from fastapi import APIRouter, HTTPException, Depends, Security, Header, Body
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from api.auth_routes import get_current_user
from api.rate_limiter import check_premium_feature
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("api-key-management")
router = APIRouter(prefix="/api/api-keys", tags=["API Keys"])

# API Key security scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key"""
    name: str = Field(..., min_length=1, max_length=100, description="API key name/label")
    scopes: List[str] = Field(
        default=["read"],
        description="API key permissions (read, write, admin)"
    )
    expires_in_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="API key expiration (days). None = never expires"
    )


class APIKeyInfo(BaseModel):
    """API key information (without actual key)"""
    id: str
    name: str
    key_prefix: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: bool


class APIKeyCreated(BaseModel):
    """Response when API key is created (includes full key)"""
    id: str
    name: str
    api_key: str  # Only returned once!
    scopes: List[str]
    expires_at: Optional[datetime] = None
    warning: str = "Save this key securely. It will not be shown again!"


class APIKeyUsageStats(BaseModel):
    """API key usage statistics"""
    api_key_id: str
    total_calls: int
    calls_today: int
    calls_this_month: int
    last_used_at: Optional[datetime] = None
    most_used_endpoints: List[dict] = []


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def generate_api_key() -> tuple[str, str]:
    """
    Generate a secure API key and its hash.

    Returns:
        (api_key, hashed_key): Full API key and its hash for storage
    """
    api_key = f"clilens_{secrets.token_urlsafe(32)}"
    hashed = hashlib.sha256(api_key.encode()).hexdigest()
    return api_key, hashed


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Verify an API key against stored hash."""
    provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
    return secrets.compare_digest(provided_hash, stored_hash)


# =============================================================================
# API KEY AUTHENTICATION
# =============================================================================

async def get_user_from_api_key(
    api_key: str = Security(api_key_header)
) -> dict:
    """
    Authenticate user via API key.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header."
        )

    db = get_postgres()

    # Hash the provided key
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Look up API key
    rows = db.execute_query(
        """
        SELECT
            ak.key_id,
            ak.user_id,
            ak.name,
            ak.scopes,
            ak.expires_at,
            ak.is_active,
            u.user_id as uid,
            u.email,
            u.full_name,
            u.subscription_tier,
            u.is_active as user_is_active
        FROM api_keys ak
        JOIN users u ON ak.user_id = u.user_id
        WHERE ak.key_hash = :key_hash
        """,
        {"key_hash": key_hash}
    )

    if not rows:
        raise HTTPException(status_code=401, detail="Invalid API key")

    result = rows[0]

    if not result["is_active"]:
        raise HTTPException(status_code=401, detail="API key has been revoked")

    if result["expires_at"] and result["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=401, detail="API key has expired")

    if not result["user_is_active"]:
        raise HTTPException(status_code=403, detail="User account is disabled")

    # Update last used timestamp
    db.execute_update(
        "UPDATE api_keys SET last_used_at = NOW() WHERE key_id = :key_id",
        {"key_id": result["key_id"]}
    )

    # Log API call
    db.execute_update(
        """
        INSERT INTO user_usage (
            usage_id, user_id, usage_type, metadata, created_at
        ) VALUES (:usage_id, :user_id, 'api_call', :metadata, NOW())
        """,
        {
            "usage_id": str(uuid4()),
            "user_id": result["user_id"],
            "metadata": json.dumps({"api_key_id": str(result["key_id"])}),
        }
    )

    return {
        "user_id": result["user_id"],
        "email": result["email"],
        "full_name": result["full_name"],
        "subscription_tier": result["subscription_tier"],
        "is_active": result["user_is_active"],
    }


# =============================================================================
# API KEY MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("", response_model=APIKeyCreated)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new API key (Professional+ only).

    **Important:** The full API key is only shown once during creation.
    Store it securely!
    """
    # Check premium feature access
    if not check_premium_feature(current_user, "api_access"):
        raise HTTPException(
            status_code=403,
            detail="API key creation requires Professional or Enterprise subscription"
        )

    # Validate scopes
    valid_scopes = ["read", "write", "admin"]
    for scope in request.scopes:
        if scope not in valid_scopes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid scope: {scope}. Valid scopes: {valid_scopes}"
            )

    db = get_postgres()

    # Check API key limit (max 5 per user for Professional)
    if current_user.get("subscription_tier") == "professional":
        count_rows = db.execute_query(
            """
            SELECT COUNT(*) as count
            FROM api_keys
            WHERE user_id = :user_id AND is_active = true
            """,
            {"user_id": current_user["user_id"]}
        )

        if count_rows and count_rows[0].get("count", 0) >= 5:
            raise HTTPException(
                status_code=400,
                detail="Maximum of 5 API keys per Professional account. Revoke unused keys first."
            )

    # Generate API key
    api_key, key_hash = generate_api_key()
    key_id = str(uuid4())
    key_prefix = api_key[:15] + "..."

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    try:
        db.execute_update(
            """
            INSERT INTO api_keys (
                key_id, user_id, name, key_hash, key_prefix,
                scopes, expires_at, is_active, created_at
            ) VALUES (:key_id, :user_id, :name, :key_hash, :key_prefix,
                      :scopes, :expires_at, true, NOW())
            """,
            {
                "key_id": key_id,
                "user_id": current_user["user_id"],
                "name": request.name,
                "key_hash": key_hash,
                "key_prefix": key_prefix,
                "scopes": request.scopes,
                "expires_at": expires_at,
            }
        )

        logger.info(f"API key created: {key_id} for user {current_user['user_id']}")

        return APIKeyCreated(
            id=key_id,
            name=request.name,
            api_key=api_key,
            scopes=request.scopes,
            expires_at=expires_at,
            warning="Save this key securely. It will not be shown again!"
        )

    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.get("", response_model=List[APIKeyInfo])
async def list_api_keys(
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    List all API keys for the current user.

    Returns metadata about each key (but NOT the actual key value).
    """
    if not check_premium_feature(current_user, "api_access"):
        raise HTTPException(
            status_code=403,
            detail="API keys require Professional or Enterprise subscription"
        )

    db = get_postgres()

    query = """
        SELECT
            key_id, name, key_prefix, scopes, created_at,
            expires_at, last_used_at, is_active
        FROM api_keys
        WHERE user_id = :user_id
    """

    if not include_inactive:
        query += " AND is_active = true"

    query += " ORDER BY created_at DESC"

    results = db.execute_query(query, {"user_id": current_user["user_id"]})

    return [
        APIKeyInfo(
            id=str(row["key_id"]),
            name=row["name"],
            key_prefix=row["key_prefix"],
            scopes=row.get("scopes") or ["read"],
            created_at=row["created_at"],
            expires_at=row.get("expires_at"),
            last_used_at=row.get("last_used_at"),
            is_active=row["is_active"],
        )
        for row in results
    ]


@router.get("/{key_id}/usage", response_model=APIKeyUsageStats)
async def get_api_key_usage(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get usage statistics for a specific API key.
    """
    db = get_postgres()

    # Verify ownership
    key_rows = db.execute_query(
        """
        SELECT key_id, last_used_at
        FROM api_keys
        WHERE key_id = :key_id AND user_id = :user_id
        """,
        {"key_id": key_id, "user_id": current_user["user_id"]}
    )

    if not key_rows:
        raise HTTPException(
            status_code=404,
            detail="API key not found or you don't have access"
        )

    key_info = key_rows[0]

    # Get total calls from usage table
    total_rows = db.execute_query(
        """
        SELECT COUNT(*) as count
        FROM user_usage
        WHERE user_id = :user_id
          AND usage_type = 'api_call'
          AND metadata->>'api_key_id' = :key_id
        """,
        {"user_id": current_user["user_id"], "key_id": key_id}
    )

    today_rows = db.execute_query(
        """
        SELECT COUNT(*) as count
        FROM user_usage
        WHERE user_id = :user_id
          AND usage_type = 'api_call'
          AND metadata->>'api_key_id' = :key_id
          AND created_at >= DATE_TRUNC('day', NOW())
        """,
        {"user_id": current_user["user_id"], "key_id": key_id}
    )

    month_rows = db.execute_query(
        """
        SELECT COUNT(*) as count
        FROM user_usage
        WHERE user_id = :user_id
          AND usage_type = 'api_call'
          AND metadata->>'api_key_id' = :key_id
          AND created_at >= DATE_TRUNC('month', NOW())
        """,
        {"user_id": current_user["user_id"], "key_id": key_id}
    )

    return APIKeyUsageStats(
        api_key_id=key_id,
        total_calls=total_rows[0].get("count", 0) if total_rows else 0,
        calls_today=today_rows[0].get("count", 0) if today_rows else 0,
        calls_this_month=month_rows[0].get("count", 0) if month_rows else 0,
        last_used_at=key_info.get("last_used_at"),
        most_used_endpoints=[]
    )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Revoke (deactivate) an API key.
    """
    db = get_postgres()

    result = db.execute_update(
        """
        UPDATE api_keys
        SET is_active = false, revoked_at = NOW()
        WHERE key_id = :key_id AND user_id = :user_id
        """,
        {"key_id": key_id, "user_id": current_user["user_id"]}
    )

    if result == 0:
        raise HTTPException(
            status_code=404,
            detail="API key not found or you don't have access"
        )

    logger.info(f"API key revoked: {key_id} by user {current_user['user_id']}")

    return {"message": "API key revoked successfully"}


@router.put("/{key_id}/rename")
async def rename_api_key(
    key_id: str,
    new_name: str = Body(..., embed=True, min_length=1, max_length=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Rename an API key.
    """
    db = get_postgres()

    result = db.execute_update(
        """
        UPDATE api_keys
        SET name = :new_name
        WHERE key_id = :key_id AND user_id = :user_id
        """,
        {"new_name": new_name, "key_id": key_id, "user_id": current_user["user_id"]}
    )

    if result == 0:
        raise HTTPException(
            status_code=404,
            detail="API key not found or you don't have access"
        )

    return {"message": "API key renamed successfully"}
