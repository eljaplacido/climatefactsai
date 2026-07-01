"""ML-03 — ingestion quality gate + Google-News redirector resolution.

Pins the launch-blocker behaviour: Google cookie-consent walls, thin stubs and
unresolved redirector URLs are REJECTED (and quarantined) before insert, while a
real >=250-char article passes. Pure functions — no DB / network.

Run: python -m pytest tests/unit/domains/test_ingest_quality_gate.py -o addopts=""
"""

from __future__ import annotations

import base64

import pytest

from app.domains.content.ingest_quality_gate import (
    GateResult,
    body_md5,
    check_article_quality,
    is_consent_wall,
    is_redirector_url,
    quarantine_article,
)
from app.domains.content.data_sources.rss_adapter import (
    _is_google_news_redirector,
    resolve_google_news_url,
)

# The exact cleaned 835-char consent body seen 1,433× in production (md5
# 94a38797a13f417b263c9c7c78c93f08). A representative slice carries every
# signature marker the gate keys on.
CONSENT_WALL = (
    "If you choose to 'Accept all,' we will also use cookies and data to\n\n"
    "If you choose to 'Reject all,' we will not use cookies for these additional "
    "purposes.\n\nNon-personalized content is influenced by things like the content "
    "you're currently viewing. Select 'More options' to see additional information, "
    "including details about managing your privacy settings. You can also visit "
    "g.co/privacytools at any time."
)

REAL_ARTICLE = (
    "The European Union agreed a new net-zero emissions target for 2040 after "
    "marathon negotiations in Brussels. The deal, underpinned by the Paris "
    "Agreement framework, commits member states to a 90% cut in greenhouse gas "
    "emissions relative to 1990 levels. Renewable energy capacity and carbon "
    "market reforms feature heavily in the accompanying roadmap, which analysts "
    "say will reshape the bloc's industrial policy for a generation."
)

PUBLISHER_URL = "https://www.reuters.com/sustainability/eu-2040-target"
REDIRECTOR_URL = (
    "https://news.google.com/rss/articles/CBMibkFVX3lxTE9uVVlfUVloQkF4ZERm"
    "cWFiTmFTWDRPTjFla2RucmxjTVlvemQ1T1A3TndCNzk2OXlxVFE3UXVKTk9l?oc=5"
)


# --- consent-wall detection ------------------------------------------------

def test_consent_wall_is_detected():
    assert is_consent_wall(CONSENT_WALL) is True


@pytest.mark.parametrize("body", ["", None, REAL_ARTICLE])
def test_real_or_empty_body_is_not_consent_wall(body):
    assert is_consent_wall(body) is False


# --- the three required gate cases -----------------------------------------

def test_consent_wall_body_rejected():
    r = check_article_quality(
        title="Climate summit reaches deal", url=PUBLISHER_URL, body=CONSENT_WALL
    )
    assert isinstance(r, GateResult)
    assert r.ok is False
    assert r.category == "consent_wall"


def test_thin_body_rejected():
    r = check_article_quality(
        title="Some headline - Publisher", url=PUBLISHER_URL, body="Short stub. Publisher"
    )
    assert r.ok is False
    assert r.category == "thin_body"


def test_real_article_passes():
    assert len(REAL_ARTICLE) >= 250
    r = check_article_quality(
        title="EU agrees 2040 net-zero target", url=PUBLISHER_URL, body=REAL_ARTICLE
    )
    assert r.ok is True
    assert r.category == "ok"


# --- URL / title requirements ----------------------------------------------

def test_unresolved_google_redirector_url_rejected():
    r = check_article_quality(
        title="Real headline", url=REDIRECTOR_URL, body=REAL_ARTICLE
    )
    assert r.ok is False
    assert r.category == "redirector_url"


@pytest.mark.parametrize("url", ["", None])
def test_missing_url_rejected(url):
    r = check_article_quality(title="Real headline", url=url, body=REAL_ARTICLE)
    assert r.ok is False
    assert r.category == "redirector_url"


@pytest.mark.parametrize("title", ["", None, "   "])
def test_missing_title_rejected(title):
    r = check_article_quality(title=title, url=PUBLISHER_URL, body=REAL_ARTICLE)
    assert r.ok is False
    assert r.category == "missing_title"


def test_known_boilerplate_md5_rejected():
    body = "x" * 400  # long enough to pass the thin-body check
    r = check_article_quality(
        title="Headline", url=PUBLISHER_URL, body=body,
        known_md5s={body_md5(body)},
    )
    assert r.ok is False
    assert r.category == "boilerplate_md5"


def test_is_redirector_url_matches_google_news():
    assert is_redirector_url(REDIRECTOR_URL) is True
    assert is_redirector_url(PUBLISHER_URL) is False
    assert is_redirector_url("https://news.google.com/rss/search?q=climate") is False


# --- quarantine write (best-effort, never raises) --------------------------

class _FakeDB:
    def __init__(self):
        self.inserts = []

    def execute_update(self, sql, params):
        self.inserts.append((sql, params))
        return 1


def test_quarantine_article_records_row():
    db = _FakeDB()
    quarantine_article(
        db, url=REDIRECTOR_URL, title="Headline", source_name="Google News Climate",
        reason="unresolved redirector", category="redirector_url",
        raw_input={"extracted_text": CONSENT_WALL, "title": "Headline"},
    )
    assert len(db.inserts) == 1
    _, params = db.inserts[0]
    assert params["category"] == "redirector_url"
    assert params["body_md5"] == body_md5(CONSENT_WALL)


def test_quarantine_article_never_raises_on_db_error():
    class _Boom:
        def execute_update(self, *a, **k):
            raise RuntimeError("db down")

    # Must swallow the error — a quarantine-write failure cannot abort ingest.
    quarantine_article(
        _Boom(), url="u", title="t", source_name="s",
        reason="r", category="thin_body", raw_input={},
    )


# --- Google-News redirector resolution -------------------------------------

def test_is_google_news_redirector():
    assert _is_google_news_redirector(REDIRECTOR_URL) is True
    assert _is_google_news_redirector(PUBLISHER_URL) is False
    assert _is_google_news_redirector("") is False


def test_resolve_passthrough_for_non_google_url():
    assert resolve_google_news_url(PUBLISHER_URL) == PUBLISHER_URL


def test_resolve_opaque_url_returns_none():
    # Post-2024 AU_yqL… IDs carry no embedded URL — must be unresolvable so the
    # gate quarantines rather than fetching the consent page.
    assert resolve_google_news_url(REDIRECTOR_URL) is None


def test_resolve_legacy_embedded_url():
    # Legacy encoding: the article segment base64-decodes to a blob that embeds
    # the publisher URL directly.
    blob = b"\x08\x13\x22\x1fhttps://www.reuters.com/world/x\x32\x02en"
    seg = base64.urlsafe_b64encode(blob).decode().rstrip("=")
    url = f"https://news.google.com/rss/articles/{seg}?oc=5"
    assert resolve_google_news_url(url) == "https://www.reuters.com/world/x"
