"""Pin test for F7 — knowledge-graph entity boilerplate filter.

The user reported a cookie-consent string ("cookies") surfacing as a
knowledge-graph entity on the article detail page. Web/CMS boilerplate
(cookie banners, nav, legal footers, newsletter prompts) leaks into
article text via RSS summaries and imperfect HTML extraction, then gets
mis-extracted as entities. `is_boilerplate_entity` drops them before
persistence.

Run locally with:
    python -m pytest tests/backend/test_entity_boilerplate_filter.py -o addopts=""
"""

from __future__ import annotations

import pytest

from app.domains.intelligence.entity_extraction_service import is_boilerplate_entity


# --- Must be filtered (boilerplate) ---------------------------------------

@pytest.mark.parametrize(
    "name",
    [
        "cookies",
        "Cookies",
        "COOKIES",
        "cookie",
        "Cookie Policy",
        "Cookie Settings",
        "Accept All Cookies",       # substring match
        "Our Cookie Consent Banner",  # substring match
        "Privacy Policy",
        "privacy policy and terms",  # substring match
        "Terms of Service",
        "Terms and Conditions",
        "Newsletter",
        "Subscribe to our newsletter",  # substring match
        "Sign Up",
        "Log In",
        "Advertisement",
        "Sponsored Content",
        "Related Articles",
        "All Rights Reserved",
        "  cookies  ",              # whitespace-padded
        "",                          # empty
        "   ",                       # whitespace-only
    ],
)
def test_boilerplate_names_are_filtered(name):
    assert is_boilerplate_entity(name) is True, f"{name!r} should be flagged boilerplate"


# --- Must NOT be filtered (legitimate climate entities) -------------------

@pytest.mark.parametrize(
    "name",
    [
        "European Union",
        "Paris Agreement",
        "IPCC",
        "Greta Thunberg",
        "carbon dioxide",
        "Science Based Targets initiative",
        "Climate Action Tracker",
        "Tesla",                     # contains no boilerplate substring
        "renewable energy",
        "Amazon rainforest",         # "Amazon" the rainforest, not the shop
        "Great Barrier Reef",
        "net-zero emissions",
        "solar power",
    ],
)
def test_legitimate_entities_pass(name):
    assert is_boilerplate_entity(name) is False, f"{name!r} should NOT be flagged boilerplate"
