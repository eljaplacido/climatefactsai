"""Smoke tests that catch container-startup failures at CI time.

2026-05-28 — added after Cloud Build deployed 9 failed revisions in a
row with "Container import failed", caused by an indent bug that
returned `None` from a FastAPI route handler. Running `from api.main
import app` in CI catches the entire class of import-time errors
(syntax bugs, missing modules, broken side-effects) before they reach
prod. Keep this fast: no DB, no network, no LLM calls — pure import.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.unit
def test_api_main_app_imports():
    """The FastAPI app object must be importable.

    If this fails, `uvicorn api.main:app` cannot start the container.
    """
    mod = importlib.import_module("api.main")
    assert hasattr(mod, "app"), "api.main must expose `app`"


@pytest.mark.unit
def test_chat_routes_imports():
    """Chat router must be importable without side-effects."""
    from api import chat_routes
    assert hasattr(chat_routes, "router"), "chat_routes must expose `router`"


@pytest.mark.unit
def test_llm_client_imports():
    """LLM client + fallback chain helpers must be importable."""
    from app.domains.intelligence.llm_client import (
        get_llm_client,
        llm_chat,
        llm_chat_with_fallback,
    )
    assert callable(get_llm_client)
    assert callable(llm_chat)
    assert callable(llm_chat_with_fallback)


@pytest.mark.unit
def test_critical_router_inclusion():
    """The 10 most-used routes are wired into the app.

    Catches the class of regression where a router was added in code
    but the include_router() line was deleted/never added.
    """
    from api.main import app

    # Map every registered prefix in the FastAPI app
    prefixes = {
        getattr(route, "path", "") for route in app.routes
    }

    critical = [
        "/api/chat",          # chat surface
        "/api/articles",      # core article feed
        "/api/companies",     # corporate tracker
        "/api/status/gx10",   # GX10 visibility
        "/api/status/summary",
        "/api/feedback/topic/off-topic-ids",
        "/api/sdg",
        "/api/semantic/explain",
        "/api/golden-examples",
        "/api/skills",
    ]
    # Each critical path should exist (or have a sub-route that does)
    for cp in critical:
        matched = any(p.startswith(cp) for p in prefixes)
        assert matched, f"Missing critical route prefix: {cp}"
