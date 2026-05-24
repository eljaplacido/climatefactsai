"""Unit tests for the structured Analyze-URL failure surface (§3.4 fix on 2026-05-23).

Covers:
- URLFetchException carries reason + status_code + title + remediation
- URLFetchException.detail() shape matches what we persist in failure_detail
- _classify_extraction_failure() heuristics correctly distinguish:
  * paywall_suspected — when paywall keywords are in the HTML
  * js_rendered_spa — when there are many <script> tags + an SPA marker
  * extraction_too_short — fallback when neither heuristic fires
- _FAILURE_COPY is complete for every defined reason constant

Stays pure: no HTTP, no DB, no FastAPI client. Runs in milliseconds.
"""

from __future__ import annotations

import pytest

from api.url_analysis_routes import (
    FAILURE_REASON_CLAIM_EXTRACTION_FAILED,
    FAILURE_REASON_EXTRACTION_TOO_SHORT,
    FAILURE_REASON_HTTP_4XX_OTHER,
    FAILURE_REASON_HTTP_5XX,
    FAILURE_REASON_HTTP_FORBIDDEN,
    FAILURE_REASON_HTTP_LEGAL_BLOCK,
    FAILURE_REASON_HTTP_NOT_FOUND,
    FAILURE_REASON_JS_RENDERED_SPA,
    FAILURE_REASON_NETWORK_ERROR,
    FAILURE_REASON_PAYWALL_SUSPECTED,
    FAILURE_REASON_REDIRECT_BLOCKED,
    FAILURE_REASON_RESPONSE_TOO_LARGE,
    FAILURE_REASON_TIMEOUT,
    FAILURE_REASON_UNKNOWN,
    FAILURE_REASON_VALIDATION_FAILED,
    URLFetchException,
    _FAILURE_COPY,
    _classify_extraction_failure,
)


# ---------------------------------------------------------------------------
# URLFetchException
# ---------------------------------------------------------------------------

class TestURLFetchException:
    """Pin the typed-exception shape that the frontend keys off."""

    def test_defaults_pull_from_failure_copy(self):
        exc = URLFetchException(FAILURE_REASON_PAYWALL_SUSPECTED)
        assert exc.reason == FAILURE_REASON_PAYWALL_SUSPECTED
        assert exc.title == _FAILURE_COPY[FAILURE_REASON_PAYWALL_SUSPECTED]["title"]
        assert exc.message == _FAILURE_COPY[FAILURE_REASON_PAYWALL_SUSPECTED]["message"]
        assert exc.remediation == _FAILURE_COPY[FAILURE_REASON_PAYWALL_SUSPECTED]["remediation"]
        assert exc.status_code is None
        assert exc.extra == {}

    def test_custom_message_overrides_default(self):
        exc = URLFetchException(
            FAILURE_REASON_HTTP_NOT_FOUND,
            message="Custom override message",
            status_code=404,
        )
        assert exc.message == "Custom override message"
        # title and remediation still come from copy
        assert exc.title == "Page not found"
        assert exc.status_code == 404

    def test_unknown_reason_falls_back_to_unknown_copy(self):
        exc = URLFetchException("definitely_not_a_real_reason")
        # title/message/remediation should fall back to the UNKNOWN copy
        assert exc.title == _FAILURE_COPY[FAILURE_REASON_UNKNOWN]["title"]
        assert exc.message == _FAILURE_COPY[FAILURE_REASON_UNKNOWN]["message"]

    def test_detail_payload_shape_minimal(self):
        exc = URLFetchException(FAILURE_REASON_TIMEOUT)
        d = exc.detail()
        assert set(d.keys()) == {"reason", "title", "message", "remediation"}
        assert d["reason"] == FAILURE_REASON_TIMEOUT

    def test_detail_payload_shape_with_status_and_extra(self):
        exc = URLFetchException(
            FAILURE_REASON_HTTP_FORBIDDEN,
            status_code=403,
            extra={"detected_keywords": ["subscribe", "premium"]},
        )
        d = exc.detail()
        assert d["status_code"] == 403
        assert d["extra"]["detected_keywords"] == ["subscribe", "premium"]
        assert d["reason"] == FAILURE_REASON_HTTP_FORBIDDEN

    def test_walks_like_an_exception(self):
        """Upstream `except Exception` paths must still see this as an Exception."""
        exc = URLFetchException(FAILURE_REASON_NETWORK_ERROR, message="oops")
        assert isinstance(exc, Exception)
        # str(exc) should be the message (Exception default behaviour)
        assert str(exc) == "oops"


# ---------------------------------------------------------------------------
# _FAILURE_COPY completeness
# ---------------------------------------------------------------------------

class TestFailureCopyCompleteness:
    """Every defined reason constant must have copy. Migrations to add a new
    reason must also add the copy — this test catches the omission."""

    ALL_REASONS = [
        FAILURE_REASON_HTTP_FORBIDDEN,
        FAILURE_REASON_HTTP_NOT_FOUND,
        FAILURE_REASON_HTTP_LEGAL_BLOCK,
        FAILURE_REASON_HTTP_4XX_OTHER,
        FAILURE_REASON_HTTP_5XX,
        FAILURE_REASON_TIMEOUT,
        FAILURE_REASON_RESPONSE_TOO_LARGE,
        FAILURE_REASON_EXTRACTION_TOO_SHORT,
        FAILURE_REASON_PAYWALL_SUSPECTED,
        FAILURE_REASON_JS_RENDERED_SPA,
        FAILURE_REASON_REDIRECT_BLOCKED,
        FAILURE_REASON_NETWORK_ERROR,
        FAILURE_REASON_VALIDATION_FAILED,
        FAILURE_REASON_CLAIM_EXTRACTION_FAILED,
        FAILURE_REASON_UNKNOWN,
    ]

    @pytest.mark.parametrize("reason", ALL_REASONS)
    def test_every_reason_has_title_message_remediation(self, reason):
        copy = _FAILURE_COPY.get(reason)
        assert copy is not None, f"_FAILURE_COPY missing entry for {reason!r}"
        assert copy.get("title"), f"{reason!r} has no title"
        assert copy.get("message"), f"{reason!r} has no message"
        assert copy.get("remediation"), f"{reason!r} has no remediation"


# ---------------------------------------------------------------------------
# _classify_extraction_failure heuristics
# ---------------------------------------------------------------------------

class TestExtractionFailureClassifier:
    """When article extraction yields < 50 chars, the classifier picks
    between paywall_suspected, js_rendered_spa, and extraction_too_short.
    These tests pin the heuristics so a future refactor doesn't silently
    flip the mapping."""

    def test_paywall_keywords_in_html_trigger_paywall_suspected(self):
        html = """
        <html><body>
            <article>
              <h1>Climate story</h1>
              <p>To continue reading, subscribe to continue.</p>
            </article>
        </body></html>
        """
        reason = _classify_extraction_failure(html, extracted_text="stub")
        assert reason == FAILURE_REASON_PAYWALL_SUSPECTED

    def test_subscriber_only_phrase_triggers_paywall(self):
        html = "<html><body>This content is for subscribers</body></html>"
        assert (
            _classify_extraction_failure(html, "stub")
            == FAILURE_REASON_PAYWALL_SUSPECTED
        )

    def test_many_scripts_plus_next_marker_triggers_js_rendered_spa(self):
        html = (
            "<html><body>"
            + ('<script src="/_next/static/chunks/a.js"></script>' * 6)
            + '<div id="__next"></div>'
            + ("x" * 6000)  # exceed the 5000-byte threshold
            + "</body></html>"
        )
        reason = _classify_extraction_failure(html, extracted_text="")
        assert reason == FAILURE_REASON_JS_RENDERED_SPA

    def test_few_scripts_does_not_trigger_spa(self):
        """A page with only 2 scripts shouldn't be flagged as a SPA even
        if it has a __next marker. This guards against false positives on
        Next.js-served static pages with limited JS."""
        html = (
            "<html><body>"
            "<script>1</script><script>2</script>"
            '<div id="__next"></div>'
            + ("x" * 6000)
            + "</body></html>"
        )
        # Only 2 scripts → fails the >= 5 check → falls through to too_short
        reason = _classify_extraction_failure(html, "")
        assert reason == FAILURE_REASON_EXTRACTION_TOO_SHORT

    def test_small_html_with_spa_markers_does_not_trigger_spa(self):
        """Tiny HTML shells (< 5000 bytes) should NOT be classified as
        JS-SPA even with markers + scripts — they may just be malformed."""
        html = (
            "<html><body>"
            + ('<script>x</script>' * 6)
            + '<div id="__next"></div>'
            + "</body></html>"
        )
        reason = _classify_extraction_failure(html, "")
        assert reason == FAILURE_REASON_EXTRACTION_TOO_SHORT

    def test_plain_short_html_falls_through_to_extraction_too_short(self):
        html = "<html><body><h1>Hi</h1></body></html>"
        reason = _classify_extraction_failure(html, extracted_text="Hi")
        assert reason == FAILURE_REASON_EXTRACTION_TOO_SHORT

    def test_paywall_check_runs_before_spa_check(self):
        """A page that LOOKS like a SPA but also contains paywall keywords
        should be classified as a paywall — paywall is the more actionable
        signal for the user."""
        html = (
            "<html><body>"
            + ('<script>x</script>' * 10)
            + '<div id="__next"></div>'
            + "Subscribe to continue reading our premium content."
            + ("x" * 6000)
            + "</body></html>"
        )
        reason = _classify_extraction_failure(html, "")
        assert reason == FAILURE_REASON_PAYWALL_SUSPECTED

    def test_empty_html_returns_extraction_too_short(self):
        reason = _classify_extraction_failure("", "")
        assert reason == FAILURE_REASON_EXTRACTION_TOO_SHORT
