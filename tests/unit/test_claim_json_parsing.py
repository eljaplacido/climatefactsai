"""P0 guard — the DeepSeek claim extractor must recover the ~34% of replies
that wrap the JSON array in markdown fences, prose preambles, an object
envelope, or a trailing comma (2026-06-09 Data-Layer audit P0 #3).

Before this fix a bare ``json.loads`` raised on all of those, dropping the
*whole article* to 0 claims. `_loads_claim_array` tolerates them; only a reply
with no salvageable array raises ClaimParseError (so the caller retries).
"""

from __future__ import annotations

import json

import pytest

from app.domains.intelligence.services import _loads_claim_array, ClaimParseError


_CLAIMS = [
    {
        "claim_text": "Arctic sea ice decreased 13% per decade since 1979",
        "claim_type": "factual",
        "claim_category": "statistical",
        "importance_score": 0.9,
        "claim_context": "Satellite data shows the decline.",
    },
    {
        "claim_text": "Emissions are likely to peak by 2025",
        "claim_type": "prediction",
        "claim_category": "predictive",
        "importance_score": 0.7,
        "claim_context": "Analysts project a near-term peak.",
    },
]


def test_plain_array_parses():
    assert _loads_claim_array(json.dumps(_CLAIMS)) == _CLAIMS


def test_json_fenced_array_parses():
    fenced = "```json\n" + json.dumps(_CLAIMS) + "\n```"
    assert _loads_claim_array(fenced) == _CLAIMS


def test_bare_fenced_array_parses():
    fenced = "```\n" + json.dumps(_CLAIMS) + "\n```"
    assert _loads_claim_array(fenced) == _CLAIMS


def test_prose_preamble_is_stripped():
    reply = "Here are the atomic claims I extracted:\n" + json.dumps(_CLAIMS)
    assert _loads_claim_array(reply) == _CLAIMS


def test_trailing_prose_is_stripped():
    reply = json.dumps(_CLAIMS) + "\n\nThat's all I could find."
    assert _loads_claim_array(reply) == _CLAIMS


def test_object_envelope_is_unwrapped():
    reply = json.dumps({"claims": _CLAIMS})
    assert _loads_claim_array(reply) == _CLAIMS


def test_trailing_comma_is_repaired():
    # A trailing comma before the closing bracket is the single most common
    # near-miss; serialise by hand so the comma survives.
    body = ",\n".join(json.dumps(c) for c in _CLAIMS)
    reply = "[\n" + body + ",\n]"
    assert _loads_claim_array(reply) == _CLAIMS


@pytest.mark.parametrize("reply", ["", "   ", "I could not find any claims."])
def test_unsalvageable_replies_raise(reply):
    with pytest.raises(ClaimParseError):
        _loads_claim_array(reply)


def test_object_without_claims_array_raises():
    with pytest.raises(ClaimParseError):
        _loads_claim_array(json.dumps({"summary": "no array here"}))
