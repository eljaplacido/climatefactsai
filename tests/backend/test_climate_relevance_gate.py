"""Pin test for F1 — content-scope relevance gate.

The platform ingested off-topic stories (e.g. a bus-accident report from a
general-news feed). classify_climate_relevance() is a conservative keyword
gate: it accepts anything with a climate/sustainability/energy signal and
rejects only items with NO signal at all, so legitimate coverage is never
dropped.

Run:  python -m pytest tests/backend/test_climate_relevance_gate.py -o addopts=""
"""

from __future__ import annotations

import pytest

from app.domains.intelligence.editorial_gate import classify_climate_relevance


# --- Must be REJECTED (no climate signal) ---------------------------------

@pytest.mark.parametrize(
    "title,body",
    [
        (
            "Accidente en vía Los Libertadores: Bus interprovincial sufre despiste y deja cinco heridos",
            "A bus skidded off the road leaving five people injured near the highway.",
        ),
        ("Local football team wins the regional championship", "The match ended 3-1 after extra time."),
        ("Celebrity wedding draws thousands of fans", "The couple married in a lavish ceremony downtown."),
        ("Stock market closes slightly higher today", "Shares in tech companies edged up in light trading."),
        ("", ""),
    ],
)
def test_off_topic_is_rejected(title, body):
    is_rel, score, reason = classify_climate_relevance(title, body)
    assert is_rel is False, f"should reject: {title!r} (reason={reason})"
    assert score < 0.5


# --- Must be ACCEPTED (clear climate signal) ------------------------------

@pytest.mark.parametrize(
    "title,body",
    [
        ("EU agrees new net-zero emissions target for 2040", "The Paris Agreement framework underpins the deal."),
        ("Solar power capacity hits record high in India", "Renewable energy now supplies a fifth of the grid."),
        ("Drought and wildfire devastate Southern Europe", "Extreme weather linked to global warming intensifies."),
        ("Company publishes CSRD sustainability report", "The ESG disclosure covers Scope 1, 2 and 3 emissions."),
        ("IPCC warns of accelerating sea level rise", "Carbon dioxide concentrations continue to climb."),
    ],
)
def test_climate_articles_are_accepted(title, body):
    is_rel, score, reason = classify_climate_relevance(title, body)
    assert is_rel is True, f"should accept: {title!r} (reason={reason})"
    assert score >= 0.5


def test_two_weak_signals_pass():
    is_rel, score, reason = classify_climate_relevance(
        "Floods and drought hit the region", "Communities cope with the aftermath."
    )
    assert is_rel is True
    assert score >= 0.5


def test_single_weak_signal_passes_low_confidence():
    # One ambiguous signal — let through but flagged for review (don't drop coverage).
    is_rel, score, reason = classify_climate_relevance(
        "New battery factory opens", "The plant will employ 500 people."
    )
    assert is_rel is True
    assert score < 0.5
    assert "review" in reason.lower()


def test_reason_is_traceable():
    _, _, reason = classify_climate_relevance("Global warming accelerates", "x")
    assert "matched" in reason.lower()
