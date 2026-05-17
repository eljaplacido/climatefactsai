"""
API Authentication Routes - Test Suite

Tests user registration, login, token management, and profile operations.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import jwt

# Import the FastAPI app
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.main import app
from api.auth_utils import PasswordHasher, TokenManager

# Test client
client = TestClient(app)

# Test data
TEST_USER_EMAIL = "testuser@example.com"
TEST_USER_PASSWORD = "SecurePass123!"
TEST_USER_NAME = "Test User"


class TestHealthCheck:
    """Test basic API health endpoint"""
    
    def test_health_check(self):
        """Health endpoint should return 200 OK"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestUserRegistration:
    """Test user registration endpoint"""
    
    def test_register_user_success(self):
        """Should successfully register a new user"""
        response = client.post("/api/auth/register", json={
            "email": f"new_{TEST_USER_EMAIL}",
            "password": TEST_USER_PASSWORD,
            "full_name": TEST_USER_NAME
        })
        
        assert response.status_code == 201
        data = response.json()
        
        # Check response structure
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600
        
        # Tokens should be valid strings
        assert len(data["access_token"]) > 20
        assert len(data["refresh_token"]) > 20
    
    def test_register_duplicate_email(self):
        """Should reject duplicate email registration"""
        # Register first user
        client.post("/api/auth/register", json={
            "email": "duplicate@example.com",
            "password": TEST_USER_PASSWORD,
            "full_name": TEST_USER_NAME
        })
        
        # Try to register again with same email
        response = client.post("/api/auth/register", json={
            "email": "duplicate@example.com",
            "password": "DifferentPass123!",
            "full_name": "Another User"
        })
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_register_invalid_email(self):
        """Should reject invalid email format"""
        response = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": TEST_USER_PASSWORD,
            "full_name": TEST_USER_NAME
        })
        
        assert response.status_code == 400
        assert "email" in response.json()["detail"].lower()
    
    def test_register_weak_password(self):
        """Should reject weak passwords"""
        response = client.post("/api/auth/register", json={
            "email": "weak@example.com",
            "password": "123",  # Too short
            "full_name": TEST_USER_NAME
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_register_missing_email(self):
        """Should reject registration without email"""
        response = client.post("/api/auth/register", json={
            "password": TEST_USER_PASSWORD,
            "full_name": TEST_USER_NAME
        })
        
        assert response.status_code == 422


class TestUserLogin:
    """Test user login endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_test_user(self):
        """Create a test user before each test"""
        client.post("/api/auth/register", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "full_name": TEST_USER_NAME
        })
    
    def test_login_success(self):
        """Should successfully log in with correct credentials"""
        response = client.post("/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_wrong_password(self):
        """Should reject login with wrong password"""
        response = client.post("/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": "WrongPassword123!"
        })
        
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()
    
    def test_login_nonexistent_user(self):
        """Should reject login for non-existent user"""
        response = client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": TEST_USER_PASSWORD
        })
        
        assert response.status_code == 401
    
    def test_login_missing_credentials(self):
        """Should reject login without credentials"""
        response = client.post("/api/auth/login", json={})
        
        assert response.status_code == 422


class TestTokenManagement:
    """Test JWT token operations"""
    
    def test_access_token_structure(self):
        """Access token should contain correct claims"""
        # Register and get token
        response = client.post("/api/auth/register", json={
            "email": "token@example.com",
            "password": TEST_USER_PASSWORD,
            "full_name": TEST_USER_NAME
        })
        
        access_token = response.json()["access_token"]
        
        # Decode without verification (for testing)
        payload = jwt.decode(access_token, options={"verify_signature": False})
        
        assert "sub" in payload  # User ID
        assert "email" in payload
        assert "tier" in payload
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_expired_token_rejected(self):
        """Should reject expired access tokens"""
        # Create an expired token
        expired_token = TokenManager.create_access_token(
            user_id="test-user-id",
            email="test@example.com",
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        
        # Try to access protected endpoint
        response = client.get(
            "/api/user/preferences",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()
    
    def test_invalid_token_rejected(self):
        """Should reject malformed tokens"""
        response = client.get(
            "/api/user/preferences",
            headers={"Authorization": "Bearer invalid-token-12345"}
        )
        
        assert response.status_code == 401
    
    def test_refresh_token(self):
        """Should refresh access token with valid refresh token"""
        # Register and get tokens
        register_response = client.post("/api/auth/register", json={
            "email": "refresh@example.com",
            "password": TEST_USER_PASSWORD,
            "full_name": TEST_USER_NAME
        })
        
        refresh_token = register_response.json()["refresh_token"]
        
        # Use refresh token to get new access token
        response = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestUserProfile:
    """Test user profile operations"""
    
    @pytest.fixture
    def auth_headers(self, request):
        """Get authentication headers for test user"""
        # Use a unique email per test to avoid duplicate-registration errors when the
        # SmartFakeDB persists state across tests sharing this module-scoped mock.
        unique_email = f"profile_{request.node.name}@example.com"
        response = client.post("/api/auth/register", json={
            "email": unique_email,
            "password": TEST_USER_PASSWORD,
            "full_name": TEST_USER_NAME
        })

        access_token = response.json()["access_token"]
        return {"Authorization": f"Bearer {access_token}"}

    def test_get_profile(self, auth_headers):
        """Should retrieve user profile"""
        response = client.get("/api/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "user_id" in data
        assert "@example.com" in data["email"]
        assert data["full_name"] == TEST_USER_NAME
        assert data["subscription_tier"] == "freemium"
        assert "created_at" in data
    
    def test_get_profile_unauthenticated(self):
        """Should reject profile request without auth"""
        response = client.get("/api/auth/me")

        # FastAPI's HTTPBearer returns 403 when auto_error=True with no header,
        # but the platform's auth dependency returns 401 (RFC 7235 — missing/
        # invalid credentials → 401). Accept either as long as the endpoint
        # refuses access.
        assert response.status_code in (401, 403)
    
    def test_update_profile(self, auth_headers):
        """Should update user profile"""
        response = client.put(
            "/api/auth/me",
            headers=auth_headers,
            json={
                "full_name": "Updated Name",
                "avatar_url": "https://example.com/avatar.jpg"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["avatar_url"] == "https://example.com/avatar.jpg"


class TestPasswordOperations:
    """Test password change and reset"""
    
    @pytest.fixture
    def auth_headers(self, request):
        """Get authentication headers for test user"""
        unique_email = f"password_{request.node.name}@example.com"
        response = client.post("/api/auth/register", json={
            "email": unique_email,
            "password": TEST_USER_PASSWORD,
            "full_name": TEST_USER_NAME
        })

        access_token = response.json()["access_token"]
        return {"Authorization": f"Bearer {access_token}"}

    def test_change_password(self, auth_headers):
        """Should change password with correct current password"""
        response = client.post(
            "/api/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": TEST_USER_PASSWORD,
                "new_password": "NewSecurePass123!"
            }
        )

        assert response.status_code == 200
    
    def test_change_password_wrong_current(self, auth_headers):
        """Should reject password change with wrong current password"""
        response = client.post(
            "/api/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "WrongPassword123!",
                "new_password": "NewSecurePass123!"
            }
        )
        
        assert response.status_code == 400
    
    def test_request_password_reset(self):
        """Should accept password reset request"""
        response = client.post("/api/auth/forgot-password", json={
            "email": TEST_USER_EMAIL
        })
        
        # Should always return 200 to prevent email enumeration
        assert response.status_code == 200


class TestPasswordHasher:
    """Test password hashing utility"""
    
    def test_hash_password(self):
        """Should hash password successfully"""
        hashed = PasswordHasher.hash_password("TestPassword123!")
        
        assert len(hashed) > 0
        assert hashed != "TestPassword123!"
        assert hashed.startswith("$2b$")  # bcrypt prefix
    
    def test_verify_correct_password(self):
        """Should verify correct password"""
        password = "TestPassword123!"
        hashed = PasswordHasher.hash_password(password)
        
        assert PasswordHasher.verify_password(password, hashed) is True
    
    def test_verify_wrong_password(self):
        """Should reject wrong password"""
        password = "TestPassword123!"
        hashed = PasswordHasher.hash_password(password)
        
        assert PasswordHasher.verify_password("WrongPassword!", hashed) is False
    
    def test_different_hashes_for_same_password(self):
        """Should generate different hashes for same password (salt)"""
        password = "TestPassword123!"
        hash1 = PasswordHasher.hash_password(password)
        hash2 = PasswordHasher.hash_password(password)
        
        assert hash1 != hash2  # Different due to random salt


# ==============================================================================
# PYTEST CONFIGURATION
# ==============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Set up test database before running tests"""
    # TODO: Implement test database setup
    # - Create test database
    # - Run migrations
    # - Seed with test data
    yield
    # TODO: Cleanup test database after tests


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_data():
    """Clean up test data after each test"""
    yield
    # TODO: Implement cleanup
    # - Delete test users
    # - Reset database state


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

