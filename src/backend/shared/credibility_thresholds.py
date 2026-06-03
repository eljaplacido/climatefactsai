"""Single source of truth for credibility-level thresholds (audit seq-5, 2026-06-02).

The e2e audit found 4 contradictory ladders mapping a numeric score to a
HIGH/MEDIUM/LOW label:
  - reliability_scorer.py            : HIGH>=80, MEDIUM>=50  (0-100)
  - services/url_analyzer.py         : HIGH>=75, MEDIUM>=45  (0-100)
  - domains/content/services.py      : high>=0.75, medium>=0.45 (0-1)
  - domains/intelligence/services.py : high>=0.75, medium>=0.45 (0-1)

So a single article scored 76/100 read "HIGH" on the URL path but "MEDIUM"
elsewhere. Every path now routes through this module so one score maps to
exactly one label everywhere. Canonical thresholds match the already-correct
reliability_scorer (HIGH=80, MEDIUM=50).
"""

from __future__ import annotations

# 0-100 scale.
HIGH = 80
MEDIUM = 50


def level_for(score) -> str:
    """Map a 0-100 score to 'HIGH' | 'MEDIUM' | 'LOW' (uppercase)."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "LOW"
    if s >= HIGH:
        return "HIGH"
    if s >= MEDIUM:
        return "MEDIUM"
    return "LOW"


def level_for_unit(score) -> str:
    """Map a 0.0-1.0 score to 'HIGH' | 'MEDIUM' | 'LOW' (uppercase)."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "LOW"
    return level_for(s * 100.0)
