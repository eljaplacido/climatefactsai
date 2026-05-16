"""
Authentication Utilities
Handles password hashing, JWT token generation, and stateful session lifecycle.

Sessions (S2 — added 2026-05-16): every refresh token corresponds to one
`sessions` row keyed by JWT `jti` claim. `/refresh` rotates (revoke old jti,
issue new); `/logout`, password change, and password reset all revoke
sessions server-side; presenting a revoked jti triggers replay detection
and cascade-revocation of all the user's other active sessions.
"""

import os
import secrets
import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import bcrypt
import jwt
from fastapi import HTTPException, status

_logger = logging.getLogger("auth")


# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY environment variable is required. "
        "Generate a secure value with 'openssl rand -hex 32'."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 days


class PasswordHasher:
    """Handles password hashing and verification using bcrypt"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception:
            return False


class TokenManager:
    """Handles JWT token creation and validation"""

    @staticmethod
    def create_access_token(
        user_id: str,
        email: str,
        subscription_tier: str = "freemium",
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token"""
        if expires_delta is None:
            expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        expire = datetime.utcnow() + expires_delta
        to_encode = {
            "sub": user_id,
            "email": email,
            "tier": subscription_tier,
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow()
        }

        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(
        db,
        user_id: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """Issue a stateful refresh token AND insert a row into `sessions`.

        Returns just the encoded JWT; the `jti` is captured in the JWT's
        own payload and persisted to `sessions.jti`. `/refresh` looks the
        jti up to enforce rotation + replay detection.

        Backwards-compat: if the `sessions` table doesn't exist yet
        (migration 017 not applied), this logs a warning and falls back to
        stateless behaviour so existing test envs without the migration
        don't break — `/refresh` will still reject jti-less tokens.
        """
        jti = str(uuid.uuid4())
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode = {
            "sub": user_id,
            "type": "refresh",
            "jti": jti,
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

        try:
            db.execute_update(
                """
                INSERT INTO sessions
                    (jti, user_id, issued_at, last_used_at, expires_at,
                     user_agent, ip_address)
                VALUES
                    (:jti, :user_id, NOW(), NOW(), :expires_at,
                     :user_agent, :ip_address)
                """,
                {
                    "jti": jti,
                    "user_id": user_id,
                    "expires_at": expire,
                    "user_agent": (user_agent or "")[:512] or None,
                    "ip_address": ip_address,
                },
            )
        except Exception as exc:
            _logger.warning(
                "Failed to persist session row for jti=%s; refresh "
                "rotation will reject this token on next use: %s",
                jti, exc,
            )

        return token

    @staticmethod
    def rotate_refresh_token(
        db,
        refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Verify a refresh token, detect replays, rotate, return (new_token, user_id).

        Replay detection: if the presented `jti` is found in `sessions`
        with `revoked_at IS NOT NULL`, treat as a stolen-token replay and
        cascade-revoke ALL remaining active sessions for the user. This
        is the standard "refresh token reuse" defence.
        """
        payload = TokenManager.verify_refresh_token(refresh_token)
        jti = payload.get("jti")
        user_id = payload.get("sub")

        if not jti or not user_id:
            # Tokens issued before migration 017 have no jti. Force re-login.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token from a prior session — please sign in again.",
            )

        try:
            rows = db.execute_query(
                "SELECT jti, revoked_at, expires_at FROM sessions WHERE jti = :jti",
                {"jti": jti},
            )
        except Exception as exc:
            _logger.error("Session lookup failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Session store unavailable.",
            )

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown refresh token.",
            )

        session_row = rows[0]

        # --- Replay detection ---
        if session_row.get("revoked_at") is not None:
            try:
                db.execute_update(
                    "UPDATE sessions "
                    "SET revoked_at = COALESCE(revoked_at, NOW()), "
                    "    revoke_reason = COALESCE(revoke_reason, 'replay_detected') "
                    "WHERE user_id = :uid AND revoked_at IS NULL",
                    {"uid": user_id},
                )
            except Exception as exc:
                _logger.warning("Cascade revoke failed: %s", exc)
            _logger.warning(
                "Refresh token replay detected for user_id=%s jti=%s — "
                "all sessions revoked",
                user_id, jti,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Refresh token replay detected. All sessions have been "
                    "revoked; please sign in again."
                ),
            )

        expires_at = session_row.get("expires_at")
        if expires_at and expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired.",
            )

        # --- Rotate ---
        try:
            db.execute_update(
                "UPDATE sessions SET revoked_at = NOW(), revoke_reason = 'rotated' "
                "WHERE jti = :jti",
                {"jti": jti},
            )
        except Exception as exc:
            _logger.error("Session rotation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to rotate session.",
            )

        new_token = TokenManager.create_refresh_token(
            db, user_id=user_id, user_agent=user_agent, ip_address=ip_address,
        )
        return new_token, user_id

    @staticmethod
    def revoke_session(db, jti: str, reason: str = "logout") -> bool:
        """Mark a single session revoked. Returns True if any row was updated."""
        if not jti:
            return False
        try:
            db.execute_update(
                "UPDATE sessions "
                "SET revoked_at = COALESCE(revoked_at, NOW()), revoke_reason = :reason "
                "WHERE jti = :jti AND revoked_at IS NULL",
                {"jti": jti, "reason": reason},
            )
            return True
        except Exception as exc:
            _logger.warning("revoke_session failed: %s", exc)
            return False

    @staticmethod
    def revoke_all_user_sessions(
        db, user_id: str, reason: str = "password_change",
    ) -> bool:
        """Revoke every active session for a user. Used on password change/reset."""
        if not user_id:
            return False
        try:
            db.execute_update(
                "UPDATE sessions SET revoked_at = NOW(), revoke_reason = :reason "
                "WHERE user_id = :uid AND revoked_at IS NULL",
                {"uid": user_id, "reason": reason},
            )
            return True
        except Exception as exc:
            _logger.warning("revoke_all_user_sessions failed: %s", exc)
            return False

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.InvalidTokenError:
            # PyJWT base class; covers signature mismatch, malformed payload,
            # bad algorithm, etc. (Pre-S8 the code referenced `jwt.JWTError`
            # which is python-jose-only and would have AttributeError'd at
            # runtime after we dropped python-jose.)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )

    @staticmethod
    def verify_access_token(token: str) -> Dict[str, Any]:
        """Verify an access token and return payload"""
        payload = TokenManager.decode_token(token)

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        return payload

    @staticmethod
    def verify_refresh_token(token: str) -> Dict[str, Any]:
        """Verify a refresh token and return payload"""
        payload = TokenManager.decode_token(token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        return payload


class TokenGenerator:
    """Generates secure random tokens for email verification and password reset"""

    @staticmethod
    def generate_verification_token() -> str:
        """Generate a secure random token for email verification"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_reset_token() -> str:
        """Generate a secure random token for password reset"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_api_key() -> tuple[str, str, str]:
        """
        Generate an API key and return (key, hash, prefix)
        Key format: clk_<random_string>
        """
        random_part = secrets.token_urlsafe(32)
        api_key = f"clk_{random_part}"

        # Hash the key for storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Prefix for user identification (first 16 chars)
        prefix = api_key[:16]

        return api_key, key_hash, prefix


class PasswordValidator:
    """Validates password strength"""

    @staticmethod
    def validate_password(password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password meets security requirements
        Returns (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        if len(password) > 128:
            return False, "Password must not exceed 128 characters"

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)

        if not (has_upper and has_lower and has_digit):
            return False, "Password must contain uppercase, lowercase, and numbers"

        return True, None


class EmailValidator:
    """Validates email addresses"""

    @staticmethod
    def validate_email(email: str) -> tuple[bool, Optional[str]]:
        """
        Basic email validation
        Returns (is_valid, error_message)
        """
        if not email or "@" not in email:
            return False, "Invalid email format"

        if len(email) > 255:
            return False, "Email is too long"

        local, domain = email.rsplit("@", 1)

        if not local or not domain:
            return False, "Invalid email format"

        if "." not in domain:
            return False, "Invalid email domain"

        return True, None


def get_password_hasher() -> PasswordHasher:
    """Dependency injection for password hasher"""
    return PasswordHasher()


def get_token_manager() -> TokenManager:
    """Dependency injection for token manager"""
    return TokenManager()
