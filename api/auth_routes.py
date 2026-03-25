"""
Authentication Routes
Handles user registration, login, password reset, email verification
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from shared.database import get_postgres
from shared.logger import setup_logging

from api.models import (
    UserRegister,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    EmailVerification,
    PasswordChange,
    UserProfile,
    UserProfileUpdate,
    UserPreferences,
)

from api.auth_utils import (
    PasswordHasher,
    TokenManager,
    TokenGenerator,
    PasswordValidator,
    EmailValidator,
)
from api.email_service import send_verification_email, send_password_reset_email


logger = setup_logging("auth")
router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer()


# Database dependency
def get_db():
    """Get database connection"""
    return get_postgres()


# =============================================================================
# AUTHENTICATION HELPERS
# =============================================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db)
) -> dict:
    """
    Dependency to get current authenticated user from JWT token
    """
    token = credentials.credentials

    try:
        payload = TokenManager.verify_access_token(token)
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        # Fetch user from database
        query = """
            SELECT
                user_id, email, full_name, avatar_url, subscription_tier,
                is_active, email_verified, created_at, last_login_at
            FROM users
            WHERE user_id = :user_id
        """

        rows = db.execute_query(query, params={"user_id": user_id})

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        user = rows[0]

        if not user.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error verifying token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


def get_optional_user(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db)
) -> Optional[dict]:
    """
    Optional authentication - returns user if token is valid, None otherwise
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    try:
        token = authorization.replace("Bearer ", "")
        payload = TokenManager.verify_access_token(token)
        user_id = payload.get("sub")

        query = """
            SELECT
                user_id, email, full_name, subscription_tier,
                is_active, email_verified
            FROM users
            WHERE user_id = :user_id AND is_active = true
        """

        rows = db.execute_query(query, params={"user_id": user_id})
        return rows[0] if rows else None

    except Exception:
        return None


# =============================================================================
# REGISTRATION & LOGIN
# =============================================================================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db=Depends(get_db)):
    """
    Register a new user account
    """
    # Validate email
    is_valid_email, email_error = EmailValidator.validate_email(user_data.email)
    if not is_valid_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=email_error)

    # Validate password
    is_valid_password, password_error = PasswordValidator.validate_password(user_data.password)
    if not is_valid_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=password_error)

    # Check if email already exists
    check_query = "SELECT user_id FROM users WHERE email = :email"
    existing = db.execute_query(check_query, params={"email": user_data.email.lower()})

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash password
    password_hash = PasswordHasher.hash_password(user_data.password)

    # Generate verification token
    verification_token = TokenGenerator.generate_verification_token()
    verification_expires = datetime.utcnow() + timedelta(hours=24)

    # Insert user
    insert_query = """
        INSERT INTO users (
            email, password_hash, full_name, verification_token,
            verification_token_expires, subscription_tier
        )
        VALUES (
            :email, :password_hash, :full_name, :verification_token,
            :verification_expires, 'freemium'
        )
        RETURNING user_id, email, subscription_tier
    """

    params = {
        "email": user_data.email.lower(),
        "password_hash": password_hash,
        "full_name": user_data.full_name,
        "verification_token": verification_token,
        "verification_expires": verification_expires
    }

    try:
        result = db.execute_query(insert_query, params=params)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )

        user = result[0]
        user_id = str(user["user_id"])

        # Create default preferences (use execute_update for non-returning INSERT)
        try:
            db.execute_update(
                "INSERT INTO user_preferences (user_id) VALUES (:user_id)",
                params={"user_id": user_id}
            )
        except Exception as pref_err:
            logger.warning("Failed to create default preferences", error=str(pref_err))

        # Send verification email (non-blocking; log errors but don't fail registration)
        try:
            send_verification_email(user_data.email, verification_token, user_data.full_name)
        except Exception as email_err:
            logger.warning("Failed to send verification email", error=str(email_err))

        logger.info("User registered", user_id=user_id, email=user_data.email)

        # Generate tokens
        access_token = TokenManager.create_access_token(
            user_id=user_id,
            email=user["email"],
            subscription_tier=user["subscription_tier"]
        )

        refresh_token = TokenManager.create_refresh_token(user_id=user_id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600
        )

    except Exception as e:
        logger.error("Registration failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db=Depends(get_db)):
    """
    Login with email and password
    """
    # Fetch user
    query = """
        SELECT
            user_id, email, password_hash, subscription_tier,
            is_active, failed_login_attempts, locked_until
        FROM users
        WHERE email = :email
    """

    rows = db.execute_query(query, params={"email": login_data.email.lower()})

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    user = rows[0]

    # Check if account is locked
    if user.get("locked_until") and user["locked_until"] > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is temporarily locked due to multiple failed login attempts"
        )

    # Check if account is active
    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    # Verify password
    if not PasswordHasher.verify_password(login_data.password, user["password_hash"]):
        # Increment failed attempts
        failed_attempts = user.get("failed_login_attempts", 0) + 1

        update_query = """
            UPDATE users
            SET failed_login_attempts = :attempts,
                locked_until = CASE WHEN :attempts >= 5 THEN :lock_until ELSE NULL END
            WHERE user_id = :user_id
        """

        lock_until = datetime.utcnow() + timedelta(minutes=15) if failed_attempts >= 5 else None

        db.execute_query(update_query, params={
            "attempts": failed_attempts,
            "lock_until": lock_until,
            "user_id": user["user_id"]
        })

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Reset failed attempts and update last login
    update_query = """
        UPDATE users
        SET failed_login_attempts = 0,
            locked_until = NULL,
            last_login_at = CURRENT_TIMESTAMP
        WHERE user_id = :user_id
    """
    db.execute_query(update_query, params={"user_id": user["user_id"]})

    user_id = str(user["user_id"])

    # Generate tokens
    access_token = TokenManager.create_access_token(
        user_id=user_id,
        email=user["email"],
        subscription_tier=user["subscription_tier"]
    )

    refresh_token = TokenManager.create_refresh_token(user_id=user_id)

    logger.info("User logged in", user_id=user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(token_data: RefreshTokenRequest, db=Depends(get_db)):
    """
    Refresh access token using refresh token
    """
    try:
        payload = TokenManager.verify_refresh_token(token_data.refresh_token)
        user_id = payload.get("sub")

        # Fetch user
        query = """
            SELECT user_id, email, subscription_tier, is_active
            FROM users
            WHERE user_id = :user_id
        """

        rows = db.execute_query(query, params={"user_id": user_id})

        if not rows or not rows[0].get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        user = rows[0]

        # Generate new tokens
        access_token = TokenManager.create_access_token(
            user_id=str(user["user_id"]),
            email=user["email"],
            subscription_tier=user["subscription_tier"]
        )

        refresh_token = TokenManager.create_refresh_token(user_id=str(user["user_id"]))

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


# =============================================================================
# EMAIL VERIFICATION
# =============================================================================

@router.post("/verify-email")
async def verify_email(verification: EmailVerification, db=Depends(get_db)):
    """
    Verify user email with token
    """
    query = """
        SELECT user_id, email, verification_token_expires
        FROM users
        WHERE verification_token = :token AND email_verified = false
    """

    rows = db.execute_query(query, params={"token": verification.token})

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )

    user = rows[0]

    if user["verification_token_expires"] < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired"
        )

    # Mark email as verified
    update_query = """
        UPDATE users
        SET email_verified = true,
            verification_token = NULL,
            verification_token_expires = NULL
        WHERE user_id = :user_id
    """

    db.execute_query(update_query, params={"user_id": user["user_id"]})

    logger.info("Email verified", user_id=str(user["user_id"]))

    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """
    Resend email verification token
    """
    if current_user.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified"
        )

    # Generate new token
    verification_token = TokenGenerator.generate_verification_token()
    verification_expires = datetime.utcnow() + timedelta(hours=24)

    update_query = """
        UPDATE users
        SET verification_token = :token,
            verification_token_expires = :expires
        WHERE user_id = :user_id
    """

    db.execute_query(update_query, params={
        "token": verification_token,
        "expires": verification_expires,
        "user_id": current_user["user_id"]
    })

    # Send verification email
    try:
        send_verification_email(
            current_user["email"],
            verification_token,
            current_user.get("full_name", ""),
        )
    except Exception as email_err:
        logger.warning("Failed to resend verification email", error=str(email_err))

    logger.info("Verification email resent", user_id=str(current_user["user_id"]))

    return {"message": "Verification email sent"}


# =============================================================================
# PASSWORD RESET
# =============================================================================

@router.post("/forgot-password")
async def forgot_password(reset_request: PasswordResetRequest, db=Depends(get_db)):
    """
    Request password reset token
    """
    # Always return success to prevent email enumeration
    query = "SELECT user_id FROM users WHERE email = :email AND is_active = true"
    rows = db.execute_query(query, params={"email": reset_request.email.lower()})

    if rows:
        user = rows[0]

        # Generate reset token
        reset_token = TokenGenerator.generate_reset_token()
        reset_expires = datetime.utcnow() + timedelta(hours=1)

        update_query = """
            UPDATE users
            SET reset_token = :token,
                reset_token_expires = :expires
            WHERE user_id = :user_id
        """

        db.execute_query(update_query, params={
            "token": reset_token,
            "expires": reset_expires,
            "user_id": user["user_id"]
        })

        # Send password reset email
        try:
            send_password_reset_email(reset_request.email, reset_token)
        except Exception as email_err:
            logger.warning("Failed to send reset email", error=str(email_err))

        logger.info("Password reset requested", user_id=str(user["user_id"]))

    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password")
async def reset_password(reset_data: PasswordResetConfirm, db=Depends(get_db)):
    """
    Reset password with token
    """
    # Validate new password
    is_valid, error = PasswordValidator.validate_password(reset_data.new_password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    query = """
        SELECT user_id, reset_token_expires
        FROM users
        WHERE reset_token = :token AND is_active = true
    """

    rows = db.execute_query(query, params={"token": reset_data.token})

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    user = rows[0]

    if user["reset_token_expires"] < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )

    # Hash new password
    password_hash = PasswordHasher.hash_password(reset_data.new_password)

    # Update password and clear reset token
    update_query = """
        UPDATE users
        SET password_hash = :password_hash,
            reset_token = NULL,
            reset_token_expires = NULL,
            failed_login_attempts = 0,
            locked_until = NULL
        WHERE user_id = :user_id
    """

    db.execute_query(update_query, params={
        "password_hash": password_hash,
        "user_id": user["user_id"]
    })

    logger.info("Password reset successful", user_id=str(user["user_id"]))

    return {"message": "Password reset successfully"}


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Change password for authenticated user
    """
    # Fetch current password hash
    query = "SELECT password_hash FROM users WHERE user_id = :user_id"
    rows = db.execute_query(query, params={"user_id": current_user["user_id"]})

    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Verify current password
    if not PasswordHasher.verify_password(password_data.current_password, rows[0]["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Validate new password
    is_valid, error = PasswordValidator.validate_password(password_data.new_password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Hash new password
    password_hash = PasswordHasher.hash_password(password_data.new_password)

    # Update password
    update_query = """
        UPDATE users
        SET password_hash = :password_hash
        WHERE user_id = :user_id
    """

    db.execute_query(update_query, params={
        "password_hash": password_hash,
        "user_id": current_user["user_id"]
    })

    logger.info("Password changed", user_id=str(current_user["user_id"]))

    return {"message": "Password changed successfully"}


# =============================================================================
# USER PROFILE
# =============================================================================

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Get current user profile
    """
    return UserProfile(
        user_id=str(current_user["user_id"]),
        email=current_user["email"],
        full_name=current_user.get("full_name"),
        avatar_url=current_user.get("avatar_url"),
        subscription_tier=current_user.get("subscription_tier", "freemium"),
        email_verified=current_user.get("email_verified", False),
        created_at=current_user["created_at"],
        last_login_at=current_user.get("last_login_at")
    )


@router.put("/me", response_model=UserProfile)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Update user profile
    """
    update_query = """
        UPDATE users
        SET full_name = :full_name,
            avatar_url = :avatar_url
        WHERE user_id = :user_id
        RETURNING user_id, email, full_name, avatar_url, subscription_tier,
                  email_verified, created_at, last_login_at
    """

    result = db.execute_query(update_query, params={
        "full_name": profile_update.full_name,
        "avatar_url": profile_update.avatar_url,
        "user_id": current_user["user_id"]
    })

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = result[0]

    return UserProfile(
        user_id=str(user["user_id"]),
        email=user["email"],
        full_name=user.get("full_name"),
        avatar_url=user.get("avatar_url"),
        subscription_tier=user.get("subscription_tier", "freemium"),
        email_verified=user.get("email_verified", False),
        created_at=user["created_at"],
        last_login_at=user.get("last_login_at")
    )
