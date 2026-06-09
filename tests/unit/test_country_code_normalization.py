"""P0 guard — pan-regional feed codes must never reach the CHAR(2)
country_code column as a wrong-but-valid ISO code (mig 067).

Root cause: 'XX-AF' truncates to 'AF' (Afghanistan), 'XX-LA'->'LA' (Laos),
'XX-AS'->'AS' (American Samoa), 'XX-ME'->'ME' (Montenegro). The normalizer
collapses any non-alpha-2 code to 'XX' before insert.
"""

from __future__ import annotations

import pytest

from app.tasks.ingestion import _normalize_country_code


@pytest.mark.parametrize("raw", ["XX-AF", "XX-LA", "XX-AS", "XX-ME"])
def test_pan_regional_codes_collapse_to_xx(raw):
    assert _normalize_country_code(raw) == "XX"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("FI", "FI"),
        ("us", "US"),        # lowercased input is upper-cased
        ("EU", "EU"),        # platform pseudo-code preserved
        ("XX", "XX"),
        ("AF", "AF"),        # a real Afghanistan GNews code is left intact
        ("ZA", "ZA"),
    ],
)
def test_valid_two_letter_codes_pass_through(raw, expected):
    assert _normalize_country_code(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "  ", "USA", "X", "GLOBAL", "XX-XX"])
def test_malformed_codes_collapse_to_xx(raw):
    assert _normalize_country_code(raw) == "XX"
