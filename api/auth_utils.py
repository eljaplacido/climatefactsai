"""
Authentication Utilities
Handles password hashing, JWT token generation, and email verification
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import bcrypt
import jwt
from fastapi import HTTPException, status


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
    def create_refresh_token(user_id: str) -> str:
        """Create a JWT refresh token"""
        expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        expire = datetime.utcnow() + expires_delta

        to_encode = {
            "sub": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow()
        }

        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
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
