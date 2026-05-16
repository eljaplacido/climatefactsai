"""Session-lifecycle tests (S2 — stateful refresh-token rotation).

Covers:
- create_refresh_token writes a session row
- rotate_refresh_token revokes the old jti and issues a new one
- presenting a revoked jti triggers cascade-revocation of all user sessions
- revoke_session marks one row revoked
- revoke_all_user_sessions revokes every active row for a user
- /logout endpoint revokes the current session and is idempotent on bad tokens
- decode_token now uses jwt.InvalidTokenError, not the dead jwt.JWTError
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# In-memory sessions store
# ---------------------------------------------------------------------------

class _InMemorySessionDB:
    """Fake DB that records sessions writes/reads exactly like the production
    schema. Lets the lifecycle tests run without Postgres or migrations.
    """

    def __init__(self) -> None:
        self.sessions: Dict[str, Dict[str, Any]] = {}
        # Tracks UPDATE calls in order for assertions
        self.updates: List[Dict[str, Any]] = []

    # ---- Production interface ----------------------------------------

    def execute_query(self, query: str, params: Optional[dict] = None):
        params = params or {}
        q = " ".join(query.split()).lower()
        if "from sessions where jti" in q:
            jti = params.get("jti")
            sess = self.sessions.get(jti)
            return [sess] if sess else []
        return []

    def execute_update(self, query: str, params: Optional[dict] = None):
        params = params or {}
        q = " ".join(query.split()).lower()
        self.updates.append({"q": q, "params": params})

        if "insert into sessions" in q:
            jti = params["jti"]
            self.sessions[jti] = {
                "jti": jti,
                "user_id": params["user_id"],
                "expires_at": params["expires_at"],
                "revoked_at": None,
                "revoke_reason": None,
                "user_agent": params.get("user_agent"),
                "ip_address": params.get("ip_address"),
            }
            return None

        if "update sessions" in q and "where jti = :jti" in q:
            jti = params["jti"]
            sess = self.sessions.get(jti)
            if sess and sess["revoked_at"] is None:
                sess["revoked_at"] = datetime.utcnow()
                sess["revoke_reason"] = params.get("reason", "rotated")
            return None

        if "update sessions" in q and "where user_id = :uid" in q:
            uid = params.get("uid") or params.get("user_id")
            reason = params.get("reason", "password_change")
            now = datetime.utcnow()
            for sess in self.sessions.values():
                if sess["user_id"] == uid and sess["revoked_at"] is None:
                    sess["revoked_at"] = now
                    sess["revoke_reason"] = reason
            return None

        return None


# ---------------------------------------------------------------------------
# create_refresh_token writes a session row
# ---------------------------------------------------------------------------

class TestCreateRefreshTokenPersistsSession:
    def test_session_row_inserted_with_jti(self, monkeypatch):
        # JWT_SECRET_KEY is required at import time. conftest already sets one,
        # but we set it again so this file is import-order independent.
        monkeypatch.setenv("JWT_SECRET_KEY", os.getenv("JWT_SECRET_KEY", "x" * 64))
        from api.auth_utils import TokenManager
        import jwt as pyjwt

        db = _InMemorySessionDB()
        user_id = "00000000-0000-0000-0000-aaaaaaaaaaaa"

        token = TokenManager.create_refresh_token(
            db, user_id=user_id, user_agent="ua/1.0", ip_address="203.0.113.5",
        )

        decoded = pyjwt.decode(
            token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"]
        )
        assert decoded["type"] == "refresh"
        assert decoded["sub"] == user_id
        jti = decoded["jti"]
        assert jti in db.sessions
        sess = db.sessions[jti]
        assert sess["user_id"] == user_id
        assert sess["user_agent"] == "ua/1.0"
        assert sess["ip_address"] == "203.0.113.5"
        assert sess["revoked_at"] is None


# ---------------------------------------------------------------------------
# rotate_refresh_token: happy path + replay detection
# ---------------------------------------------------------------------------

class TestRotateRefreshToken:
    def test_rotation_revokes_old_jti_and_issues_new(self):
        from api.auth_utils import TokenManager
        import jwt as pyjwt

        db = _InMemorySessionDB()
        user_id = "11111111-1111-1111-1111-111111111111"

        old_token = TokenManager.create_refresh_token(db, user_id=user_id)
        old_jti = pyjwt.decode(
            old_token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"]
        )["jti"]

        new_token, returned_uid = TokenManager.rotate_refresh_token(db, old_token)

        assert returned_uid == user_id
        new_jti = pyjwt.decode(
            new_token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"]
        )["jti"]
        assert new_jti != old_jti

        # Old session is revoked with reason 'rotated'; new one is active.
        assert db.sessions[old_jti]["revoked_at"] is not None
        assert db.sessions[old_jti]["revoke_reason"] == "rotated"
        assert db.sessions[new_jti]["revoked_at"] is None

    def test_replay_of_revoked_jti_cascades_revocation(self):
        from api.auth_utils import TokenManager
        from fastapi import HTTPException

        db = _InMemorySessionDB()
        user_id = "22222222-2222-2222-2222-222222222222"

        # Issue two sessions for the same user (one will become the "stolen" one).
        old_token = TokenManager.create_refresh_token(db, user_id=user_id)
        new_token, _ = TokenManager.rotate_refresh_token(db, old_token)
        # Also issue a "parallel" session (e.g. user logged in from a phone).
        parallel = TokenManager.create_refresh_token(db, user_id=user_id)

        active_before = sum(
            1 for s in db.sessions.values()
            if s["user_id"] == user_id and s["revoked_at"] is None
        )
        assert active_before == 2  # new_token + parallel

        # Replay the OLD (already-rotated) token — must cascade-revoke all.
        with pytest.raises(HTTPException) as exc:
            TokenManager.rotate_refresh_token(db, old_token)
        assert exc.value.status_code == 401
        assert "replay" in str(exc.value.detail).lower()

        active_after = sum(
            1 for s in db.sessions.values()
            if s["user_id"] == user_id and s["revoked_at"] is None
        )
        assert active_after == 0, "All sessions must be revoked after replay"

    def test_unknown_jti_returns_401(self):
        from api.auth_utils import TokenManager
        from fastapi import HTTPException
        import jwt as pyjwt
        import uuid

        db = _InMemorySessionDB()
        # Craft a refresh token whose jti was never persisted (e.g. server lost session row).
        forged_payload = {
            "sub": "33333333-3333-3333-3333-333333333333",
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "exp": datetime.utcnow() + timedelta(days=1),
            "iat": datetime.utcnow(),
        }
        forged_token = pyjwt.encode(
            forged_payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256"
        )

        with pytest.raises(HTTPException) as exc:
            TokenManager.rotate_refresh_token(db, forged_token)
        assert exc.value.status_code == 401
        assert "unknown" in str(exc.value.detail).lower()

    def test_jtiless_legacy_token_rejected(self):
        """Refresh tokens issued before migration 017 had no jti — they must
        be rejected at /refresh to force a fresh login."""
        from api.auth_utils import TokenManager
        from fastapi import HTTPException
        import jwt as pyjwt

        db = _InMemorySessionDB()
        legacy_payload = {
            "sub": "44444444-4444-4444-4444-444444444444",
            "type": "refresh",
            # No jti.
            "exp": datetime.utcnow() + timedelta(days=1),
            "iat": datetime.utcnow(),
        }
        legacy_token = pyjwt.encode(
            legacy_payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256"
        )

        with pytest.raises(HTTPException) as exc:
            TokenManager.rotate_refresh_token(db, legacy_token)
        assert exc.value.status_code == 401
        assert "prior session" in str(exc.value.detail).lower()


# ---------------------------------------------------------------------------
# revoke_session + revoke_all_user_sessions
# ---------------------------------------------------------------------------

class TestRevokeHelpers:
    def test_revoke_session_marks_one_row(self):
        from api.auth_utils import TokenManager
        import jwt as pyjwt

        db = _InMemorySessionDB()
        token = TokenManager.create_refresh_token(db, user_id="user-a")
        jti = pyjwt.decode(token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"])["jti"]

        assert TokenManager.revoke_session(db, jti, reason="logout") is True
        assert db.sessions[jti]["revoked_at"] is not None
        assert db.sessions[jti]["revoke_reason"] == "logout"

    def test_revoke_session_idempotent(self):
        from api.auth_utils import TokenManager
        import jwt as pyjwt

        db = _InMemorySessionDB()
        token = TokenManager.create_refresh_token(db, user_id="user-b")
        jti = pyjwt.decode(token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"])["jti"]

        TokenManager.revoke_session(db, jti)
        first_revoke = db.sessions[jti]["revoked_at"]
        # Second revoke is a no-op (revoked_at NOT changed; revoke_reason kept).
        TokenManager.revoke_session(db, jti, reason="logout")
        assert db.sessions[jti]["revoked_at"] == first_revoke

    def test_revoke_all_user_sessions(self):
        from api.auth_utils import TokenManager

        db = _InMemorySessionDB()
        # Three sessions for user X, one for user Y.
        TokenManager.create_refresh_token(db, user_id="X")
        TokenManager.create_refresh_token(db, user_id="X")
        TokenManager.create_refresh_token(db, user_id="X")
        TokenManager.create_refresh_token(db, user_id="Y")

        TokenManager.revoke_all_user_sessions(db, "X", reason="password_change")

        x_active = sum(1 for s in db.sessions.values()
                       if s["user_id"] == "X" and s["revoked_at"] is None)
        y_active = sum(1 for s in db.sessions.values()
                       if s["user_id"] == "Y" and s["revoked_at"] is None)
        assert x_active == 0
        assert y_active == 1


# ---------------------------------------------------------------------------
# decode_token now catches jwt.InvalidTokenError (not the dead JWTError)
# ---------------------------------------------------------------------------

class TestDecodeTokenExceptionHandling:
    def test_invalid_signature_raises_401(self):
        """Before S2 the except clause referenced `jwt.JWTError` which doesn't
        exist in PyJWT after the S8 python-jose drop. Bad tokens would have
        AttributeError'd at runtime. This test pins the fixed behaviour."""
        from api.auth_utils import TokenManager
        from fastapi import HTTPException
        import jwt as pyjwt

        # Sign with the wrong secret → invalid signature.
        bad = pyjwt.encode(
            {"sub": "X", "type": "access",
             "exp": datetime.utcnow() + timedelta(hours=1)},
            "totally-different-secret",
            algorithm="HS256",
        )
        with pytest.raises(HTTPException) as exc:
            TokenManager.decode_token(bad)
        assert exc.value.status_code == 401

    def test_malformed_token_raises_401(self):
        from api.auth_utils import TokenManager
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            TokenManager.decode_token("not-a-jwt-at-all")
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# /logout endpoint
# ---------------------------------------------------------------------------

class TestLogoutEndpoint:
    def test_logout_revokes_session(self, monkeypatch):
        # Wire the route's get_postgres dependency to our in-memory fake.
        import shared.database as _shared_db
        from api.auth_utils import TokenManager
        from api.main import app
        import jwt as pyjwt

        db = _InMemorySessionDB()
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = db
        try:
            token = TokenManager.create_refresh_token(db, user_id="logout-user")
            jti = pyjwt.decode(
                token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"]
            )["jti"]
            assert db.sessions[jti]["revoked_at"] is None

            client = TestClient(app)
            resp = client.post("/api/auth/logout", json={"refresh_token": token})
            assert resp.status_code == 200
            assert db.sessions[jti]["revoked_at"] is not None
            assert db.sessions[jti]["revoke_reason"] == "logout"
        finally:
            _shared_db._postgres_client = prior

    def test_logout_with_bad_token_is_idempotent(self):
        import shared.database as _shared_db
        from api.main import app

        db = _InMemorySessionDB()
        prior = _shared_db._postgres_client
        _shared_db._postgres_client = db
        try:
            client = TestClient(app)
            resp = client.post(
                "/api/auth/logout",
                json={"refresh_token": "this-is-not-a-real-jwt"},
            )
            # Idempotent: even garbage tokens return 200 so clients can always
            # "log out" without depending on token state.
            assert resp.status_code == 200
        finally:
            _shared_db._postgres_client = prior
